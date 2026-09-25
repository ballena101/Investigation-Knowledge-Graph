# Search, News and Class-D Ask refinement

Date: 2026-09-25

## Purpose

This update removes duplicate analysis output from **Analyse Documents**, clarifies the current **Similar MAIRA Cases** search boundary, improves the **News & Alerts** screening workflow, and makes Class-D free-text question allowances explicit and independent by model.

## Analyse Documents

The Analyse Documents page is for defining/running an analysis and following processing status. The duplicate `Analysis summary` block and graph-count KPIs are removed from this page.

The brief analysis summary and analytical content index remain in **Findings & Evidence**, which is the single read-only place for analysis outputs and evidence inspection.

## Similar MAIRA Cases — current retrieval

The existing retrieval remains deliberately deterministic and low-cost.

For a completed analysis, notebook `52_find_similar_maira_cases.py` derives up to 20 focus concepts from the analysis graph using these node kinds:

- `ContributingFactor`
- `Event`
- `SafetyIssue`
- `Finding`
- `System`

Vessel, Actor and Claim identities are excluded. The current MAIRA report package is excluded from candidates.

The searchable corpus is the canonical MAIRA Delta corpus restricted to:

- `corpus_type = INVESTIGATION`
- `document_role = MAIN_REPORT`
- documents with canonical rows in `bdw_analysis_prod.maira.passages`

Therefore the search is not limited to reports already used in IKF analyses. It searches all processed/query-ready MAIRA main investigation reports within the current bounded PoC retrieval implementation.

The App now states this scope explicitly. Page-level provenance and matched terms remain visible.

The Similar MAIRA Cases panel checks the Databricks Job state and reloads
stored candidates only when **Refresh similar-case status** is selected. A
failed run is labelled as notebook 52 failure with the Databricks run ID, so
the notebook output can identify the cause. This avoids a Job API call and
candidate query on every Streamlit refresh. Notebook 53 creates or resets the
Job; the App resource key is `similar_cases_job` with **Can manage run**.

### Semantic reranking — deliberately not added in this update

A second-stage semantic reranker could improve recall and concept-level similarity, but it requires a selected and benchmarked embedding/semantic model plus a governed endpoint/cost decision. It is therefore kept as a separate future enhancement rather than being added silently to the current PoC.

Recommended future architecture:

1. deterministic full-corpus MAIRA lexical retrieval;
2. shortlist candidate report packages;
3. semantic reranking only over the shortlist;
4. retain canonical MAIRA passages/pages as the evidence shown to the investigator.

## News & Alerts

The News view continues to query the SIANA EU/EEA alert hierarchy through the configured Databricks SQL warehouse. It remains external intelligence and never becomes investigation evidence automatically.

The live News & Alerts table, map and filters were restored from the latest
shared App source after a repository update had left only the dashboard link.
The warehouse query now runs when the user selects **Load / refresh news
alerts**. Its results stay in that user's App session, so unrelated Streamlit
tab refreshes do not repeatedly start SQL queries. The dashboard link remains
available when warehouse access is not configured.

This update adds:

- event-type filter;
- vessel-type filter;
- match-reason filter;
- free-text alert search;
- optional `Related to active analysis only` lexical screening using the active analysis graph concepts;
- unique-alert counting for the fatal-alert KPI;
- safer triage terminology.

### Related alerts for a selected analysis

In Findings & Evidence → Similar cases, **Find related news alerts** runs an
on-demand seven-day SIANA alert query and screens headlines against up to 20
Event, ContributingFactor, SafetyIssue, Finding and System labels in the
selected completed analysis graph. Results show alert text, update time and
matched concepts, deduplicated by alert ID and bounded to 20. The panel
explicitly says when no related alerts are identified. This is lexical
screening of external, unverified news; it does not create a persistent
investigation-to-alert relationship or promote news to case evidence.

Live warehouse permissions, query output and App deployment still require
runtime validation in Databricks.

### Triage terminology

Headline-derived severity-like labels are now presented as **triage signals**, not as an official casualty severity classification. They are screening heuristics based on alert text and must not be interpreted as an IMO/Directive/EMCIP legal classification.

### Active-analysis relevance

The optional active-analysis filter uses existing Event, ContributingFactor, SafetyIssue, Finding and System labels from the active graph. It performs deterministic lexical matching against alert text and makes no extra LLM call.

A positive match is only a relevance cue. It does not establish that an alert is factually connected to the investigation.

## Class-D Ask allowances

The previous App implementation applied a daily counter only to Llama 3.3 70B and also consumed that counter when a Class-D analysis was started. This mixed two different activities.

The revised policy is specifically for **Ask LLMs free-text questions**:

- GPT-OSS 20B: **30 questions per user per day**;
- Llama 3.3 70B: **10 questions per user per day**;
- choosing `Both models` reserves one allowance from each model;
- Class-D analysis creation/execution does **not** consume the Ask-question allowance.

Both limits are environment-configurable:

- `GPT20_DAILY_QUESTION_LIMIT=30`
- `LLAMA_DAILY_QUESTION_LIMIT=10`

Usage remains persisted per user/model/day in Neo4j `ModelDailyUsage`. For `Both models`, the reservation is performed inside one Neo4j write transaction so the two allowances are reserved together.

These numbers are PoC governance/cost controls, not model technical limits.

## Cost impact

This update does not introduce a new model endpoint, embedding service or recurring job.

- Similar Cases remains deterministic lexical retrieval.
- News active-case relevance is deterministic in-App text matching.
- No additional LLM call is made for News relevance.
- Question allowances only control permitted calls to already configured Class-D endpoints.

## Done / pending

### Done

- Analyse Documents duplicate summary removed.
- Findings & Evidence retained as the single analysis-output summary surface.
- Similar Cases corpus scope clarified.
- News filters and active-analysis lexical relevance added.
- Findings & Evidence related-alert panel added on demand.
- News severity-like output relabelled as triage signal.
- Fatal-alert KPI deduplicated by `alert_id`.
- GPT-OSS 20B Ask allowance set to 30/day.
- Llama 3.3 70B Ask allowance set to 10/day.
- Analysis runs separated from Ask quota consumption.
- Atomic reservation added for `Both models`.

### Pending / future benchmark

- Evaluate a semantic/embedding reranker for the Similar Cases shortlist.
- Add an explicit live MAIRA `query-ready / registered main reports` coverage KPI after deciding whether that check should be computed on demand or persisted by the MAIRA catalogue-sync process.

## MAIRA PDF visibility reconciliation

Run `notebooks/55_reconcile_maira_pdf_and_ikf_catalogue.py` in the IKF
Databricks Git folder for a read-only comparison of MAIRA Volume PDFs,
`maira.documents`, `maira.passages`, and IKF Neo4j `SourceDocument` entries.
It prints exact missing paths/IDs and distinguishes registered main reports
with passages from annexes and unprocessed PDFs. If registered document IDs
are absent in IKF, run notebook 33 to sync the catalogue and refresh the App;
notebook 37 validates query-ready main reports. The GitHub repository does
not contain MAIRA source PDFs by design.
