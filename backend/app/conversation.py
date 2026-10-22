# SPDX-License-Identifier: AGPL-3.0-only
"""Retain acknowledged request constraints for bounded document follow-ups.

Session state contains requests, pending choices and population-scoped approval,
not previously calculated numbers. Every answer re-reads the source ledger. An
explicit null context token means the client has not acknowledged prior context;
it must remain different from an omitted token for legacy clients.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Conversation
"""

from __future__ import annotations

import re
import time
import uuid
from collections import OrderedDict
from typing import Any

from app.api.schemas import QueryRequest, QueryResponse
from app.core.exceptions import StaleWorkspaceError
from app.structured.cross_scope import IDENTITIES
from app.structured.engine import clarify, contains
from app.structured.grouped import resolve_group_followup
from app.structured.intent import SUM_WORDS
from app.structured.scopes import (
    document_scopes,
    named_scopes,
    replace_scope,
    scope_choice,
)


def clarification_question(question: str) -> bool:
    """Recognize a question about a pending clarification, not document evidence."""
    text = " ".join(question.strip(" ?.!\n").casefold().split())
    return bool(
        re.fullmatch(
            r"what clarification (?:do you need|you need|is needed|is required)|"
            r"what (?:do you need me|should i|must i) to clarify|"
            r"why (?:do you need|are you asking for) clarification|"
            r"(?:please )?explain (?:the |your )?clarification",
            text,
        )
    )


def counting_population(request: QueryRequest) -> tuple[object, ...] | None:
    """Identify a supported grouped SUM without retaining numerical answer facts."""
    if request.operation != "sum" or not request.fields or not request.group_field:
        return None
    # Approval identifies the calculation population, never its previous numeric result.
    return (
        request.source_file,
        request.document_id,
        request.workspace_revision,
        tuple(sorted(request.fields)),
        request.group_field,
        tuple(sorted(tuple(sorted(g)) for g in request.entity_groups)),
        tuple(
            sorted(
                [request.sheet_or_page]
                if request.sheet_or_page
                else request.source_scopes
            )
        ),
        tuple(sorted(request.filters.items())),
        request.record_scope,
        request.breakdown,
    )


