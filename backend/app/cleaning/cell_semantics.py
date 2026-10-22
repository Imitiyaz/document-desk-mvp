# SPDX-License-Identifier: AGPL-3.0-only
"""Retain standard Excel numeric units without evaluating formulas/display rounding.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Cleaning
"""

from __future__ import annotations

import re
from decimal import Context, Decimal
from typing import Any


def semantic_cell(value: Any, number_format: str) -> Any:
    """Use stored precision; respect standard percent, currency and quoted units."""
    if (
        value is None
        or isinstance(value, bool)
        or not isinstance(value, (int, float, Decimal))
    ):
        return value
    # Use the supplied decimal representation; do not add a binary-float conversion artifact.
    number = Decimal(str(value))
    if not number.is_finite():
        return value
    operators = re.sub(r'"[^\"]*"|\\.', "", number_format)
    percent = "%" in operators
    code = re.search(r"\[\$([A-Z]{3})(?:-|\])", number_format)
    symbols = {code[1]} if code else set(re.findall(r"[$€£¥]", number_format))
    if len(symbols) > 1 or (percent and symbols):
        return f"{value} [ambiguous source format: {number_format}]"
    if percent:
        number = Context(prec=80).multiply(number, Decimal(100))
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if percent:
        return text + "%"
    if symbols:
        unit = next(iter(symbols))
        return (unit + " " if len(unit) == 3 else unit) + text
    units = [
        u.strip()
        for u in re.findall(r'"([^\"]*)"', number_format)
        if re.fullmatch(r"\s*[A-Za-z][A-Za-z0-9²³/·^.-]{0,15}\s*", u)
    ]
    scaling = bool(re.search(r"[0#?],+(?:$|[^0#?.,])", operators))
    if units and not scaling:
        return text + " " + " ".join(units)
    if "%" in number_format:
        return text + "%"
    return value
