# Simple capability-based App interface

Status: UI implemented; individual capabilities remain subject to their own
validation and connection status.

## Decision

The App must not force every user through the complete investigation-analysis
pipeline when the user only needs one function. The pipeline remains available
underneath for provenance, governance and reproducibility, while the interface
is organised around five direct capabilities:

1. **News & Alerts** — country news dashboard and, later, read-only LLM queries
   over governed news views.
2. **Analyse Documents** — start an evidence-grounded document or direct-text
   analysis.
3. **Compare LLMs** — inspect independent answers against the same evidence;
   opening or generating a graph is not a user prerequisite.
4. **Review & Validate** — review relationships and EMCIP mappings, followed
   later by separately reviewed SHIELD suggestions.
5. **Findings & Knowledge** — search or ask about processed findings and open a
   graph only when relationship visualisation is useful.

The Terms of reference remain available as supporting information rather than
as a capability.

## Why “Findings & Knowledge”

“Findings” provides a clear investigation-oriented entry point. “Knowledge” is
retained because the capability also covers validated relationships, cross-case
retrieval and other structured information that is broader than the findings
of a single investigation.

The LLM belongs inside this capability as a contextual assistant. It is not a
separate main-menu function. Its responses must identify their sources and
distinguish model candidates from human-validated knowledge.

## Knowledge graph integration

The knowledge graph remains a central data structure but is not a mandatory UI
step. It is exposed as:

- an optional view in Findings & Knowledge;
- an optional relationship-oriented view during review;
- an evidence/provenance structure used by the other capabilities underneath.

Future LLM-assisted graph correction follows this controlled sequence:

1. the user selects a relationship and requests a review;
2. the LLM checks the original evidence;
3. the App displays the current relationship and the proposed replacement;
4. the user approves or rejects the proposal;
5. only an approved change updates canonical knowledge;
6. the previous relationship, proposal, evidence, reviewer and model/prompt
   provenance remain recorded.

The LLM must not directly modify validated graph knowledge.

## Partial availability

Unavailable functions are visible only as clearly labelled, disabled previews.
The interface must not imply that a preview is operational. As of this UI
version:

- the existing investigation-analysis and review functions remain active;
- Class D dual-model results remain available for comparison;
- the Commodore Clipper reference graph remains available;
- the news dashboard/table connection is pending;
- direct MAIRA benchmark comparison in the App is pending;
- LLM search over findings is pending;
- LLM-assisted relationship correction is pending;
- SHIELD suggestion/review is pending and may occur only after the contributing
  factor has been human validated.

News is treated as external, unvalidated information and must not be silently
merged with validated investigation knowledge.
