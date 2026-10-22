# Development and delivery lifecycle

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

This guide defines the contribution/release workflow for this application. It is a practical engineering process, not a claim of TOGAF, ISO, NIST or MITRE certification.

## Roles and decision gates

One person can hold several roles, but each decision still needs an explicit owner.


**Table LIFE-T01 — Roles and decision gates.**

| Gate | Owner | Required evidence |
| --- | --- | --- |
| Define change | Maintainer / requester | User outcome, supported document assumptions, acceptance examples and exclusions |
| Design | Implementer + reviewer | Affected contracts, data/security implications, compatibility and rollback approach |
| Implement | Contributor | Focused branch, readable changes, tests and documentation |
| Verify | Reviewer | Independent expected facts, automated results and identified test substitutions |
| Approve release | Maintainer | Remaining limitations, dependency/license review, platform/model evidence and rollback readiness |
| Operate / retire | Operator | Backup/restore, monitoring, incident handling and data-retention disposition |

**Figure LIFE-01 — Engineering decision gates and release ownership.**

```mermaid
flowchart TD
    Need["`Outcome and acceptance
contract`"] -->|"`Agree scope and
exclusions`"| Design["`Design, threats and
data changes`"]
    Design -->|"`Approve contracts and
rollback`"| Branch["`Focused implementation
branch`"]
    Branch -->|"`Implementation and
expectations`"| Verify["Tests and code review"]
    Verify -->|"Review results and risks"| Gate{"`Enough
evidence?`"}
    Gate -->|"`No: bound corrective
work`"| Design
    Gate -->|"Yes: present conditions"| Approval["`Maintainer release
approval`"]
    Approval -->|"`Record acceptance
conditions`"| Release["`Versioned source and
checksums`"]
    Release -->|"Install reviewed version"| Operate["`Observe, recover and
manage retention`"]
    Operate -->|"`New requirements or
incidents`"| Need
    class Gate decision
    class Approval,Release success
    classDef default fill:#F1F5F9,stroke:#64748B,color:#0F172A,font-size:15px,stroke-width:1.3px
    classDef success fill:#DCFCE7,stroke:#15803D,color:#14532D,font-size:15px
    classDef error fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D,font-size:15px
    classDef decision fill:#FEF3C7,stroke:#B45309,color:#78350F,font-size:14px
    classDef model fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95,font-size:15px
    classDef storage fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,font-size:15px
    classDef interface fill:#CCFBF1,stroke:#0F766E,color:#134E4A,font-size:15px
    linkStyle default font-size:12px,color:#334155
```

A requirement becomes a reviewed design and focused change. Independent verification gates release approval; insufficient evidence returns to design. Operation, retention and recovery feed the next requirement instead of treating deployment as the end of engineering.


## Change discipline

Record a reproducing request, source facts and expected behavior before changing a parser, scope resolver or calculation. Cover the class of failure using varied names/layouts/wording, rather than adding fixture-specific terms.

Separate raw source facts, interpretation rules, derived results and presentation. Review defaults and failure paths as carefully as successful examples. A “safe” refusal is not a useful answer to an answerable question.

Keep architecture decisions short: context, decision, alternatives, consequences and verification. Public records should explain enduring engineering choices rather than contain private conversations, host paths or raw diagnostic transcripts.

## CI implemented in this repository

The workflow in `.github/workflows/ci.yml` runs on pull requests, pushes to main and manual dispatch. It uses read-only repository permissions, commit-pinned actions, no deployment credentials and no automatic release/publish step.

**Figure LIFE-02 — Implemented CI checks and manual release decision.**

```mermaid
flowchart TD
    Event["`Pull request, main push
or manual run`"] -->|"`Check source and
documentation`"| Repo["`Repository and catalog
guards`"]
    Event -->|"Isolated Python matrix"| Backend["`Backend tests and
quality checks`"]
    Event -->|"`Node build and component
checks`"| Frontend["`Types, React tests,
audit and build`"]
    Event -->|"Isolated browser servers"| Browser["`Controlled browser
workflows`"]
    Event -->|"`Compose; build on manual
dispatch`"| Docker["`Container configuration
and optional image
build`"]
    Repo -->|"`Catalog, links and
boundaries`"| Review["`Maintainer reviews all
results`"]
    Backend -->|"`Tests and static
analysis`"| Review
    Frontend -->|"`Rendering, typing and
build`"| Review
    Browser -->|"`Actual requests and
evidence`"| Compare["`Independent
expectations and
viewport comparison`"]
    Compare -->|"`Compare values, sources,
status`"| Review
    Docker -->|"`Config / build, not
model proof`"| Review
    Review -->|"`Acceptance and license
gates`"| Decision["`Approve, revise or
reject`"]
    class Browser interface
    class Decision decision
    classDef default fill:#F1F5F9,stroke:#64748B,color:#0F172A,font-size:15px,stroke-width:1.3px
    classDef success fill:#DCFCE7,stroke:#15803D,color:#14532D,font-size:15px
    classDef error fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D,font-size:15px
    classDef decision fill:#FEF3C7,stroke:#B45309,color:#78350F,font-size:14px
    classDef model fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95,font-size:15px
    classDef storage fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,font-size:15px
    classDef interface fill:#CCFBF1,stroke:#0F766E,color:#134E4A,font-size:15px
    linkStyle default font-size:12px,color:#334155
```

Repository, backend, frontend, controlled browser and Compose-configuration checks run independently. Image builds run only on manual dispatch; that CI job does not establish host-model or target-runtime behavior. Comparison expectations complement browser success. A maintainer reviews results before a release decision; CI has no authority to publish or deploy automatically.


GitHub branch protection, required checks, private vulnerability reporting and secret-scanning settings are repository settings; source files cannot enable them. Configure them separately when operating a hosted repository.

## Continuous delivery boundaries

CI validates changes. Continuous delivery would additionally prepare reviewed release artifacts and a deployment-ready package. Continuous deployment would automatically install them into an environment. This repository does not implement automatic deployment, signing/attestation or complete environment promotion.

Do not add write permissions, production secrets, auto-merge or `pull_request_target` execution of untrusted code without a specific reviewed need. Review action/dependency update PRs; do not treat dependency automation as an approval mechanism.

## Release evidence

Before tagging an application release, record:

- Source revision and complete runtime/tool dependency resolution.
- Schema, extraction-policy and model/configuration versions.
- Synthetic and representative-document results, including unanswerable/unknown-entity cases.
- Real-model, storage and target-platform evidence separately from fake-backend tests.
- Visual/keyboard checks and operating limits measured on the target hardware.
- Security/license decisions, open issues and an exercised rollback/restore procedure.

Retain sensitive/raw evidence in an access-controlled system. Publish only sanitized summaries. Never republish a trace containing source documents or credentials merely because a test passed.

## Traceability

Link each requirement to its design decision, implementing change, test/reference facts, observed result and disposition. Track correctness/security blockers separately from improvements. A high coverage percentage or a resolved citation marker alone cannot close a correctness issue.

Retirement includes stopping services, retaining/revoking access as appropriate, disposing of indexes/backups/logs according to policy and documenting which user originals remain outside application control.
