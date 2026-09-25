# Similarity, News and Class-D Ask refinement

Date: 2026-09-25

## Objective

This update simplifies the investigator workflow, improves explainability of related-case and news retrieval, and applies symmetric daily Ask guardrails to the two dedicated Class-D model routes without adding new model infrastructure.

## Analyse Documents

The duplicate `Analysis summary` block is removed from **Analyse Documents**. Analyse Documents remains focused on creating an analysis and following processing status. The brief analytical summary remains available in **Findings & Evidence**, which is the single read-only location for analysis outputs and evidence inspection.

## Similar MAIRA cases — deterministic V0.2

`notebooks/52_find_similar_maira_cases.py` remains the Similar Cases execution notebook and the existing Similar Cases Lakeflow Job continues to call the same notebook path.

The search scope is the processed MAIRA corpus where:

- `corpus_type = INVESTIGATION`
- `document_role = MAIN_REPORT`
- a canonical MAIRA passage exists.

The current case's MAIRA report package is excluded. A report merely downloaded into MAIRA storage is not query-ready until it is registered and has canonical passages. Annexes and other supporting documents remain outside this current retrieval scope.

V0.2 preserves MAIRA deterministic free-text lexical retrieval as the first-stage candidate method. It then ranks candidate report packages using weighted graph concepts:

| Concept type | Weight |
| --- | ---: |
| ContributingFactor | 5 |
| SafetyIssue | 4 |
| Event | 3 |
| Finding | 2 |
| System | 1 |

Whole multi-word concept matches receive an additional deterministic boost. Vessel, Actor and Claim identity are not used for similarity ranking.

The persisted SimilarCaseRun now records:

- registered MAIRA MAIN_REPORT count;
- query-ready MAIRA MAIN_REPORT count;
- processing-gap count;
- retrieval version and snapshot.

Each candidate additionally records matched weighted concepts and its deterministic weighted score. The App shows the actual MAIRA query-ready coverage and retains exact matched pages/passages for provenance.

No LLM, embedding endpoint or vector service is invoked by Similar Cases V0.2. Semantic reranking remains a possible future second-stage experiment and should be benchmarked before adoption.

The current PoC still fails closed above 5,000 candidate passages or 30 million corpus characters. If MAIRA grows beyond that bound, the next scaling step is distributed/indexed retrieval rather than silently reducing corpus coverage.

## News & Alerts

News remains external, unvalidated intelligence and never becomes investigation evidence automatically.

The App continues to query the governed SIANA EU/EEA alerts view through the Databricks SQL warehouse. This update adds investigator-facing filters for:

- country;
- date range;
- event type;
- vessel type;
- match reason;
- free-text alert search.

The former headline-derived `severity` display is labelled **Triage signal**. It is explicitly a screening heuristic and not an official casualty/severity classification.

Fatal-incident KPIs use unique `alert_id` values so an alert expanded across Flag/Location/Crew country rows is not counted more than once.

When an active analysis exists, **Related to active analysis only** applies deterministic lexical relevance using existing Event, ContributingFactor, SafetyIssue, Finding and System labels. This is a screening aid only. It makes no extra LLM call and does not assert a factual relationship between the news alert and the investigation.

## Class-D Ask guardrails

The former implementation had only a Llama 3.3 70B daily limit (default 5). GPT-OSS 20B had no comparable counter. This was a PoC operational/cost-control asymmetry, not a demonstrated technical capacity difference between the endpoints.

The new per-user, per-day Ask allowances are:

- **GPT-OSS 20B: 30 questions**
- **Llama 3.3 70B: 10 questions**

The quota date uses `Europe/Lisbon`, consistent with the existing implementation.

Important scope rule: these limits apply to **Ask LLMs questions only**. Creating/running an analysis does not consume the Ask allowance.

For `Both models`, one allowance from each model is reserved in one Neo4j write transaction before the Ask Job is queued. This avoids consuming one model allowance and then failing because the second model is already at its limit.

The UI displays the remaining daily allowance for every selected Class-D model.

These values are operational guardrails, not statements about model quality, endpoint throughput, contractual quotas or exact cost equivalence. They can be changed later through App configuration after usage and Databricks billing evidence are reviewed.

## Cost and performance impact

This update does not create or deploy a new model endpoint and does not add an automatic model call.

- Similar Cases remains deterministic and lexical.
- News active-case relevance is local lexical screening over already fetched alerts.
- Analysis runs no longer consume the Ask quota.
- Existing Class-D endpoints remain unchanged.

The next optional intelligence improvement is semantic reranking of only a small lexical Similar Cases shortlist. It should remain off until a benchmark shows a useful quality gain relative to added cost and complexity.

## Status

Done:

- Analyse Documents duplicate summary removed.
- GPT-OSS 20B Ask allowance set to 30/day.
- Llama 3.3 70B Ask allowance set to 10/day.
- Both-model allowance reservation made atomic.
- Similar Cases weighted deterministic V0.2 implemented.
- MAIRA query-ready coverage persisted and exposed in the App.
- News triage semantics, unique fatal count, filters and active-case lexical relevance implemented.

Pending / future:

- benchmark optional semantic reranking before adding any embedding/model service;
- move Similar Cases retrieval to a distributed/indexed implementation when MAIRA corpus size approaches the current PoC bound;
- use Databricks billing/system tables to revisit the 30/10 operational allowances from measured consumption rather than assumptions.
