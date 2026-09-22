# IKF implementation status and roadmap

_Last updated: 2026-09-22_

This document is the operational implementation tracker for the current IKF
Proof of Concept. It complements the architectural roadmap and is updated at
the end of each implementation slice.

## 1. Current operating principle

IKF remains the orchestration, review and validated-knowledge layer.

MAIRA remains the canonical investigation evidence layer for documents,
passages, provenance, governed terminology and governed retrieval.

The App must keep source evidence, reference material, controlled taxonomies
and human-validated knowledge distinct.

## 2. DONE

### App workflow and navigation

- Simplified primary navigation so investigators can access analysis, model
  comparison, review and findings without walking through the full pipeline.
- Simplified investigator-facing processing progress to:
  1. Prepare evidence
  2. Analyse evidence
  3. Check output
  4. Build result
- Technical pipeline stages remain available under Technical details.
- Compare-LLMs status refresh uses a Streamlit fragment so refresh no longer
  resets the user to the first tab.
- Vessel graph styling updated so the fallback `Subject vessel` label is
  visible.

### Graph sequence representation

- Added deterministic fallback `Subject vessel` only when source evidence
  refers to one unnamed vessel and the LLM omitted the vessel node.
- Vessel connects only to the first supported event in the event sequence.
- Explicit source times may establish deterministic `FOLLOWED_BY` chronology.
- `FOLLOWED_BY` does not imply causality.
- Structural `INVOLVED_IN` links are excluded from semantic human review.

### Direct-text performance

- Direct-text preparation no longer installs PDF/DOCX extraction libraries.
- Removed unnecessary explicit Python restart in the direct-text path.
- Added `extraction_duration_seconds` to measure the actual extraction stage.
- App exposes evidence-source mode and extraction timing under Technical
  details.

### MAIRA canonical passage integration

- Normal App document analysis is MAIRA-first by full SHA-256.
- When a source matches exactly one MAIRA document, IKF consumes MAIRA
  canonical passages.
- MAIRA passage ID, exact passage text, text SHA-256, page bounds, order and
  chunking metadata are preserved.
- Ambiguous SHA matches fail closed.
- Unmatched documents temporarily continue through the IKF local parser.
- Direct text remains an IKF-specific ingress.
- Terminology gate aligned to MAIRA operational review status
  `HUMAN_VALIDATED`.
- Added notebook 32 to validate that normal App analyses preserve the
  MAIRA/IKF passage contract.

### Unified document catalogue

- MAIRA investigation documents are now exposed upstream in the App catalogue.
- Added notebook 33 to synchronise MAIRA investigation-document metadata into
  Neo4j `SourceDocument` catalogue nodes without copying PDFs.
- MAIRA ownership is explicit with `source_managed_by = MAIRA`.
- IKF volume documents are explicit with `source_managed_by = IKF`.
- Duplicate physical files are deduplicated by SHA-256, preferring the MAIRA
  canonical entry.
- MAIRA-owned source files are exempt from IKF source-retention semantics.
- User-facing selector identifies repository and MAIRA document role.
- The underlying catalogue can contain both owners, but the analysis selector
  is now classification-scoped: Class B exposes MAIRA only; A/C/D expose IKF
  only.

### Explicit question answering and evidence traceability

- Analysis objective/question is now an explicit model output contract.
- New runs return a distinct evidence-grounded answer to the user's question.
- The answer must return valid supporting passage IDs.
- Answers without valid passage references are not presented as grounded.
- Graph nodes/relationships and the explicit answer carry human-readable
  report/page references.
- Added machine-readable evidence locations:
  `document_id|page_start|page_end`.

### Evidence sheet and source viewer

- Findings & Knowledge now contains an Evidence sheet.
- Investigator can inspect the explicit answer, graph nodes and relationships.
- Each evidence item exposes description, report/page references and technical
  passage IDs.
- Viewer supports both source repositories:
  - IKF: `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources`
  - MAIRA: `/Volumes/bdw_analysis_prod/maira/source_documents`
- For MAIRA canonical evidence, viewer uses MAIRA's original
  `documents.file_path`; no IKF source copy is required.
- Source PDF is read through Databricks Files API using the logged-in user's
  forwarded user token.
- Unity Catalog permissions therefore remain authoritative.
- Primary viewer renders the cited page range; full report is available in a
  collapsed viewer.
