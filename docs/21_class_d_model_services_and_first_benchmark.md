# Class D model services and first dual-model benchmark

## Purpose

This document records the Databricks implementation milestone for the Class D
dual-model Proof of Concept. It complements:

- `docs/17_class_d_dual_model_poc.md`;
- `docs/18_model_validation_and_feedback.md`;
- `docs/19_current_poc_functional_specification.md`.

It records what has actually been configured and tested in the Databricks
workspace. It does not contain credentials, raw protected evidence or retained
model outputs from investigation material.

## 1. Implementation status

As of 21 September 2026, two Class D PoC model services have been created and
successfully connectivity-tested through Databricks Unity Gateway.

### Model A

- model: OpenAI GPT-OSS 20B;
- PoC service name: `ikf-gpt-oss-20b-poc`;
- model identifier used by the notebook:
  `bdw_analysis_prod.kg_poc.ikf-gpt-oss-20b-poc`;
- serving mode: Databricks Unity Gateway;
- capacity mode: pay-per-token.

### Model B

- model: Meta Llama 3.3 70B Instruct;
- PoC service name: `ikf-llama-3-3-70b-poc`;
- serving mode: Databricks Unity Gateway;
- capacity mode: pay-per-token.

The earlier design option of using an Ollama-hosted Llama service is not the
current PoC implementation. The current controlled comparison uses Databricks
model services for both Class D candidate models.

## 2. Authentication and secrets

The notebook uses a Databricks access token stored as a governed secret rather
than embedding credentials in notebook source.

Current secret location:

- catalog: `bdw_analysis_prod`;
- schema: `kg_poc`;
- secret name: `databricks_model_token`.

The secret value must never be committed to GitHub, printed in notebook output
or copied into project documentation.

The established notebook retrieval pattern is:

```python
DATABRICKS_TOKEN = dbutils.secrets.get(
    catalog="bdw_analysis_prod",
    schema="kg_poc",
    key="databricks_model_token"
)
```

The same governance pattern is already used for the Neo4j credentials.

## 3. Controlled dual-model test design

The first dual-model test used a deliberately simple synthetic evidence item in
order to verify the complete request path before using real investigation
material.

Frozen test input:

```text
SOURCE TEXT:
This is a test with an engine failure due to water ingress.

QUESTION:
Using only the source text above, identify the contributing factor.
Return only the contributing factor. Do not add assumptions or explanations.
```

Expected human reference:

```text
water ingress
```

Both models were called independently with the same source text and the same
question. Neither model received the other model's output.

Both returned the expected contributing factor.

This test demonstrates end-to-end connectivity and persistence only. It is not
evidence of general model accuracy.

## 4. Benchmark notebook configuration

The initial controlled notebook configuration uses:

```python
MODEL_A = "bdw_analysis_prod.kg_poc.ikf-gpt-oss-20b-poc"
MODEL_B = "bdw_analysis_prod.kg_poc.ikf-llama-3-3-70b-poc"

MAX_OUTPUT_TOKENS = 1200
BENCHMARK_ID = "ikf_benchmark_001"
```

The synthetic connectivity benchmark used a smaller output-token limit for the
actual requests because the expected response was a single factor.

The core experimental rule is:

```text
same frozen evidence
+ same frozen question
+ same prompt version
+ equivalent inference constraints
        |
        +--> Model A
        |
        +--> Model B
```

Only the model route changes.

## 5. Persisted benchmark table

The first benchmark record is persisted in the Unity Catalog Delta table:

`bdw_analysis_prod.kg_poc.ikf_model_benchmark_results`

Initial schema:

| Column | Type | Purpose |
|---|---|---|
| benchmark_id | STRING | Stable benchmark item identifier |
| source_text | STRING | Frozen evidence supplied to the models |
| question | STRING | Frozen benchmark question/instruction |
| expected_answer | STRING | Human reference where one exists |
| model_a | STRING | Model A identifier |
| model_a_answer | STRING | Raw/normalised Model A answer for this minimal test |
| model_b | STRING | Model B identifier |
| model_b_answer | STRING | Raw/normalised Model B answer for this minimal test |
| human_validation | STRING | Human validation state |
| created_at | TIMESTAMP | Record creation time |

For `ikf_benchmark_001`, the human-validation state was changed from
`pending` to `validated` after the reviewer confirmed that both outputs
matched the expected synthetic answer.

## 6. Planned schema extension before real benchmark cases

Before using real investigation evidence, the benchmark table should include at
least:

- `source_document_id`;
- `source_passage_id`;
- `prompt_version`;
- `model_a_max_output_tokens`;
- `model_b_max_output_tokens`;
- `reviewer_comment`.

The initial prompt version for contributing-factor extraction is intended to be:

`cf_extraction_v1`

Further extensions should preserve model-specific review decisions rather than
collapsing both answers into one overall result.

## 7. Validation principle

The first synthetic test closes the technical loop:

```text
source
  -> same question
  -> GPT-OSS 20B
  -> Llama 3.3 70B
  -> independent stored outputs
  -> human validation
```

The next stage is a real, controlled benchmark based on frozen investigation
passages and explicit human review.

Human feedback does not automatically train either model. It creates a
versioned validation/feedback dataset that may later be used deliberately for:

- evaluation;
- retrieval;
- few-shot examples;
- or, only after separate approval and design, model adaptation.

Validated prior knowledge must never be presented as evidence for a different
investigation unless its underlying source evidence is part of that
investigation.

## 8. Repository/data boundary

GitHub remains the authoritative location for code, methodology, architecture
and implementation history.

