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

### Build scoped free-text Ask / Compare backend

Implement the question runner for already processed evidence sets.

Required interaction:
1. choose one completed analysis/case;
2. choose evidence scope:
   - whole case;
   - one source document;
   - selected source documents;
3. enter a free-text question;
4. run the default model, or optionally compare models;
5. return a grounded answer with document + page/page-range citations;
6. preserve supporting passage IDs;
7. allow direct opening of the cited source page in the Evidence viewer;
8. keep question execution separate from the case graph construction.

The question runner must reuse the governed MAIRA evidence/retrieval stack where
applicable and must not introduce a second canonical passage/retrieval system.

### Consolidated runtime validation after Ask backend is ready

Validate repaired MAIRA document run

1. Pull current `main`.
2. Redeploy the App if App code changed since the active deployment.
3. Create/retry one Class-B analysis using a MAIRA MAIN_REPORT.
4. Confirm Prepare evidence completes.
5. Confirm Technical details shows `MAIRA canonical passages`.
6. Confirm the explicit answer has report/page references.
7. Confirm Evidence sheet opens the cited MAIRA PDF page.
8. Run notebook 32 against that analysis ID and require:
   `PASS — NORMAL APP ANALYSIS PRESERVES MAIRA_IKF_PASSAGE_V0.1`.
9. Run notebook 34 with the governed query used for the next retrieval test
   (Q003 is the current default) and require:
   `PASS — GOVERNED MAIRA RETRIEVAL DATA PREFLIGHT`.
10. Run notebook 35 and require:
    `PASS — SOURCE VIEWER METADATA AND PAGE RANGES ARE VALID`.
11. Confirm the App renders the cited source PDF page after the metadata PASS.

These validations are the gate before relying on governed question answering
and source-page rendering in the normal App workflow.

## 4. PENDING — planned implementation sequence

### P1 — scoped free-text Ask / Compare execution

- Persist each question as its own run, separate from the analysis/case.
- Scope to whole case, one document or selected documents.
- Single-model answer by default.
- Optional same-question/same-evidence model comparison.
- Always return document/page citations and passage provenance.
- Do not rebuild the graph merely because a new question is asked.

### P2 — governed MAIRA retrieval in question execution

- Reuse MAIRA governed query specifications and terminology where applicable.
- Reuse MAIRA deterministic retrieval/relationship modules rather than creating
  an IKF retrieval stack.
- Apply only human-validated terminology normalisations.
- Preserve deterministic retrieval snapshots for benchmarkable questions.
- Keep arbitrary free-text questions distinct from governed query-spec
  execution unless a traceable governed mapping exists.

### P3 — generic human relationship review

- Remove remaining Commodore-Clipper-specific assumptions.
- Review arbitrary analysis relationships.
- Preserve append-only human decisions.
- Add evidence-sheet/page-viewer access directly in review.

### P4 — generic EMCIP mapping review

- LLM proposes mapping only.
- Human validates/rejects/amends independently from relationship review.
- Consume MAIRA EMCIP registry; do not create another taxonomy.

### P5 — reference-context retrieval

- Add legal/methodological reference fragments separately from occurrence
  evidence.
- Preserve source layer labels:
  SOURCE_EVIDENCE / REFERENCE_CONTEXT / CONTROLLED_TAXONOMY.
- Reference context may guide interpretation but cannot prove an accident fact.

### P6 — Class-D completion

- Automated A/B/C/D pre-screen with fail-closed routing.
- Complete protected-data controls and assurance.
- Keep production protected raw content outside Neo4j.
- Preserve dual-model comparison and privacy validation.

### P7 — SHIELD workflow

- Candidate contributing factor
  → human validation
  → LLM SHIELD suggestion
  → independent human SHIELD validation.
- Only validated SHIELD classification becomes authoritative.

### P8 — knowledge assistant and relationship correction

- Ask/Research over processed knowledge with citations.
- Distinguish candidate from human-validated knowledge.
- Allow LLM to propose relationship corrections from the graph.
- Never change validated graph relationships without explicit human approval.

### P9 — similar cases and external signals

- Retrieve similar MAIRA investigation reports.
- Keep News & Alerts separate as external/unvalidated information.
- Later allow governed read-only LLM access to the news backend without mixing
  news with validated investigation findings.

### P10 — production-readiness validation

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
- scoped free-text question execution is the next backend slice.

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