class ConversationBook:
    """One-hour sessions, at most 100 chats and 20 acknowledged contexts each."""

    def __init__(self, capacity: int = 100, ttl: float = 3600) -> None:
        self.items: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.capacity, self.ttl = capacity, ttl

    def start(self, source: str, identity: str) -> str:
        """Create a session bound to an immutable document version."""
        now = time.monotonic()
        for key in list(self.items):
            if now - self.items[key]["touched"] > self.ttl:
                del self.items[key]
        while len(self.items) >= self.capacity:
            self.items.popitem(last=False)
        key = str(uuid.uuid4())
        self.items[key] = {
            "source": source,
            "identity": identity,
            "touched": now,
            "snapshots": OrderedDict(),
            "last": None,
        }
        return key

    def end(self, key: str) -> None:
        """New chat is idempotent and never removes document data."""
        self.items.pop(key, None)

    def remove_source(self, source: str) -> None:
        """Invalidate only chats associated with the removed document."""
        for key in list(self.items):
            if self.items[key]["source"] == source:
                del self.items[key]

    def resolve(
        self, request: QueryRequest, identity: dict | None, document: dict | None
    ) -> QueryRequest:
        """Resolve supported follow-ups using the client's acknowledged snapshot.


        Args:
            request: Current input; explicit null context means no inherited context.
            identity: Current ledger identity used to detect document replacement.
            document: Fresh schema and source rows used to resolve entities/fields.

        Returns:
            A copied request with supported constraints resolved, or the original input.

        Raises:
            StaleWorkspaceError: The session, document binding or context expired.

        This is a bounded resolver, not an arbitrary natural-language planner. Stored
        assistant answers never become numeric inputs to a later question.
        """
        key = request.conversation_id or ""
        item = self.items.get(key)
        if (
            not item
            or not identity
            or item["identity"] != identity["document_id"]
            or item["source"] != request.source_file
            or time.monotonic() - item["touched"] > self.ttl
        ):
            self.end(key)
            raise StaleWorkspaceError(
                "This chat expired or its document changed. Start a new chat."
            )
        item["touched"] = time.monotonic()
        self.items.move_to_end(key)
        # Explicit null is a fresh context; only omission permits the legacy latest-token fallback.
        token = (
            request.context_token
            if "context_token" in request.model_fields_set
            else item["last"]
        )
        if token is None or document is None:
            return request
        if token not in item["snapshots"]:
            raise StaleWorkspaceError(
                "That conversation context expired. Start a new chat."
            )
        previous, clarification, _ = item["snapshots"][token]
        if clarification_question(request.question):
            return previous.model_copy(
                update={
                    "conversation_id": key,
                    "context_token": token,
                    "document_id": request.document_id,
                    "workspace_revision": request.workspace_revision,
                }
            )
        q = request.question.strip()
        sheets = document_scopes(document)
        fields = sorted({f for row in document["rows"] for f in row["values"]})
        updates: dict[str, Any] = {
            "conversation_id": key,
            "context_token": token,
            "page": 1,
        }
        chosen = scope_choice(q, sheets)
        if chosen:
            return previous.model_copy(
                update={
                    **updates,
                    "sheet_or_page": chosen[0] if len(chosen) == 1 else None,
                    "source_scopes": chosen if len(chosen) != 1 else [],
                    "question": replace_scope(previous.question, sheets, chosen),
                    "aggregation_basis": "auto",
                    "breakdown": "source" if previous.breakdown != "none" else "none",
                }
            )
        grouped = resolve_group_followup(request, previous, document)
        if grouped is not None:
            return grouped
        if re.fullmatch(
            r"(?:sum|total)(?: (?:these|those|the|all))? (?:records|values|amounts)|sum (?:them|these|those)",
            q.strip(" ?.!"),
            re.I,
        ):
            return previous.model_copy(
                update={
                    **updates,
                    "operation": "sum",
                    "aggregation_basis": "all_selected_records",
                }
            )
        if (
            re.fullmatch(
                r"(?:use |sum )?(?:all )?(?:selected |source )?records[.!]?", q, re.I
            )
            and previous.fields
            and (
                previous.operation == "sum"
                or re.search(SUM_WORDS, previous.question, re.I)
            )
        ):
            # A typed confirmation keeps the acknowledged source population.
            return previous.model_copy(
                update={**updates, "aggregation_basis": "all_selected_records"}
            )
        if clarification:
            if q.casefold() in {"use detail records", "use summary records"}:
                return previous.model_copy(
                    update={
                        **updates,
                        "record_scope": (
                            "detail" if "detail" in q.casefold() else "summary"
                        ),
                    }
                )
            if q in fields:
                return previous.model_copy(
                    update={
                        **updates,
                        "fields": [q],
                        "question": previous.question + " " + q,
                    }
                )
            if re.fullmatch(
                r"(?:use |sum )?(?:all )?(?:selected |source )?records[.!]?", q, re.I
            ):
                return previous.model_copy(
                    update={**updates, "aggregation_basis": "all_selected_records"}
                )
        simple_entity = re.fullmatch(
            r"(?:and|what about|how about)\s+([\w-]+|[\"'][^\"']+[\"'])\s*[?.!]?",
            q,
            re.I,
        )
        identity_fields = [f for f in fields if f.casefold() in IDENTITIES]
        if (
            simple_entity
            and len(identity_fields) == 1
            and len(previous.fields) == 1
            and not previous.entity_groups
            and previous.breakdown == "none"
            and previous.operation in {"auto", "sum", "lookup"}
            and not re.search(
                r"\b(increase|growth|highest|lowest|maximum|minimum|before|after|except|excluding)\b",
                previous.question,
                re.I,
            )
            and simple_entity.group(1).strip("\"'").casefold()
            not in {"sum", "total", "records", "same", "all"}
            and not named_scopes(q, sheets)
            and not any(contains(q, f) for f in fields)
            and not re.search(r"\b(?:q[1-4]|20\d{2})\b", q, re.I)
        ):
            entity = simple_entity.group(1).strip("\"'")
            prefix = (
                "Total "
                if previous.operation == "sum"
                or re.search(SUM_WORDS, previous.question, re.I)
                else "What "
            )
            # Carry constraints, never the last answer's numbers. A new entity
            # changes the counting population, so previous approval is reset.
            return previous.model_copy(
                update={
                    **updates,
                    "question": prefix + previous.fields[0] + " for " + entity + "?",
                    "filters": {
                        k: v
                        for k, v in previous.filters.items()
                        if k != identity_fields[0]
                    },
                    "aggregation_basis": "auto",
                    "workspace_revision": request.workspace_revision,
                    "document_id": request.document_id,
                }
            )
        if not re.match(
            r"^(and\b|what about\b|how about\b|instead\b|now\b|same\b)", q, re.I
        ):
            return request
        resolved = previous.question
        filters = dict(previous.filters)
        chosen_scopes = named_scopes(q, sheets)
        changed = bool(chosen_scopes)
        if chosen_scopes:
            resolved = replace_scope(resolved, sheets, chosen_scopes)
            updates.update(
                sheet_or_page=chosen_scopes[0] if len(chosen_scopes) == 1 else None,
                source_scopes=chosen_scopes if len(chosen_scopes) != 1 else [],
                aggregation_basis="auto",
            )
        for field in fields:
            values = {
                str(row["values"][field])
                for row in document["rows"]
                if isinstance(row["values"].get(field), str)
            }
            new = [v for v in values if len(v) >= 2 and contains(q, v)]
            old = [
                v
                for v in values
                if len(v) >= 2
                and (contains(previous.question, v) or previous.filters.get(field) == v)
            ]
            if len(new) == 1 and old:

                def replace_entity(match: re.Match[str], target: str = new[0]) -> str:
                    return target

                for value in sorted(old, key=len, reverse=True):
                    resolved = re.sub(
                        r"(?<!\w)" + re.escape(value) + r"(?!\w)",
                        replace_entity,
                        resolved,
                        flags=re.I,
                    )
                if field in filters:
                    filters[field] = new[0]
                changed = True
        words = (
            re.sub(
                r"^(and|what about|how about|instead|now|same)\s*", "", q, flags=re.I
            )
            .strip(" ?.")
            .casefold()
        )
        new_fields = [f for f in fields if f.casefold() == words]
        if len(new_fields) == 1 and previous.fields:
            for field in previous.fields:
                resolved = re.sub(
                    re.escape(field), lambda m: new_fields[0], resolved, flags=re.I
                )
            updates["fields"] = new_fields
            changed = True
        quarters = set(re.findall(r"\bQ[1-4]\b", q.upper()))
        if len(quarters) == 1:
            quarter = next(iter(quarters))
            resolved = (
                re.sub(r"\bQ[1-4]\b", quarter, resolved, flags=re.I)
                if re.search(r"\bQ[1-4]\b", resolved, re.I)
                else resolved + " in " + quarter
            )
            updates["fields"] = [
                re.sub(r"\bQ[1-4]\b", quarter, f, flags=re.I) for f in previous.fields
            ]
            matches = [s for s in sheets if contains(s, quarter)]
            if matches:
                updates.update(
                    sheet_or_page=matches[0] if len(matches) == 1 else None,
                    source_scopes=[] if len(matches) == 1 else matches,
                )
            changed = True
        if not changed:
            return request
        return previous.model_copy(
            update={
                **updates,
                "question": resolved,
                "filters": filters,
                "workspace_revision": request.workspace_revision,
                "document_id": request.document_id,
            }
        )

    def clarification_response(self, request: QueryRequest) -> QueryResponse | None:
        """Explain an acknowledged pending request without retrieval or model calls."""
        if not clarification_question(request.question):
            return None
        item = self.items.get(request.conversation_id or "")
        token = (
            request.context_token
            if "context_token" in request.model_fields_set
            else item["last"] if item else None
        )
        saved, pending, _ = (
            item["snapshots"].get(token, (None, None, None))
            if item
            else (None, None, None)
        )
        if pending is None or saved is None:
            response = clarify(
                "There is no pending clarification in this chat. Ask your document question, including the measure and source scope you want."
            )
            response.status = "no_evidence"
        else:
            response = pending.model_copy(deep=True)
            response.answer = (
                "Question awaiting clarification: "
                + saved.question
                + "\n\n"
                + pending.answer
                + (
                    "\n\nChoose one of the displayed options, or rephrase the unclear part of that request."
                    if pending.clarification_options
                    else "\n\nRephrase the indicated part; the measure and groups already understood remain in this chat."
                )
            )
            response.coverage["pending_message"] = pending.answer
        response.execution_path = "conversation_clarification"
        return response

    def resume_counting_choice(
        self, request: QueryRequest, original: QueryRequest
    ) -> QueryRequest | None:
        """Reuse counting approval while repairing the same acknowledged population.

        Returns a copied request only when a pending repair has a matching confirmed
        population. Explicit basis options, changed source/metric/groups/filter/scope,
        missing acknowledgement or cleared context return None. Numerical results are
        not reused; the source ledger will be read again.
        """
        # Even an explicit reset to auto outranks previously acknowledged approval.
        if "aggregation_basis" in original.model_fields_set:
            return None
        item = self.items.get(original.conversation_id or "")
        token = (
            original.context_token
            if "context_token" in original.model_fields_set
            else (item["last"] if item else None)
        )
        _, pending, confirmed = (
            item["snapshots"].get(token, (None, None, None))
            if item
            else (None, None, None)
        )
        # Repair may keep the choice only when every population dimension still matches.
        if (
            pending is None
            or confirmed is None
            or counting_population(request) is None
            or counting_population(request) != counting_population(confirmed)
        ):
            return None
        return request.model_copy(update={"aggregation_basis": "all_selected_records"})

    def remember(
        self,
        key: str,
        request: QueryRequest,
        response: QueryResponse,
        original: QueryRequest | None = None,
    ) -> None:
        """Attach a response token and retain a bounded request/clarification snapshot.


        Args:
            key: Session receiving the new snapshot; an ended session is ignored.
            request: Understood constraints for the response just produced.
            response: Mutated only to attach the token the client may acknowledge.
            original: Raw request used to detect an explicit counting-basis reset.

        Returns:
            None. The response carries the token; no numeric answer is cached here.

        The next client request chooses which snapshot it actually saw. Keeping the latest
        server response alone would allow cancelled or unseen answers to steer follow-ups.
        """
        item = self.items.get(key)
        if item is None:
            return
        saved = request.model_copy(deep=True)
        fields = response.coverage.get("fields")
        if not saved.fields and isinstance(fields, list):
            saved.fields = [str(f) for f in fields]
        # Follow the client's acknowledged token, never an unseen server answer.
        acknowledged = (
            request.context_token
            if "context_token" in request.model_fields_set
            else item["last"]
        )
        _, previous_pending, confirmed = item["snapshots"].get(
            acknowledged, (None, None, None)
        )
        if (
            saved.aggregation_basis == "all_selected_records"
            and response.status in {"answered", "incomplete"}
            and response.grouped_results
            and counting_population(saved) is not None
        ):
            confirmed = saved.model_copy(deep=True)
        elif not (
            response.status == "clarification_required"
            and confirmed is not None
            and counting_population(saved) == counting_population(confirmed)
            and (
                response.coverage.get("unrecognized_terms")
                or (
                    previous_pending is not None
                    and response.execution_path == "conversation_clarification"
                )
            )
        ):
            confirmed = None
        if (
            original is not None
            and "aggregation_basis" in original.model_fields_set
            and original.aggregation_basis == "auto"
        ):
            confirmed = None
        token = str(uuid.uuid4())
        response.context_token = token
        pending = None
        if response.status == "clarification_required":
            # Store the request and clarification metadata, never source rows or
            # assistant-authored numerical facts as future calculation inputs.
            message = str(
                response.coverage.get("pending_message")
                or response.answer.splitlines()[0]
            )
            pending = clarify(message, fields=saved.fields)
            pending.clarification_options = [
                dict(c) for c in response.clarification_options
            ]
        item["snapshots"][token] = (saved, pending, confirmed)
        item["last"] = token
        while len(item["snapshots"]) > 20:
            item["snapshots"].popitem(last=False)
