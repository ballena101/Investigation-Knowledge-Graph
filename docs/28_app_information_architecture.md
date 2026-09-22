# IKF App information architecture

_Last updated: 2026-09-22_

## Purpose

The operational App is organised by **user intent**, not by the historical order
in which PoC capabilities were implemented.

This avoids mixing document processing, free-text questioning, evidence
exploration and human validation in the same page.

## Primary operational capabilities

### 1. Analyse Documents

Purpose:

- choose the governed source route;
- create a question-independent analysis;
- follow processing status;
- inspect what the analysis identified.

After a completed run the page exposes structured analytical outputs directly:

- Events / casualty sequence;
- Contributing Factors;
- Findings;
- Safety Issues;
- Safety Recommendations;
- evidence-derived analytical relationships.

Each displayed item preserves available report/page provenance.

This page does **not** ask free-text analytical questions and does not perform
human validation.

### 2. Ask / Compare LLMs

Purpose:

- provide the only operational free-text question surface for processed
  evidence;
- scope a question to the whole case, one document or selected documents;
- optionally include governed REFERENCE_CONTEXT;
- compare approved model outputs only where useful/allowed;
- preserve source/page citations and retrieval provenance.

QuestionRun remains separate from AnalysisGroup construction. Asking a question
does not rebuild the graph.

### 3. Findings & Knowledge

Purpose:

- read-only exploration of processed knowledge;
- browse evidence items and source pages;
- inspect the knowledge graph;
- retrieve deterministic similar MAIRA cases.

This page does **not** create QuestionRuns and does **not** make validation
decisions.

### 4. Review & Validate

Purpose:

- centralise human-governance actions;
- validate/reject/amend graph relationships;
- optionally request an evidence-bounded assistant correction proposal;
- review governed EMCIP mapping proposals;
- perform the SHIELD Gate-1 / Gate-2 workflow.

Assistant proposals remain advisory. Human review records are append-only and
authoritative according to the relevant workflow. Graph edges are not silently
overwritten.

### 5. News & Alerts

News remains an external-signal capability. It is not silently mixed with
validated investigation knowledge.

## Source ownership

- Class B — Published investigation material: MAIRA.
- Classes A/C/D: governed IKF-managed source routes.
- REFERENCE_CONTEXT: separate legal / IMO / technical corpus.
- SHIELD: separate persistent classification/taxonomy corpus.
- EMCIP: MAIRA-owned controlled analytical vocabulary.

## Legacy separation

The Commodore Clipper material remains a controlled project
reference/validation asset but is no longer exposed as a primary operational
App tab.

The operational pages must not depend on the Clipper demonstrator dataset.

## Streamlit compatibility

The searchable document selector uses the Streamlit `filter_mode` capability,
introduced in Streamlit 1.56.

The App requirements now enforce:

`streamlit[pdf]>=1.56.0,<2`

This avoids deploying an older Streamlit runtime that fails while building the
searchable multiselect. A previous failure occurred before the
`st.form_submit_button` line was reached, which also produced the secondary
Streamlit warning that the form had no submit button.

## Additional correction

The App direct-text pre-screen previously compared the visible input-mode value
against `DIRECT_TEXT`, even though the UI value is `Direct text`. The branch
condition has been corrected so non-Class-D direct text reaches the intended
privacy/classification pre-screen.

## Deployment safety

Before this information-architecture change, a backup branch was created:

`backup/pre-ux-separation-2026-09-22`

The main-source changes are not considered runtime validated until the
Databricks App is redeployed and the consolidated functional validation is
continued.

## Validation expectations after redeploy

1. App loads without the form/search-selector exception.
2. Analyse Documents:
   - classification-scoped catalogue is correct;
   - analysis can be created;
   - completed results expose events, contributing factors, findings, safety
     issues and recommendations with provenance.
3. Ask / Compare:
   - is the only free-text question workflow;
   - preserves QuestionRun provenance and source-layer separation.
4. Findings & Knowledge:
   - contains no Ask form;
   - contains no relationship-correction decision workflow;
   - remains evidence/graph/similar-case exploration.
5. Review & Validate:
   - contains direct human relationship review;
   - contains optional assistant relationship check and human decision;
   - contains EMCIP review;
   - contains SHIELD review.
6. The Commodore Clipper demonstrator is absent from the primary operational
   tab bar.


## Case-centric GUI refinement

Implemented in source on 2026-09-22 after the first simplified-capability
deployment was reviewed.

### Shared active analysis

The App now has one **Active analysis** selector in the sidebar.

That analysis is reused by:

- Analyse Documents results;
- Findings & Knowledge;
- Ask / Compare LLMs;
- Review & Validate;
- EMCIP and SHIELD review.

A compact persistent header shows the active analysis title/ID, information
class, source count and processing status.

When a new analysis is created it is queued to become the active analysis on
the next rerun. This avoids illegal mutation of an already-instantiated
Streamlit widget state in the same execution.

### Analyse Documents results

Completed analyses now expose a compact results dashboard with counts for:

- Events;
- Contributing Factors;
- Findings;
- Safety Issues;
- Safety Recommendations.

A horizontal result filter allows the investigator to focus on one category or
on analytical relationships.

Result cards place the description and investigation-evidence references side
by side.

State wording is explicit:

- ordinary extracted items are labelled **AI identified / candidate**;
- a Contributing Factor is shown as human validated only when its current
  human relationship review confirms a `CONTRIBUTED_TO` relationship.

This prevents model extraction from being visually confused with validated
knowledge.

### Ask scope

The evidence-scope control remains explicit because it changes the retrieval
boundary.

When the user chooses:

- **One document** → the next control is labelled
  **Use this document for the question**;
- **Selected documents** → the next control is labelled
  **Use these documents for the question**.