- Added Streamlit PDF and PyMuPDF dependencies.
- Updated user-authorization notebook so enabling scopes preserves all existing
  App resources rather than replacing them.

### Prepare-evidence failure fix

- Identified a cross-repository runtime dependency: notebook 15 could match a
  MAIRA document but fail when the separate MAIRA Python package was not on the
  automated job's `sys.path`.
- Notebook 15 now uses the authoritative MAIRA package when importable and a
  strict V0.1 compatibility implementation otherwise.
- The fallback validates required fields, positive page/order integers,
  SHA-256 values and exact passage-text hash parity before materialising the
  IKF analysis-scoped evidence.
- The compatibility path preserves MAIRA passage identity and does not create a
  second passage identity.
- Errors during evidence-route preparation now set
  `PREPARE_EVIDENCE_FAILED` with the actual exception text on the
  `AnalysisGroup`.
- The App maps this technical failure to the user-facing Prepare evidence step.


### Governed retrieval preflight started

- Added notebook `34_validate_governed_maira_retrieval_preflight.py`.
- The notebook is read-only and validates:
  - governed query specification availability;
  - governed concept rows/component roles;
  - supported deterministic relationship type;
  - operational `HUMAN_VALIDATED` terminology;
  - MAIRA MAIN_REPORT corpus/passages.
- This does not yet activate governed retrieval in the normal App workflow.

## 3. NEXT — current milestone

### Production-readiness and consolidated validation

The consolidated release preflight has now passed in Databricks with
**0 warnings and 0 errors**. SHIELD and authoritative REFERENCE_CONTEXT are
indexed.

The current milestone is **functional runtime validation of the simplified App
information architecture**.

Next execution step:

1. pull current GitHub `main`;
2. redeploy the App with the pinned Streamlit requirement;
3. verify the App loads without the searchable-selector/form exception;
4. run one fresh Class-B MAIRA analysis;
5. validate structured outputs, citations and source-page rendering;
6. continue the feature-specific validators in
   `docs/26_consolidated_runtime_validation.md`;
7. record observed PASS/FAIL results here.

### Consolidated runtime validation sequence

The eventual test session should include:

- notebook 32 — MAIRA passage contract;
- notebook 35 — source viewer/page ranges;
- notebook 38 — scoped Ask provenance;
- notebook 43 — Class-D pre-screen;
- notebook 44 — REFERENCE_CONTEXT indexing;
- notebook 45 — SHIELD corpus indexing;
- notebook 47 — SHIELD proposal Job;
- notebook 48 — SHIELD two-gate validation;
- notebook 50 — relationship-correction Job;
- notebook 51 — relationship-correction governance;
- notebook 53 — Similar MAIRA Cases Job;
- notebook 54 — similar-case deterministic provenance.

Expected App Job resources after setup:

- `analysis_job`;
- `class_d_analysis_job`;
- `ask_job`;
- `emcip_mapping_job`;
- `shield_proposal_job`;
- `relationship_correction_job`;
- `similar_cases_job`.

News/dashboard integration remains outside this conversation.

## 4. PENDING — planned implementation sequence

### P1 — consolidated production-readiness validation

- release/preflight validator: **RUNTIME PASS — 0 warnings / 0 errors**;
- governed SHIELD corpus: **RUNTIME PASS**;
- authoritative REFERENCE_CONTEXT corpus: **RUNTIME PASS**;
- simplified App capability separation: **CODE COMPLETE; REDEPLOY/VALIDATION PENDING**;
- one consolidated Databricks functional test session: **IN PROGRESS**;
- reproducible benchmark/retrieval snapshots;
- permissions/scopes validation;
- retention validation;
- rollback/deployment notes;
- final update of the capability matrix from code-complete to runtime-validated.

### P2 — external signals / News

- Keep News & Alerts separate as external/unvalidated information.
- This work remains in the separate News/dashboard conversation unless
  explicitly brought back here.
- Do not mix news with validated investigation findings.

## 5. Deferred UI improvements

- Potential catalogue grouping by MAIN_REPORT / ANNEX / APPENDIX.
- Faster browse for larger MAIRA repositories.
- Optional direct jump from answer citations to the matching Evidence-sheet
  item.

## 6. Definition of milestone completion

An implementation slice is considered complete only when:

