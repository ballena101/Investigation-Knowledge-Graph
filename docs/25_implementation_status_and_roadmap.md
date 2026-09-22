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

### Development — Class-D completion

Complete the automatic information-class pre-screen and fail-closed routing for
protected investigation material.

Required principles:

- investigator-declared A/B/C/D remains visible and auditable;
- automatic screening is a safeguard, not a silent reclassification engine;
- obvious protected indicators can escalate/reroute but must not downgrade D;
- ambiguous material fails closed toward the more protected path;
- witness statements, identities, medical/personal data, investigator drafts,
  VTS/VDR and equivalent protected evidence remain Class-D indicators;
- raw protected production content must not become a general Neo4j evidence
  store;
- dedicated Class-D model routes remain mandatory;
- rule version and trigger reason must be logged deterministically.

### Consolidated runtime validation

The accumulated App/Job changes remain intentionally undeployed to avoid
repeated Databricks cost.

Next validation session:

1. Pull current IKF `main` and MAIRA `main`.
2. Populate:
   `/Volumes/bdw_analysis_prod/kg_poc/reference_context`
   with the governed legal/IMO/technical reference files.
3. Run notebook 44 and require:
   `PASS — IKF REFERENCE_CONTEXT CORPUS INDEXED`.
4. Run notebook 37 to create/update the Ask Job.
5. Attach App Job resource:
   - key: `ask_job`;
   - permission: `Can manage run`.
6. Run notebook 41 to create/update the EMCIP mapping Job.
7. Attach:
   - key: `emcip_mapping_job`;
   - permission: `Can manage run`.
8. Redeploy the App once.
9. Create/retry one Class-B MAIRA MAIN_REPORT analysis.
10. Require notebook 32:
    `PASS — NORMAL APP ANALYSIS PRESERVES MAIRA_IKF_PASSAGE_V0.1`.
11. Require notebook 35:
    `PASS — SOURCE VIEWER METADATA AND PAGE RANGES ARE VALID`.
12. Confirm visible report/page citations and cited PDF rendering.
13. Run one ordinary Ask question and one document-scoped Ask question.
14. Run one Ask question with REFERENCE_CONTEXT enabled.
15. Require notebook 38:
    `PASS — SCOPED ASK / COMPARE PRESERVES SOURCE_EVIDENCE AND REFERENCE_CONTEXT BOUNDARIES`.
16. Test one exact persisted MAIRA governed query and confirm:
    `GOVERNED_RELATIONSHIP_EVIDENCE`.
17. Test one large ordinary free-text scope and confirm:
    `DETERMINISTIC_FREE_TEXT_LEXICAL_V0.1`.
18. Save at least one generic relationship review and require notebook 39:
    `PASS — GENERIC RELATIONSHIP REVIEWS PRESERVE ANALYSIS AND MODEL PROVENANCE`.
19. Generate generic EMCIP proposals from Review & Validate.
20. Save at least one mapping review and require notebook 42:
    `PASS — GENERIC EMCIP PROPOSALS AND REVIEWS REMAIN GOVERNED`.

No question, reference retrieval, relationship review or EMCIP mapping review
should rebuild the case graph.

## 4. PENDING — planned implementation sequence

### P1 — Class-D completion

- Automated A/B/C/D pre-screen with fail-closed routing.
- Complete protected-data controls and assurance.
- Keep production protected raw content outside Neo4j.
- Preserve dual-model comparison and privacy validation.

### P2 — SHIELD workflow

- Candidate contributing factor
  → human validation
  → LLM SHIELD suggestion
  → independent human SHIELD validation.
- Only validated SHIELD classification becomes authoritative.

### P3 — knowledge assistant and relationship correction

- Ask/Research over processed knowledge with citations.
- Distinguish candidate from human-validated knowledge.
- Allow LLM to propose relationship corrections from the graph.
- Never change validated graph relationships without explicit human approval.

### P4 — similar cases and external signals

- Retrieve similar MAIRA investigation reports.
- Keep News & Alerts separate as external/unvalidated information.
- Later allow governed read-only LLM access to the news backend without mixing
  news with validated investigation findings.

### P5 — production-readiness validation

- Reproducible benchmarks.
- Versioned prompts/models/retrieval snapshots.
- Precision/recall against canonical semantic gold.
- Privacy and quotation/contract compliance measured separately.
- Permissions, retention, logging and rollback checks.

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