The page displays a **Question scope** summary immediately before the question
form, including whether legal/IMO/technical reference material is included.

The default remains the entire prepared case/analysis.

Technical model-route details are collapsed for normal A/B/C use. Class-D model
choice remains visible because it is an operational processing decision.

### Reduced technical clutter

The global model-routing/Article-9 matrix is now collapsed by default.

Analyse Documents hides endpoint/service details under **Technical processing
details**.

Review & Validate hides model-run IDs and evidence anchors under
**Technical provenance**.

The normal investigator view therefore prioritises the case, extracted
knowledge, evidence and human decisions.

### Review queue

Review & Validate is explicitly ordered as:

1. Relationship review;
2. EMCIP mapping review;
3. SHIELD classification review.

The optional assistant relationship check sits with relationship governance,
not with Findings & Knowledge.

Existing counters show reviewable/proposed, human-reviewed and remaining work.

### Safety / rollback

Backup branch before this case-centric GUI refinement:

`backup/pre-case-centric-gui-2026-09-22`

The changes remain **runtime-validation pending** until the updated Databricks
App is redeployed and checked.


## Pre-validation restoration: processing stages and graph workspace

Implemented in source on 2026-09-22 before continuing functional validation.

### Analyse Documents

The previously implemented four investigator-facing processing stages are
restored as the primary status view:

1. **Prepare evidence**
2. **Analyse evidence**
3. **Check output**
4. **Build result**

They are rendered horizontally as four compact status cards rather than as
vertical rows.

The Analyse Documents order is now:

1. create/configure analysis;
2. **Refresh status**;
3. four-stage horizontal processing view;
4. collapsed **Recent analyses** history;
5. structured **Analysis results**.

This keeps the current analysis result visible without allowing analysis
history to consume the page.

Technical stages remain available under the collapsed Technical details
section.

### Findings & Evidence

The previous Findings & Knowledge page is renamed **Findings & Evidence**.

It remains read-only and is responsible for:

- extracted concepts/findings/relationships;
- cited source pages and embedded evidence viewing;
- deterministic similar MAIRA cases.

The graph is no longer embedded as a secondary expander here.

### Knowledge Graph workspace

A dedicated **Knowledge Graph** tab is now a first-class capability.

It uses the shared Active analysis and supports:

- model-graph selection when more than one completed model graph exists;
- document-scope selection;
- concept/node-type filtering;
- relationship-type filtering;
- diagram layout selection;
- graph size counters;
- interactive Cytoscape rendering.

Available diagram layouts currently include force-directed, hierarchy, circle,
concentric and grid.

Document selection is an evidence-scope control. Node/relationship/layout
controls are view controls only and never mutate validated knowledge.

When a document subset is selected, graph nodes and relationships are limited
to items whose persisted evidence locations are supported by those documents,
plus structural relationships needed to connect the selected evidence-backed
concepts.

### Graph-scoped questions

The Knowledge Graph page can ask a question using the document scope currently
selected for the graph.

It reuses the governed QuestionRun and Ask Job infrastructure, but records:

`interaction_surface = KNOWLEDGE_GRAPH`

Normal Ask / Compare questions remain:

`interaction_surface = ASK_COMPARE`

The histories are therefore kept separate in the UI.

The graph question is grounded in governed source evidence. Visual
node/relationship filters do **not** silently remove passages from question
retrieval; only the selected document evidence scope changes retrieval.

REFERENCE_CONTEXT remains optional and remains separate from SOURCE_EVIDENCE.

Class-D graph questions continue to follow the approved Class-D model routes and
quota controls.

### Governance boundary

The Knowledge Graph workspace may change how knowledge is **viewed**, not what
is authoritative.

Actual relationship validation, rejection or amendment remains exclusively in
**Review & Validate**.

### Rollback

Backup branch created before this slice:

`backup/pre-graph-workspace-2026-09-22`

Status: **code/documentation complete; runtime validation pending**.


## Analysis summary versus Findings & Evidence

Refined on 2026-09-22 to remove remaining duplication.

### Analyse Documents — Analysis summary

The Analyse Documents page is now the processing/overview surface.

After the four processing stages, it shows only a compact summary of the active
analysis:

- Events count;
- Contributing Factors count;
- Findings count;
- Safety Issues count;
- Safety Recommendations count;
- analytical relationship count;
- graph concept count;
- graph relationship count.

It does not repeat the individual finding descriptions or page-level evidence.

The previous Recent analyses list has been removed. Analysis switching is owned
by the single shared **Active analysis** selector in the sidebar.

### Findings & Evidence — detailed drill-down

Findings & Evidence is the item-level inspection surface.

It is where the investigator:

- selects an Event, Finding, Contributing Factor, Safety Issue,
  Recommendation or relationship;
- reads the extracted description;
- sees the supporting source reference;
- opens the cited source page;
- inspects technical evidence IDs when needed;
- retrieves deterministic similar MAIRA cases.

The distinction is therefore:

- **Analyse Documents** = processing status + quantitative/structural overview;
- **Findings & Evidence** = qualitative item-level content + provenance.

This separation avoids showing the same extracted content twice.


## Findings & Evidence content index

Added on 2026-09-22.

The top of Findings & Evidence now contains a compact **Analysis content
index** with separate counts for:

- Events;
- Contributing Factors;
- Findings;
- Safety Issues;
- Safety Recommendations;
- Analytical Relationships.

The index is not an official investigation-report classification. It is a
navigation/index layer over the AI-derived analytical content of the active
analysis.

The investigator can select a category and the Evidence sheet is filtered to
that family only.

Analytical Relationships excludes structural graph links so that the category
contains investigation-analysis relationships rather than graph plumbing.

Detailed item text, source references and cited-page rendering remain in the
Evidence sheet below the index.