- code is committed to GitHub;
- material architecture/governance decisions are documented in GitHub;
- the Databricks run is validated where applicable;
- evidence/provenance remains traceable;
- no new parallel canonical data model is introduced;
- this implementation-status document is updated with DONE / NEXT / PENDING.


### Classification-driven document catalogue

Implemented in code on 2026-09-22:

- Class A — Public / technical → IKF-managed documents only.
- Class B — Published investigation material → MAIRA investigation documents
  only.
- Class C — Internal / restricted → IKF-managed documents only.
- Class D — Protected / confidential → IKF-managed documents only.
- Direct text is unaffected by this document-catalogue filter and continues to
  follow the selected information-class/model route.
- The App displays the active catalogue scope and available-document count.

Reason: MAIRA is the actual canonical store for saved investigation reports;
the remaining project/technical documentation is held in the IKF-managed
library.

Status: **code complete; runtime validation intentionally deferred** to avoid an
additional App deployment/run before the next planned validation session.


### Searchable classification-scoped document selector

Implemented in code:
- the Available documents multiselect now supports typing/filtering;
- Class B searches only MAIRA investigation material;
- Classes A/C/D search only IKF-managed documents;
- no cross-repository search is performed after classification selects the
  source domain.

Status: code complete; runtime validation deferred.


### Question-independent analysis UX

Implemented in code:
- removed the free-text analytical question from Analyse Documents;
- replaced it with optional descriptive metadata;
- document extraction/graph resolution no longer uses an analysis objective;
- renamed Compare LLMs to Ask / Compare LLMs;
- existing model comparison remains visible;
- scoped free-text question execution is implemented in source through
  QuestionRun + the dedicated Ask Job.

### Page-citation visibility

Implemented in code:
- completed model-run panels now show a visible Source pages block;
- normal completed analyses show aggregated report/page references from their
  graph evidence;
- Findings & Knowledge retains item-level source/page references and PDF
  evidence viewing;
- older analyses without persisted citation metadata explicitly explain that a
  rerun is required.

### Source viewer validation gap

- Added read-only notebook `35_validate_source_viewer_metadata.py` to validate
  source paths, PDF readability, evidence locations and page-range validity
  before App rendering is tested.

The PDF-viewer implementation is present in code and uses:
- Databricks user authorization;
- Files API `files` scope;
- MAIRA or IKF governed source paths;
- Streamlit `st.pdf`;
- PyMuPDF cited-page extraction.

However, source rendering has **not yet been runtime-validated after the latest
deployment changes**. Existing/older analyses do not contain the new
`evidence_locations` metadata, so they cannot demonstrate the page-linked
viewer without a fresh citation-enabled run.

Status: code complete; runtime validation deferred to the next consolidated
Databricks test session.


### Scoped Ask / Compare backend

Implemented in code:
- added `QuestionRun` as a separate interaction from AnalysisGroup creation;
- scope can be whole case, one document or selected documents;
- questions do not rebuild or modify the graph;
- added dedicated one-task Lakeflow Job definition:
  `Investigation KG - Ask Processed Evidence`;
- added notebook `36_ask_processed_evidence.py`;
- added notebook `37_create_ask_processed_evidence_job.py`;
- App resource binding is `ASK_JOB_ID <- ask_job`;
- A/B/C use their class-approved default model;
- D supports GPT-OSS 20B / Llama 3.3 70B / Both;
- Class-D question text is encrypted before persistence;
- answers preserve passage IDs, report/page references and viewer locations;
- cited PDF pages can be rendered directly in Ask results;
- ordinary large scopes use deterministic MAIRA free-text lexical retrieval
  rather than silent truncation;
- QuestionRun/QuestionModelRun content is included in retention cleanup.

Status: **code complete; runtime validation deferred**.

### Exact governed MAIRA query integration

Implemented in code:
- Class-B free-text questions are normalised conservatively;
- only an exact match to one persisted MAIRA `user_query` activates governed
  query execution;
- no fuzzy/LLM semantic mapping is performed;
- the IKF wrapper now supports both MAIRA `FOLLOWED_BY` and
  `CONTRIBUTED_TO` deterministic detectors;
- governed retrieval can be restricted to selected document IDs;
- positive governed evidence narrows the LLM evidence set to the supported
  passages;
- zero governed support returns a deterministic insufficient-evidence result
  without calling the LLM;
