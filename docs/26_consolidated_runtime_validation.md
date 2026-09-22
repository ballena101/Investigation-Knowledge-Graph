# IKF consolidated runtime validation plan

_Last updated: 2026-09-22_

This plan is the single operational checklist for the next paid Databricks
validation session.

The purpose is to validate the accumulated source changes together rather than
redeploying for every individual feature.

## 1. Before deploying the App

Pull the current `main` branch in both Git-backed workspace repositories:

- Investigation-Knowledge-Graph;
- MAIRA.

Run notebook:

`55_validate_consolidated_release_preflight.py`

This notebook is read-only and does not call an LLM.

It verifies:

- required Lakeflow Jobs;
- required Databricks App resources;
- Apps user API scopes `files` and `sql`;
- required MAIRA and IKF Delta tables;
- governed source roots;
- Neo4j connectivity;
- REFERENCE_CONTEXT / SHIELD source-layer separation.

Required marker:

`PASS — IKF CONSOLIDATED RELEASE PREFLIGHT`

Warnings for not-yet-indexed REFERENCE_CONTEXT or SHIELD tables should be
resolved by the indexing steps below before testing those capabilities.

## 2. Job/resource setup

Create or update the Git-backed Jobs where required:

- notebook 17 — Automated Analysis;
- notebook 19 — Class D Dual Model;
- notebook 37 — Ask Processed Evidence;
- notebook 41 — Propose EMCIP Mappings;
- notebook 47 — SHIELD Proposals;
- notebook 50 — Relationship Correction;
- notebook 53 — Similar MAIRA Cases.

Expected App Job resource keys:

- `analysis_job`;
- `class_d_analysis_job`;
- `ask_job`;
- `emcip_mapping_job`;
- `shield_proposal_job`;
- `relationship_correction_job`;
- `similar_cases_job`.

Use `Can manage run`.

Do not remove the existing secret resources when attaching Jobs.

## 3. Governed corpus setup

### REFERENCE_CONTEXT

Place governed legal / IMO / technical reference documents under:

`/Volumes/bdw_analysis_prod/kg_poc/reference_context`

Run notebook 44.

Verify the dedicated tables:

- `bdw_analysis_prod.kg_poc.reference_document`;
- `bdw_analysis_prod.kg_poc.reference_passage`.

### SHIELD

Keep the persistent SHIELD source documents under:

`/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/SHIELD`

Run notebook 45.

Required marker:

`PASS — PERSISTENT SHIELD CORPUS INDEXED`

SHIELD must remain excluded from the normal SourceDocument catalogue.

## 4. Deploy once

Redeploy the App only after the resource/corpus setup above.

Expected source build includes:

- classification-scoped document catalogues;
- searchable selectors;
- question-independent analysis;
- Ask / Compare;
- Findings & Knowledge assistant;
- evidence/page viewer;
- relationship review;
- EMCIP review;
- SHIELD two-gate review;
- relationship correction proposals;
- deterministic Similar MAIRA Cases.

## 5. Core Class-B MAIRA run

Create one fresh Class-B analysis from a MAIRA MAIN_REPORT.

Verify:

- Prepare evidence completes;
- evidence source reports MAIRA canonical passages;
- report/page references are visible;
- cited source page renders.

Run notebook 32.

Required marker:

`PASS — NORMAL APP ANALYSIS PRESERVES MAIRA_IKF_PASSAGE_V0.1`

Run notebook 35.

Required marker:

`PASS — SOURCE VIEWER METADATA AND PAGE RANGES ARE VALID`

## 6. Ask / knowledge assistant

Ask:

- one whole-case ordinary free-text question;
- one document-scoped question;
- one Findings & Knowledge question.

Verify:

- QuestionRun is separate from AnalysisGroup construction;
- no graph rebuild occurs;
- case and reference citations stay separated;
- source page can be opened.

Run notebook 38 for representative QuestionRuns.

Required marker:

`PASS — SCOPED ASK / COMPARE RUN IS EVIDENCE-BOUNDED`

Also validate one exact persisted MAIRA governed query and confirm the retrieval
mode identifies governed MAIRA relationship evidence.

## 7. Human relationship and EMCIP review

Validate/reject/amend one generic relationship.

Run notebook 39 where applicable.

Generate generic EMCIP proposals through notebook 41's Job, review one proposal
in the App, then run notebook 42.

The LLM proposal must remain separate from the human review.

## 8. Class-D pre-screen

Run the notebook 43 validation cases.

Confirm:

- obvious protected inputs fail closed when declared non-D;
- blocked raw direct text is purged;
- zero analysis passages/model runs are produced for a blocked backend case;
- Class D is never downgraded.

## 9. SHIELD two-gate workflow

Human-validate one ContributingFactor — CONTRIBUTED_TO relationship.

Generate SHIELD proposals.

Verify:
- Gate 1 is a human relationship review;
- assistant proposal is grounded in SHIELD source passages;
- Gate 2 requires a separate human decision;
- only Gate-2 validated/amended classification is authoritative.

Run notebook 48.

Required marker:

`PASS — SHIELD PROPOSALS REQUIRE GATE 1 AND AUTHORITATIVE CLASSIFICATION REQUIRES GATE 2`

## 10. Relationship correction

From Findings & Knowledge:

1. select one evidence-derived relationship;
2. generate a correction proposal;
3. inspect action/rationale/evidence;
4. approve, dismiss or apply a different human outcome.

Run notebook 51.

Required marker:

`PASS — RELATIONSHIP CORRECTION REMAINS HUMAN-GOVERNED`

Confirm the Neo4j graph edge itself was not overwritten.

## 11. Similar MAIRA cases

Run Similar MAIRA Cases for the same analysis.

Verify:

- current report/package is absent;
- matched terms are visible;
- report/page evidence is visible;
- cited MAIRA page opens;
- no AI similarity percentage is presented.

Run notebook 54.

Required marker:

`PASS — SIMILAR MAIRA CASES ARE DETERMINISTIC AND TRACEABLE`

## 12. Retention

Run the retention validation/cleanup checks against a controlled expired test
analysis.

Confirm transient content is scrubbed for:

- passages/candidates/summary;
- QuestionRun/QuestionModelRun answer content;
- SHIELD proposal rationale/evidence;
- relationship-correction rationale/evidence;
- similar-case matched-term/evidence details.

Compact audit/human-review governance should remain where designed.

## 13. Completion rule

The current PoC capability set is runtime-validated only after:

- notebook 55 passes;
- feature-specific validators pass;
- App source-page rendering is confirmed;
- human-review gates behave as documented;
- no source-layer boundary is silently collapsed;
- GitHub documentation is updated with the observed runtime results.

News/dashboard integration is deliberately excluded from this checklist and
remains in its separate workstream.


## Runtime record — REFERENCE_CONTEXT

Validated on 2026-09-22:

- registry version: `IKF_REFERENCE_SOURCE_REGISTRY_V0.1`;
- 4 authoritative URL sources;
- 0 manual governed sources;
- 4 indexed reference documents;
- 81 indexed passages;
- snapshot root:
  `/Volumes/bdw_analysis_prod/kg_poc/reference_context/_snapshots`;
- source layer: `REFERENCE_CONTEXT`;
- observed marker:
  `PASS — IKF AUTHORITATIVE REFERENCE_CONTEXT CORPUS INDEXED`.

Result: **PASS**.