Databricks remains the execution and governed-data environment.

Do not commit to GitHub:

- access tokens or secrets;
- investigation source evidence;
- protected prompts containing source evidence;
- model outputs containing protected evidence;
- temporary benchmark artefacts containing confidential material.

The repository documents the method and schemas; governed investigation data
remain in Databricks.


## 9. Candidate-level human-feedback table

After benchmark 002, answer-level validation was found to be too coarse because a
single model response can contain multiple contributing-factor candidates with
different review outcomes.

The PoC therefore adds a candidate-level feedback table:

`bdw_analysis_prod.kg_poc.ikf_model_benchmark_candidates`

Recommended schema:

| Column | Type | Purpose |
|---|---|---|
| benchmark_id | STRING | Parent benchmark item |
| model_role | STRING | Model A or Model B |
| model_id | STRING | Exact model identifier |
| candidate_id | STRING | Stable candidate identifier within the benchmark/model |
| candidate_concept | STRING | Concise model-proposed concept |
| evidence_quote | STRING | Source wording cited by the model |
| review_decision | STRING | VALIDATED / REJECTED / AMENDED |
| amended_concept | STRING | Human-amended concept where applicable |
| reviewer_comment | STRING | Reason for the decision |
| prompt_version | STRING | Prompt version used |
| created_at | TIMESTAMP | Record creation timestamp |

This table is the preferred unit for model-quality metrics because it allows
mixed decisions within one response and preserves the original model proposal
without overwriting it.


## 10. Benchmark 002 descriptive candidate metrics

The first candidate-level metric query for `ikf_benchmark_002` produced:

| Model role | Total candidates | Validated % | Amended % | Rejected % |
|---|---:|---:|---:|---:|
| MODEL_A | 1 | 0.0 | 100.0 | 0.0 |
| MODEL_B | 3 | 0.0 | 66.7 | 33.3 |

These percentages describe this single benchmark item only. They must not be
reported as general model accuracy or comparative performance.

The next validation extension is to record the reason for rejection/amendment so
that errors can be analysed by failure mode rather than only by review outcome.


## 11. Candidate failure taxonomy introduced

Benchmark 002 now records a controlled failure type for each amended/rejected
candidate.

Current labels:

- `CAUSAL_OVERREACH` — a fact/event is supported, but the model promotes it to
  a contributing/causal role without sufficient support in the supplied
  evidence.
- `UNSUPPORTED_INFERENCE` — the model introduces a claim that is not stated or
  adequately supported by the supplied evidence.
- `OVER_GENERALISATION` — the model broadens or abstracts the source wording
  beyond what the evidence supports.

Benchmark 002 assignments:

| Model | Candidate | Review | Failure type |
|---|---|---|---|
| MODEL_A | Installation of a 250 kg/h nozzle to increase boiler capacity | AMENDED | CAUSAL_OVERREACH |
| MODEL_B | Lack of expertise | REJECTED | UNSUPPORTED_INFERENCE |
| MODEL_B | Lack of support from the manufacturer | AMENDED | CAUSAL_OVERREACH |
| MODEL_B | Modification of boiler settings | AMENDED | OVER_GENERALISATION |

These labels are descriptive validation categories, not model-quality rankings.


## 12. Benchmark 003 negative-control result

A synthetic negative-control benchmark was executed using a passage that
contained ordinary vessel/port events but no evidence supporting a contributing
factor.

Expected response:

`NO_SUPPORTED_CONTRIBUTING_FACTOR`

Observed result:

- MODEL_A / GPT-OSS 20B: `NO_SUPPORTED_CONTRIBUTING_FACTOR`;
- MODEL_B / Llama 3.3 70B: `NO_SUPPORTED_CONTRIBUTING_FACTOR`.

Both model outputs were therefore human-validated for this benchmark item.

This benchmark measures abstention/restraint rather than extraction ability. It
provides evidence that, under prompt version `cf_extraction_v1`, both model
routes can refrain from inventing a contributing factor on this specific
negative-control example. It does not establish a general false-positive rate.


## 13. Planned first validation round

The first PoC validation round targets 15 benchmark items. The purpose is
coverage of distinct behaviours, not statistical representativeness.

Planned coverage:

1. synthetic connectivity/extraction check — completed;
2. real contributing-factor extraction — completed;
3. negative-control abstention — completed;
4. chronology without causal support;
5. explicit causal relationship;
6. multiple contributing factors in one passage;
7. ambiguous/insufficient evidence requiring abstention;
8. supported factor expressed indirectly;
9. unsupported plausible-domain inference;
10. duplicate/overlapping factor candidates;
11. evidence-quote accuracy;
12. relationship-direction accuracy;
13. privacy/de-identification behaviour;
14. mixed supported and unsupported candidates in one passage;
15. repeated-run stability on a locked benchmark item.

Most items should use real investigation passages. Synthetic items are retained
only where they provide a clean control condition.

Results from this first 15-item round are descriptive PoC validation evidence
and must not be presented as a general model-performance estimate.


## 14. Benchmark 004 execution-control observation

Benchmark 004 tests chronology without causal support.

The initial GPT-OSS 20B run used `max_output_tokens=200` and returned no final
text because the response ended with:

`status = incomplete`

and:

`reason = max_output_tokens`.

This run is not scored as a semantic/model-quality failure. It is an execution
configuration event because the model exhausted its output budget during
reasoning before producing a final answer.

The benchmark must therefore be rerun for both models using the same larger
output-token allowance while keeping the evidence, question and prompt version
unchanged.

Execution/configuration failures must remain analytically separate from
semantic validation failures.