- Ask results expose `retrieval_mode`, governed query ID and provenance.

Status: **code complete; runtime validation deferred**.

### Ask validation

Added read-only notebook:
`38_validate_scoped_ask_run.py`.

It validates:
- QuestionRun → AnalysisGroup linkage;
- scope-document validity;
- answer passage IDs remain inside the selected scope;
- citation page locations are backed by scoped passages;
- governed query metadata resolves to a persisted MAIRA query specification;
- deterministic no-support runs do not also contain model-generated answers.

Required success marker:
`PASS — SCOPED ASK / COMPARE RUN IS EVIDENCE-BOUNDED`.


### Large-scope deterministic free-text retrieval

Implemented in code:
- MAIRA now owns reusable
  `DETERMINISTIC_FREE_TEXT_LEXICAL_V0.1`;
- IKF uses it automatically when an ordinary free-text evidence scope exceeds
  the all-passages limit;
- Class-B expansions use only `HUMAN_VALIDATED` terminology mapped to governed
  EMCIP values;
- A/C/D use raw deterministic query terms only;
- no embeddings or LLM query rewriting are introduced;
- whole passages are selected under controlled passage/character budgets;
- zero lexical matches return a deterministic insufficient-evidence result;
- every answering run persists a deterministic retrieval snapshot;
- notebook 38 now verifies that answer passage IDs remain inside both the user
  scope and the retrieval snapshot.

Status: **code complete; runtime validation deferred**.


### Generic relationship review and EMCIP mapping review

Implemented in code.

Relationship review:
- no longer depends on the Commodore Clipper demo dataset;
- only completed AnalysisGroups are offered for generic review;
- Class-D dual-model graphs are reviewed per model_run_id;
- each candidate relationship shows report/page evidence and cited PDF page;
- human reviews are append-only and linked to AnalysisGroup/source/target nodes;
- graph relationships are not overwritten;
- notebook 39 validates analysis/model/edge provenance.

EMCIP mapping:
- added on-demand generic proposal notebook 40;
- added Job setup notebook 41;
- added App resource `emcip_mapping_job`;
- MAIRA operational registry remains the only taxonomy source;
- deterministic shortlist precedes the LLM;
- the LLM may select a shortlist candidate or NO_MAPPING only;
- human VALIDATED/REJECTED/AMENDED review is independent;
- human amendment must select another governed shortlist candidate;
- source report/page and PDF evidence are visible during review;
- notebook 42 validates proposal/review governance.

Status: **code complete; runtime validation deferred**.


### Separate reference-context retrieval

Implemented in code:
- Ask can attach up to three completed Class-A analyses as optional
  REFERENCE_CONTEXT;
- selected reference analyses are validated as completed Class A;
- primary case evidence and reference passages use separate retrieval;
- reference context uses MAIRA deterministic lexical retrieval;
- independent reference retrieval snapshot and passage IDs are persisted;
- model prompt labels every passage as SOURCE_EVIDENCE or REFERENCE_CONTEXT;
- response contract returns separate passage-ID arrays per layer;
- case and reference citations/page locations are persisted separately;
- App displays case evidence and reference context as separate citation blocks;
- PDF viewer resolves sources across the primary analysis and reference
  analyses;
- notebook 38 validates cross-layer provenance and prevents layer leakage;
- retention cleanup scrubs layer-specific citation/provenance content.

Status: **code complete; runtime validation deferred**.


### Dedicated reference-context corpus

Implemented in code:
- added notebook `44_index_reference_context.py`;
- dedicated source root:
  `/Volumes/bdw_analysis_prod/kg_poc/reference_context`;
- governed Delta tables:
  `reference_document` and `reference_passage`;
- compact `ReferenceDocument` metadata mirrored to Neo4j;
- source layer is explicitly `REFERENCE_CONTEXT`;
- SHIELD remains outside this corpus;
- Ask exposes an optional reference-context control;
- MAIRA deterministic free-text retrieval is reused for reference passages;
- source-evidence and reference-context retrieval snapshots are independent;
- model prompt and output contract preserve source-layer boundaries;
- App renders case citations and reference citations separately;
- reference PDF pages use the same user-authorised viewer path;
- old completed-Class-A-analysis reference mechanism was removed so there is
  only one reference-context architecture;
- notebook 38 now validates the dedicated corpus boundary.

