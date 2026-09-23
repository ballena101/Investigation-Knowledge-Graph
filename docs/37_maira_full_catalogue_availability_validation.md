# MAIRA full-catalogue availability validation

Date added: 2026-09-23

## Objective

Verify, at negligible compute cost and without any LLM call or application deployment, whether every investigation main report currently registered and processed by MAIRA is available to IKF through the canonical MAIRA-backed query path.

## Architectural boundary

MAIRA remains responsible for acquisition, source provenance, parsing and canonical passage construction. IKF consumes MAIRA passages and adds analysis/model/review context. IKF must not independently re-download or re-chunk investigation reports that already exist in MAIRA.

The current IKF query runner reads `bdw_analysis_prod.maira.passages`, joins `bdw_analysis_prod.maira.documents`, and restricts governed accident-analysis queries to documents where:

- `corpus_type = INVESTIGATION`
- `document_role = MAIN_REPORT`

Accordingly, a MAIRA main report is considered available to the current IKF query path only when it has at least one canonical MAIRA passage.

## Validation notebook

`notebooks/37_validate_maira_full_catalogue_availability.py`

The notebook is read-only. It:

1. reads `bdw_analysis_prod.maira.documents` and `bdw_analysis_prod.maira.passages`;
2. counts passages per investigation document;
3. reports all registered `MAIN_REPORT` documents;
4. identifies main reports with zero passages as processing gaps;
5. separately audits annexes, appendices and other supporting documents;
6. fails closed if any registered main report has no canonical passage;
7. emits `PASS` only when every registered MAIRA investigation main report is query-ready in IKF.

## Cost and side effects

The validation performs Spark reads and aggregations only. It does not:

- call an LLM endpoint;
- deploy or restart the Databricks app;
- write Delta tables;
- write to Neo4j;
- download source documents;
- modify MAIRA data.

## Important scope distinction

A document being downloaded by MAIRA does not by itself prove that IKF can use it. The source file must also be registered and have canonical MAIRA passages. The validation therefore checks the processed catalogue exposed through MAIRA tables, not merely files present in a Volume.

Supplementary files are reported separately because the current IKF query runner intentionally scopes governed queries to `MAIN_REPORT`. Their exclusion is an explicit current implementation boundary, not evidence that MAIRA failed to acquire them.

## Acceptance criterion

`PASS` means: every `INVESTIGATION` + `MAIN_REPORT` currently registered in `bdw_analysis_prod.maira.documents` has one or more rows in `bdw_analysis_prod.maira.passages` and is therefore addressable by the current MAIRA-backed IKF query path.

A `FAIL` lists the exact MAIRA documents that still require passage construction or processing before they are available to IKF.
