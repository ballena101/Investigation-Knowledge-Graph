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

## Operational pages and the reference example

The operational pages use a selected existing `analysis_id`:

- **Analyse Documents** creates and runs an analysis;
- **Compare LLMs** compares model outputs already produced for the same
  analysis, question and evidence;
- **Review & Validate** reviews candidates belonging to the selected analysis;
- **Findings & Knowledge** explores the selected analysis and optionally opens
  its graph.

The Commodore Clipper is not the hidden dataset behind those pages. It has a
separate **complete worked example** sheet that demonstrates document analysis,
model-comparison status, review status, findings, graph, MAIRA similar-case
retrieval status and news-alert status together.

Graph colours encode node and relationship types consistently. The App also
displays a colour key so colour is explanatory rather than decorative.

## Similar-case retrieval

Findings & Knowledge will search two sources separately:

1. the MAIRA investigation-report/PDF repository, returning candidate similar
   cases with a short evidence-grounded description and report provenance;
2. the news tables, returning potentially related external alerts or an
   explicit “no related news alerts identified” result.

The LLM may support query formulation, ranking and short descriptions, but the
result must retain source type and provenance. News must remain visibly
separate from official investigation-report evidence.


## Question-independent analysis and Ask / Compare

The simplified capability model now distinguishes two user intents.

### Analyse Documents

This creates a reusable evidence/knowledge base. It contains:
- classification;
- source selection;
- optional description;
- processing progress;
- evidence/graph outputs.

It does not ask the investigator to formulate the analytical question.

### Ask / Compare LLMs

This is the interaction surface for free-text questions.

Planned scope control:

```text
Evidence scope
○ Entire processed case
○ One document
○ Selected documents

Question
[ free text ................................ ]

Model mode
○ Default model
○ Compare models
```

The answer surface must always place evidence references close to the answer,
using document/report name plus page/page range. Page citations must not be
hidden only inside technical provenance fields.


## Operational Ask / Compare interaction

The Ask / Compare capability now has an operational source design:

```text
Select processed analysis
        ↓
Evidence scope
  ○ whole case
  ○ one document
  ○ selected documents
        ↓
Free-text question
        ↓
Approved model route
        ↓
Answer
+ report/page citations
+ cited-page PDF viewer
```

For Class D only, the model-mode control allows:
- GPT-OSS 20B;
- Llama 3.3 70B;
- Both.

For A/B/C, the class-approved default model is used automatically.

Question history is preserved per AnalysisGroup. Each QuestionRun displays its
scope, status and retrieval provenance. Governed MAIRA retrieval is explicitly
labelled when activated.

The existing analysis/model outputs remain available below the Ask interaction,
but asking a question never rebuilds the graph.


## Reference context

Ask / Compare LLMs has an optional:

`Include legal / IMO / technical reference context`

control.

When enabled, the App retrieves relevant passages from the dedicated governed
IKF reference corpus. The user does not need to create or select another
analysis merely to provide Directive/IMO/technical background.

The answer surface keeps the two citation groups visually distinct:

- **Case evidence — SOURCE_EVIDENCE**
- **Reference context — REFERENCE_CONTEXT**

Reference context may explain framework, methodology or technical background
but is never presented as proof that a case fact occurred.


## SHIELD in Review & Validate

The SHIELD section reuses the selected analysis/model and shows:

- number of Gate-1 eligible contributing factors;
- persistent SHIELD source availability;
- Generate / refresh SHIELD proposals;
- human-validated factor and target;
- assistant SHIELD proposal;
- SHIELD corpus snapshot;
- cited SHIELD taxonomy page;
- latest Gate-2 human review;
- VALIDATED / REJECTED / AMENDED controls.

If Gate 1 changes after proposal generation, the proposal is visibly marked
STALE and Gate-2 review is disabled until proposals are regenerated.