Status: **code complete; runtime validation deferred**.


### Class-D deterministic fail-closed pre-screen

Implemented in source:

- canonical reusable detector:
  `src/ikf/classification_prescreen.py`;
- synthetic unit tests:
  `tests/test_classification_prescreen.py`;
- early App preflight for non-D direct text and IKF document metadata;
- backend content preflight in notebook 15 before passage persistence/model use;
- published MAIRA Class-B reports are explicitly exempt from escalation merely
  because the published report discusses protected evidence types;
- strong indicators require Class D for non-D raw/IKF-managed material;
- blocked direct-text encrypted payload is purged immediately;
- blocked backend analyses persist zero passages and must have zero ModelRuns;
- declared Class D is never downgraded;
- backend stores rule version/status/rule IDs/required class without matched
  protected text;
- App-blocked attempts now persist compact privacy-safe
  `ClassificationPrescreenAttempt` audit metadata;
- App Technical details exposes backend pre-screen status/version/rule IDs;
- generic public email alone does not trigger Class D; the test suite now
  matches that governed rule;
- notebook 43 validates fail-closed routing and App audit privacy constraints.

Status: **code complete; runtime validation deferred**.


### SHIELD two-gate classification workflow

Implemented in source:

- generic source indexer excludes reserved `SHIELD/` from ordinary
  SourceDocument catalogue/retention;
- previously indexed SHIELD SourceDocument metadata is migrated to
  `RESERVED_TAXONOMY` / `IKF_SHIELD` with persistent exemption;
- notebook 45 indexes persistent `shield_document` / `shield_passage`;
- corpus snapshot is deterministic from source-file SHA-256 values;
- notebook 46 generates proposals only for factors whose latest Gate-1
  RelationshipReview confirms `CONTRIBUTED_TO`;
- MAIRA deterministic free-text retrieval is reused over SHIELD passages;
- assistant label/code must occur in cited SHIELD source text;
- ungrounded output becomes `NO_GROUNDED_PROPOSAL`;
- ShieldProposal preserves Gate-1 review, factor, target, model, retrieval and
  corpus-snapshot provenance;
- stale proposals are blocked when Gate 1 receives a newer human review;
- notebook 47 defines the one-task SHIELD proposal Job;
- App resource is `SHIELD_PROPOSAL_JOB_ID <- shield_proposal_job`;
- Review & Validate exposes grounded SHIELD source pages and Gate-2
  VALIDATED / REJECTED / AMENDED review;
- every Gate-2 action creates append-only `ShieldReview`;
- proposal/KGNode are never overwritten;
- notebook 48 validates both human gates, grounding and provenance;
- transient SHIELD proposal rationale/evidence follows analysis retention;
- persistent SHIELD source corpus and compact human-review governance remain.

Status: **code complete; runtime validation deferred**.


### Findings Knowledge assistant and relationship correction

Implemented in source:

- enabled whole-case cited questions in Findings & Knowledge;
- reuses the existing QuestionRun + Ask Job rather than creating another model
  pipeline;
- QuestionRuns record `interaction_surface = KNOWLEDGE`;
- optional REFERENCE_CONTEXT remains a separately retrieved source layer;
- Class-D questions preserve the existing dedicated-model policy;
- relationship selector exposes candidate vs latest human-review status;
- notebooks 49/50 provide evidence-bounded relationship correction proposals;
- App exposes proposal generation and human APPROVED / DISMISSED /
  APPLIED_WITH_AMENDMENT decisions;
- approved/amended assistant proposals create a new append-only
  RelationshipReview;
- graph edges are never overwritten by the correction workflow;
- stale proposals are blocked when a newer human RelationshipReview exists;
- notebook 51 validates the proposal → human correction review →
  authoritative RelationshipReview chain;
- relationship-correction rationale/evidence follows analysis retention and is
  scrubbed by notebook 23.

Status: **code complete; runtime validation deferred**.


### Deterministic similar MAIRA cases

Implemented in source:

- notebook 52 derives similarity focus from processed Event /
  ContributingFactor / Finding / SafetyIssue / System graph labels;
- Vessel / Actor / Claim identity labels are excluded;
- MAIRA MAIN_REPORT passages are searched with
  `DETERMINISTIC_FREE_TEXT_LEXICAL_V0.1`;
