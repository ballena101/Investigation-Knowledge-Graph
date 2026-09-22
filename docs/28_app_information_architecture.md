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