- the current MAIRA package is excluded;
- candidate passages are aggregated to report-package candidates;
- top candidates preserve rank, matched terms, evidence passage IDs,
  report/page references, page locations and a deterministic retrieval
  snapshot;
- no LLM, embedding or vector similarity model is used;
- notebook 53 defines the one-task Similar MAIRA Cases Job;
- App resource is `SIMILAR_CASES_JOB_ID <- similar_cases_job`;
- Findings & Knowledge displays "why this matched" and can render the cited
  MAIRA page directly;
- notebook 54 validates current-package exclusion and passage/page provenance;
- transient similar-case matched evidence follows analysis retention cleanup.

Status: **code complete; runtime validation deferred**.


### Consolidated release preflight

Implemented in source:

- notebook `55_validate_consolidated_release_preflight.py`;
- no LLM/model calls and no Job triggers;
- checks required Lakeflow Job names;
- checks App resource keys and effective user scopes `files` / `sql`;
- checks core MAIRA / IKF Delta tables;
- reports REFERENCE_CONTEXT / SHIELD indexing readiness;
- checks governed source roots;
- checks Neo4j connectivity;
- verifies REFERENCE_CONTEXT is not mixed into ordinary SourceDocument;
- verifies SHIELD is not exposed as an ordinary AVAILABLE document;
- added `docs/26_consolidated_runtime_validation.md` as the one-shot
  deployment/validation checklist.

Status: **code/documentation complete; execution pending**.


### Authoritative REFERENCE_CONTEXT runtime validation — PASS

Validated in Databricks on 2026-09-22:

- registry version: `IKF_REFERENCE_SOURCE_REGISTRY_V0.1`;
- authoritative URL sources: **4**;
- manual governed sources: **0**;
- indexed documents: **4**;
- indexed passages: **81**;
- snapshot root:
  `/Volumes/bdw_analysis_prod/kg_poc/reference_context/_snapshots`;
- source layer: `REFERENCE_CONTEXT`;
- required marker observed:
  `PASS — IKF AUTHORITATIVE REFERENCE_CONTEXT CORPUS INDEXED`.

Initial governed sources are the current consolidated Directive 2009/18/EC,
Directive (EU) 2024/3017, IMO MSC.255(84), and IMO A.1075(28). Authoritative
URLs remain provenance while captured snapshots are used for deterministic,
page-level retrieval and rendering.

Status: **runtime validated**.


### Consolidated release preflight — runtime PASS

Validated in Databricks on 2026-09-22:

- warnings: **0**;
- errors: **0**;
- observed marker:
  `PASS — IKF CONSOLIDATED RELEASE PREFLIGHT`;
- all checked release prerequisites reported present.

Result: **PASS — environment/setup validation complete.**


### App information-architecture correction

Implemented in source on 2026-09-22 after the first post-preflight App deploy:

- backup branch created:
  `backup/pre-ux-separation-2026-09-22`;
- removed the Commodore Clipper demonstrator from the primary operational tab
  bar while retaining it as a project validation/reference asset;
- **Analyse Documents** now owns creation/status plus structured outputs:
  Events, Contributing Factors, Findings, Safety Issues, Safety Recommendations
  and analytical relationships with provenance;
- **Ask / Compare LLMs** is the sole operational free-text question surface;
- **Findings & Knowledge** is read-only evidence / graph / similar-case
  exploration;
- **Review & Validate** centralises direct human relationship review, optional
  assistant relationship correction, EMCIP review and SHIELD review;
- fixed the non-Class-D direct-text pre-screen UI branch value;
- pinned `streamlit[pdf]>=1.56.0,<2` because the searchable multiselect uses
  `filter_mode`, introduced in Streamlit 1.56;
- documented the separation in `docs/28_app_information_architecture.md`.

The observed Streamlit "form has no submit button" message followed a failure
while constructing the searchable multiselect before execution reached the
form-submit line; it is treated as a secondary symptom of the runtime/library
mismatch rather than as evidence that the source form lacked a submit button.

Status: **code/documentation complete; runtime validation pending redeploy**.


### Case-centric GUI refinement

Implemented in source on 2026-09-22:

- added one persistent **Active analysis** selector shared across Analyse,
  Findings, Ask and Review;
- added compact active-analysis header with class/source/status context;
- newly created analyses are handed off safely to the shared active context on
  the next rerun;
- Analyse Documents results now support category filtering and side-by-side
  description/evidence presentation;
- extracted items are visibly **AI identified / candidate** unless human
  validation has occurred;
- Contributing Factors show human-validated state only when the current
  relationship review confirms `CONTRIBUTED_TO`;
- Ask now uses explicit document-scope labels and a visible Question scope
  summary;
- normal model-route details are collapsed;
- global model-routing/Article-9 matrix is collapsed by default;
- Review & Validate is explicitly ordered as Relationship → EMCIP → SHIELD;
- technical relationship provenance is collapsed;
- backup branch created:
  `backup/pre-case-centric-gui-2026-09-22`.

Status: **code/documentation complete; runtime validation pending one
redeployment**.


### Pre-validation UI restoration and Knowledge Graph workspace

Implemented in source on 2026-09-22:

- restored the four processing stages in Analyse Documents:
  Prepare evidence → Analyse evidence → Check output → Build result;
- changed the four stages from vertical rows to horizontal cards;
- moved Refresh status before Recent analyses;
- collapsed Recent analyses so current structured results remain visible;
- removed the legacy processed-evidence/graph block from Ask / Compare;
- renamed Findings & Knowledge to **Findings & Evidence**;
- added a dedicated **Knowledge Graph** tab;
- graph workspace supports document scope, concept filters, relationship filters
  and multiple layouts;
- graph questions reuse the governed QuestionRun/Ask Job but are tagged
  `KNOWLEDGE_GRAPH`;
- normal Ask / Compare history is kept separate as `ASK_COMPARE`;
- diagram controls cannot mutate graph knowledge;
- relationship changes remain governed by Review & Validate;
- backup branch created:
  `backup/pre-graph-workspace-2026-09-22`.

Status: **code/documentation complete; runtime validation pending redeploy**.


### Analysis summary / evidence separation

Implemented in source on 2026-09-22:

- removed the Recent analyses list from Analyse Documents;
- the sidebar Active analysis selector is now the only analysis-switching
  control;
- renamed detailed Analysis results to **Analysis summary**;
- Analyse Documents now shows counts/structural metrics only;
- detailed extracted items and source-page evidence remain exclusively in
  **Findings & Evidence**;
- App build:
  `2026-09-22-summary-evidence-separation-v24`.

Status: **code/documentation complete; runtime validation pending redeploy**.


### Findings content index

Implemented in source on 2026-09-22:

- added a compact Findings & Evidence content index;
- first-class categories are Events, Contributing Factors, Findings,
  Safety Issues, Safety Recommendations and Analytical Relationships;
- category selection filters the detailed evidence sheet;
- structural graph links are excluded from Analytical Relationships;
- App build:
  `2026-09-22-findings-index-v25`.

Status: **code/documentation complete; runtime validation pending redeploy**.


### Simplified supporting evidence viewer

Implemented in source on 2026-09-22:

- Findings & Evidence now uses
  Description → Supporting evidence → Source page;
- one evidence location renders directly with no selector;
- multiple evidence locations use a Supporting evidence selector;
- PDF rendering is driven by structured document/page evidence locations;
- passage IDs and raw provenance are hidden under Technical details;
- source-reference-only legacy items are handled explicitly;
- backup branch:
  `backup/pre-evidence-viewer-simplification-2026-09-22`;
- App build:
  `2026-09-22-evidence-viewer-v26`.

Status: **code/documentation complete; runtime validation pending redeploy**.


### Evidence viewer and asynchronous follow-up

Implemented in source on 2026-09-22:

- simplified Findings & Evidence to
  Description → Supporting evidence → Source page/PDF;
- one evidence location renders directly; multiple locations use one
  Supporting evidence selector;
- technical passage/location/reference data moved under
  **Technical provenance (advanced)**;
- added reusable Databricks async-run status rendering;
- added Similar MAIRA Cases refresh/status follow-up;
- added relationship-correction refresh/status follow-up;
- added Knowledge Graph question refresh/status follow-up;
- clarified queued-message follow-up for normal Ask, EMCIP and SHIELD;
- preserved immediate rerun behavior for synchronous human review saves;
- backup branch:
  `backup/pre-action-followup-2026-09-22`;
- App build:
  `2026-09-22-evidence-and-action-followup-v26`.

Status: **code/documentation complete; runtime validation pending redeploy**.
