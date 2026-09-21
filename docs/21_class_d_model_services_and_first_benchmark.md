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

The first PoC validation round targets 12 core benchmark items. The purpose is
coverage of distinct behaviours, not statistical representativeness.

Planned coverage:

1. synthetic connectivity/extraction check — completed;
2. real contributing-factor extraction — completed;
3. negative-control abstention — completed;
4. chronology without causal support — completed;
5. explicit causal relationship — completed;
6. multiple contributing factors in one passage — completed;
7. ambiguous/insufficient evidence requiring abstention — completed;
8. supported factor expressed indirectly — completed;
9. unsupported plausible-domain inference — completed;
10. duplicate/overlapping factor candidates — completed;
11. evidence-quote accuracy — completed;
12. relationship-direction accuracy — completed.

The core 12-item round is now complete. Additional checks, such as
privacy/de-identification and repeated-run stability, are tracked as supplementary
controls rather than extending the core benchmark count.

Results from the 12-item round are descriptive PoC validation evidence and must
not be presented as a general model-performance estimate.


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


## 15. Benchmark 005 explicit contributory relationship

Benchmark 005 used a synthetic control in which the source explicitly stated
that a blocked cooling-water inlet contributed to engine overheating.

Human reference:

`blocked cooling-water inlet`

Observed outputs:

- MODEL_A / GPT-OSS 20B identified the blocked cooling-water inlet and cited the
  supporting wording;
- MODEL_B / Llama 3.3 70B identified the same factor and explicitly linked it to
  the source phrase `contributed to the overheating of the engine`.

Both outputs were human-validated for this benchmark item.

This benchmark complements benchmark 004: benchmark 004 tests restraint when
only chronology is present, while benchmark 005 tests recognition when a
contributory relationship is explicitly stated.


## 16. Benchmark 006 multiple supported contributing factors

Benchmark 006 used a synthetic control containing two explicitly supported
contributing factors:

1. inadequate maintenance of the cooling system;
2. delayed detection of the rising temperature.

Observed result:

- MODEL_A / GPT-OSS 20B recovered both factors, kept them separate and cited the
  supporting wording;
- MODEL_B / Llama 3.3 70B recovered the same two factors, kept them separate and
  cited the supporting wording.

No unsupported additional factor was introduced.

Both model outputs were human-validated for this benchmark item.


## 17. Benchmark 007 ambiguous/insufficient-evidence abstention

Benchmark 007 used a synthetic passage containing:
- increased engine temperature;
- a cooling-system inspection two days earlier;
- a later engine shutdown.

The passage did not explicitly establish any contributing factor.

Expected response:

`NO_SUPPORTED_CONTRIBUTING_FACTOR`

Final clean-run result:
- MODEL_A / GPT-OSS 20B: correct abstention;
- MODEL_B / Llama 3.3 70B: correct abstention.

An earlier Llama output repeated benchmark-006 content. This was traced to notebook-state / response reuse rather than a clean benchmark-007 run and is excluded from semantic scoring.

This benchmark tests resistance to plausible but unsupported maintenance/temporal inference.


## 18. Benchmark 008 indirectly supported contributing factor

Benchmark 008 tested whether the models could identify a contributing factor
without relying on the literal phrase "contributed to".

The source described a cooling-water strainer heavily obstructed with debris and
stated that, as a result, cooling-water flow to the engine was substantially
reduced before the engine temperature increased.

Human reference:

`heavily obstructed cooling-water strainer`

Observed result:

- MODEL_A / GPT-OSS 20B identified the obstructed cooling-water strainer and
  cited the supporting wording;
- MODEL_B / Llama 3.3 70B identified the same factor and correctly referred to
  the supported mechanism linking the obstruction to reduced cooling-water
  flow.

Both outputs were human-validated for this benchmark item.


## 19. Benchmark 009 unsupported plausible-domain inference

Benchmark 009 used a synthetic technical passage describing an unexpected main-
engine stoppage and restart, while explicitly stating that no defect was
identified in the information provided.

Expected response:

`NO_SUPPORTED_CONTRIBUTING_FACTOR`

Observed result:

- MODEL_A / GPT-OSS 20B: correct abstention;
- MODEL_B / Llama 3.3 70B: correct abstention.

Neither model introduced a plausible engineering cause from general domain
knowledge. This benchmark therefore tests evidence-bounded restraint in the
presence of technically suggestive but causally insufficient information.


## 20. Benchmark 010 duplicate/overlapping candidate handling

Benchmark 010 described the same underlying contributing factor twice:
- the cooling-water strainer was heavily blocked with debris;
- the obstruction of the strainer reduced cooling-water flow and contributed to overheating.

Human reference:

`blocked/obstructed cooling-water strainer`

Observed result:
- MODEL_A / GPT-OSS 20B returned one merged factor;
- MODEL_B / Llama 3.3 70B explicitly recognised both descriptions as referring to the same underlying factor and returned one merged factor.

Both outputs were human-validated. No duplicate-candidate failure was observed.


## 21. Benchmark 011 evidence-quote accuracy

Benchmark 011 tested whether the model could identify the supported contributing
factor while citing the correct source sentence and ignoring nearby distractors.

Human reference factor:

`Emergency generator not tested in accordance with the planned maintenance schedule`

Correct supporting evidence:

`During the investigation, it was established that the emergency generator had not been tested in accordance with the planned maintenance schedule.`

Observed result:

- MODEL_A / GPT-OSS 20B identified only the supported maintenance-testing factor
  and cited the correct sentence. Review: `VALIDATED`.
- MODEL_B / Llama 3.3 70B correctly identified the maintenance-testing factor and
  cited the correct sentence, but additionally classified `loss of emergency
  electrical power` as a contributing factor. The source sentence describes
  that item as delaying recovery of essential systems; in this benchmark it is
  treated as a consequence/effect rather than a contributing factor. The second
  candidate is therefore `REJECTED`.

This benchmark introduces a distinct semantic error class: confusing an
event/consequence/effect with a contributing factor.

### API invocation semantics

The two Class D model services use different OpenAI-compatible API surfaces and
their response objects must be handled differently.

#### MODEL_A — GPT-OSS 20B

Notebook call pattern:

```python
response_a = client.responses.create(
    model=MODEL_A,
    max_output_tokens=600,
    input=[
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt}
            ]
        }
    ]
)

final_text_a = response_a.output_text
```

Databricks returned the underlying model identifier:

`gpt-oss-20b-080525`

The response object is an OpenAI `Response`. It may contain separate reasoning
items and final assistant-message items. Benchmark scoring uses the final
user-visible output (`response.output_text`), not the reasoning content.

A response with `status="incomplete"` and
`incomplete_details.reason="max_output_tokens"` is an execution/configuration
event and is not scored as a semantic answer.

An empty `input=[]` call is not a valid benchmark request even if the API
returns a generic assistant response; every benchmark must explicitly send the
frozen prompt.

#### MODEL_B — Llama 3.3 70B Instruct

Notebook call pattern:

```python
response_b = client.chat.completions.create(
    model=MODEL_B,
    max_tokens=600,
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ]
)

final_text_b = response_b.choices[0].message.content
```

Databricks returned the underlying model identifier:

`meta-llama-3.3-70b-instruct-121024`

The response object is an OpenAI-compatible `ChatCompletion`. The benchmark
answer is taken from `response_b.choices[0].message.content`. Completion status
is represented by `choices[0].finish_reason`.

#### Controlled-comparison rule

The benchmark does **not** require identical SDK methods because the two model
services expose different interfaces. It requires semantic equivalence:

- identical frozen source text;
- identical frozen question/instructions;
- identical prompt version;
- independent requests;
- equivalent output-token budget;
- no cross-model answer sharing;
- model-specific response parsing;
- explicit recording of execution failures separately from semantic review.

API syntax is therefore part of the reproducibility metadata, not part of the
semantic task itself.


## 22. Failure taxonomy extension

Add:

- `CONSEQUENCE_AS_FACTOR` — the model identifies an event, outcome or effect as
  a contributing factor even though the supplied evidence supports it only as a
  consequence/effect.


## 23. Serving/API metadata required for future benchmark records

For reproducibility, future benchmark records should distinguish the configured
model-service identifier from the underlying model/version returned by the API.

Recommended additional metadata:

- `model_a_api_method = responses.create`;
- `model_a_underlying_model = gpt-oss-20b-080525`;
- `model_a_output_accessor = output_text`;
- `model_b_api_method = chat.completions.create`;
- `model_b_underlying_model = meta-llama-3.3-70b-instruct-121024`;
- `model_b_output_accessor = choices[0].message.content`;
- finish/status metadata for both models.

This prevents API-surface differences from being mistaken for model-semantic
differences and allows a later model/version change behind a stable endpoint to
be detected.


## 24. Benchmark 012 relationship-direction accuracy

Benchmark 012 tested whether the models preserved the direction of an explicitly
supported causal relationship.

Source relation:

`loss of lubricating-oil pressure -> engine shutdown`

Observed result:

- MODEL_A / GPT-OSS 20B correctly identified the contributing factor, outcome,
  relationship direction and supporting sentence.
- MODEL_B / Llama 3.3 70B also preserved the correct direction. Its outcome
  wording (`engine to shut down`) was stylistically awkward but semantically
  equivalent for this benchmark and did not reverse the relationship.

Both model outputs were human-validated for relationship-direction accuracy.


## 25. Core benchmark count locked at 12

The first validation round is formally fixed at 12 core benchmark items.

The privacy/de-identification test executed immediately after benchmark 012 is
retained as a supplementary validation control rather than being renumbered as
core benchmark 013.

Observed supplementary privacy-control result:
- MODEL_A / GPT-OSS 20B extracted the overdue lubricating-oil filter replacement
  and omitted the personal name and email address;
- MODEL_B / Llama 3.3 70B extracted the overdue filter replacement and also
  omitted the personal name and email address.

Both therefore passed this specific de-identification control.

Supplementary controls may be added without changing the locked 12-item core
benchmark set.


## 26. Consolidated summary — 13 executed validation tests

The first validation exercise executed 13 tests in total:

- 12 core benchmark items;
- 1 supplementary privacy/de-identification control.

### Benchmark-level outcome summary

| Test | Purpose | GPT-OSS 20B | Llama 3.3 70B |
|---|---|---|---|
| 001 | Synthetic connectivity / simple extraction | VALIDATED | VALIDATED |
| 002 | Real contributing-factor passage | AMENDED | AMENDED / mixed candidate review |
| 003 | Negative-control abstention | VALIDATED | VALIDATED |
| 004 | Chronology without causal support | VALIDATED after token-limit rerun | VALIDATED |
| 005 | Explicit contributory relationship | VALIDATED | VALIDATED |
| 006 | Multiple supported factors | VALIDATED | VALIDATED |
| 007 | Ambiguous / insufficient evidence | VALIDATED | VALIDATED after clean rerun |
| 008 | Indirectly supported factor | VALIDATED | VALIDATED |
| 009 | Unsupported plausible domain inference | VALIDATED | VALIDATED |
| 010 | Duplicate / overlapping candidate handling | VALIDATED | VALIDATED |
| 011 | Evidence-quote accuracy / semantic role | VALIDATED | MIXED: one VALIDATED candidate, one REJECTED consequence-as-factor candidate |
| 012 | Relationship-direction accuracy | VALIDATED | VALIDATED |
| Supplementary privacy control | De-identification / identifier omission | VALIDATED | VALIDATED |

### Descriptive benchmark-level counts

GPT-OSS 20B:
- 12 of 13 executed tests were fully validated at benchmark level;
- benchmark 002 required amendment;
- no benchmark-level semantic rejection was recorded.

Llama 3.3 70B:
- 11 of 13 executed tests were fully validated at benchmark level;
- benchmark 002 required amendment / mixed candidate review;
- benchmark 011 contained one validated candidate and one rejected candidate;
- the rejected benchmark-011 candidate was classified as `CONSEQUENCE_AS_FACTOR`.

These counts are descriptive PoC results only. They are not general accuracy
estimates and must not be used as a model ranking.

### Execution events excluded from semantic scoring

Two execution/notebook events occurred and were excluded from semantic scoring:

1. benchmark 004 / GPT-OSS 20B initially returned an incomplete response because
   `max_output_tokens=200` was exhausted during reasoning. The benchmark was
   rerun at 600 tokens and then validated.
2. benchmark 007 / Llama 3.3 70B initially displayed a response from the prior
   benchmark due to notebook-state / response reuse. A clean benchmark-007 run
   returned the expected abstention and was validated.

These are execution-control observations, not semantic model failures.

### API semantics used in the exercise

GPT-OSS 20B:
- API method: `client.responses.create(...)`;
- output accessor: `response.output_text`;
- underlying model observed: `gpt-oss-20b-080525`.

Llama 3.3 70B:
- API method: `client.chat.completions.create(...)`;
- output accessor: `response.choices[0].message.content`;
- underlying model observed: `meta-llama-3.3-70b-instruct-121024`.

The comparison therefore controls semantic input equivalence, not identical SDK
syntax.

### Interpretation

The 13-test exercise demonstrates that the dual-model validation pipeline,
candidate-level human review, abstention controls, evidence-grounding checks,
relationship-direction checks and privacy control are functioning end to end.

The exercise does not establish general model accuracy because:
- the sample is small;
- most controls are synthetic;
- only a limited number of real investigation passages have been used;
- the benchmark set is designed for behavioural coverage rather than statistical
  representativeness.

The next phase should integrate the same validation protocol with MAIRA-derived
passages and provenance so that benchmark inputs come from the governed document
analysis pipeline rather than manual `SOURCE_TEXT` variables.


## 27. MAIRA passage bridge established

The first governed bridge from MAIRA-derived passages into the IKG analysis layer
has been executed successfully.

Source:
`bdw_analysis_prod.maira.passages`

Target:
`bdw_analysis_prod.kg_poc.analysis_passage`

The bridge preserves MAIRA provenance rather than re-chunking source documents.

Field mapping used:
- `document_id -> document_id`;
- `passage_id -> passage_id`;
- `start_page -> page_start`;
- `end_page -> page_end`;
- `passage_number -> passage_order`;
- `passage_text -> passage_text`;
- `passage_text_sha256 -> text_sha256`;
- `chunking_version -> extraction_version`;
- `creation_timestamp -> created_at`;
- `detected_language -> NULL` because MAIRA passages currently do not expose that
  field directly.

The IKG adds `analysis_id` only to bind the preserved MAIRA evidence units to a
specific IKG analysis.

A Delta `MERGE` was used to keep the operation idempotent and avoid duplicate
passage insertion on reruns.

This confirms the intended architectural boundary:

`MAIRA extraction/chunking/provenance -> IKG retrieval/analysis/review/graph`

The next implementation step is evidence retrieval/selection from the bridged
passage set before dual-model inference.


## 28. MAIRA governed query semantics confirmed

The MAIRA integration review confirmed that retrieval is driven by governed query
specifications rather than ad-hoc keyword matching.

Observed examples include:

- `Q003`: `maintenance deficiencies contributed to engine failure`;
- intent: `CONTRIBUTORY_RELATIONSHIP`;
- relationship: `CONTRIBUTED_TO`;
- subject phrase: `maintenance deficiencies`;
- object phrase: `engine failure`.

MAIRA resolves the query components to controlled EMCIP concepts in
`query_spec_concepts`, including controlled contributing-factor terms,
accident-event terms and machinery context.

This supports the intended boundary:

`MAIRA governed query interpretation + retrieval -> frozen evidence set -> IKG dual-model interpretation + human review`

IKG should not replace this with an independent keyword or embedding retriever
unless a future validated requirement explicitly calls for one.


## 29. Missing MAIRA CONTRIBUTED_TO detector restored

During IKG-to-MAIRA integration, Q003 was found to have a persisted governed
query specification and controlled concept resolution but no rows in
`maira.query_relationship_assessments`.

Repository inspection showed that MAIRA had a reusable deterministic
`FOLLOWED_BY` detector but no committed `CONTRIBUTED_TO` module.

A new MAIRA source module was therefore added:

`src/maira/relationships/contributed_to.py`

and exported through:

`src/maira/relationships/__init__.py`

The detector is intentionally strict:
- subject/object/context terms come from the governed query specification;
- positive support requires explicit contributory wording;
- co-occurrence, chronology and plausible domain inference are insufficient;
- relationship direction is preserved;
- unsupported text returns `UNRESOLVED`.

This logic remains in MAIRA, not IKG. IKG consumes the resulting governed
evidence set for dual-model interpretation and human review.


## 30. CONTRIBUTED_TO detector unit test passed

The new MAIRA deterministic `CONTRIBUTED_TO` detector was tested in Databricks
with one positive and one negative control.

Positive control:
`Inadequate maintenance contributed to the engine failure.`

Result:
`SUPPORTED_REQUESTED_RELATIONSHIP`

Negative control:
`Maintenance was carried out before the engine failure.`

Result:
`UNRESOLVED`

This confirms that the detector requires explicit contributory wording and does
not promote simple co-occurrence or chronology into a contributory relationship.


## 31. Q003 real-passage assessment returned zero supported matches

Q003 was executed against the current MAIRA investigation main-report passages
using the deterministic `CONTRIBUTED_TO` detector and the governed concepts
resolved in `query_spec_concepts`.

Observed result:

`SUPPORTED MATCHES: 0`

This is retained as a legitimate deterministic result. The detector was not
relaxed merely to produce positive matches.

The next diagnostic step is to inspect MAIRA's governed terminology
normalisation layer and report-language variants before deciding whether
additional evidence-term mappings are required. This preserves the principle
that taxonomy labels and source-language evidence terms are distinct and must
be connected explicitly rather than by unsupported inference.


## 32. Q003 first real supported CONTRIBUTED_TO relationship

After adding validated terminology normalisations and an explicit deterministic grammar
for the construction `factors that contributed to OBJECT included: SUBJECT`, Q003 was
rerun against the MAIRA investigation MAIN_REPORT passages.

Observed result:

- supported matches: 1
- document_id: `doc_ce8bf6b1636aa4331674e83a`
- report_package_id: `pkg_670bccd5fe7adc52aa1ad8c0`
- passage_id: `passage_72dbb21102453719a48d8352`
- passage_number: 2
- pages: 5-9
- subject evidence term: `standards of maintenance management`
- object evidence term: `engine failure`
- cue: `CONTRIBUTED_TO_LISTED_FACTOR`
- semantic direction: `FORWARD_SEMANTIC`

The source sentence explicitly states that factors contributing to the engine failure
included standards of maintenance management. This is therefore treated as an explicit,
deterministically supported relationship rather than an inferred association.

This milestone confirms the intended path:

controlled query concepts -> validated terminology normalisation -> deterministic
relationship grammar -> supported passage-level relationship evidence.

The next step is to persist the supported relationship using the existing governed
`query_relationship_assessments` conventions, then freeze the evidence for identical
dual-model analysis.


## 33. Q003 governed relationship assessment persisted

The first real Q003 CONTRIBUTED_TO relationship was persisted in
`bdw_analysis_prod.maira.query_relationship_assessments`.

Persisted identifiers and semantics:

- query_spec_id: `af0d8a456e84ab517a5f6b606f5b94e3f91ecbc1eb48696c65b3b1033b5808d2`
- query_id: `Q003`
- report_package_id: `pkg_670bccd5fe7adc52aa1ad8c0`
- document_id: `doc_ce8bf6b1636aa4331674e83a`
- passage_number: 2
- pages: 5-9
- subject taxonomy code: `TA-197-TCL-TC-62`
- requested relationship: `CONTRIBUTED_TO`
- object taxonomy code: `TA-196-TCL-TC-1`
- relationship assessment: `SUPPORTED_REQUESTED_RELATIONSHIP`
- evidence classification: `DIRECT`
- validation method: `GENERIC_EXPLICIT_RELATIONSHIP_V0.1`
- relation cue: `CONTRIBUTED_TO_LISTED_FACTOR`
- relation direction: `FORWARD_SEMANTIC`
- subject evidence term: `standards of maintenance management`
- object evidence term: `engine failure`
- context required/satisfied: true/true
- matched context term: `main engine`
- evidence SHA-256: `2c1322756f7e2bd4e7251e05e3795cdc4fdc566dc72198525b03b0923dca5159`
- assessment_id: `6d05eabb8f4f77359b4088bf3e08397314b105663321f7d81a1c06f4bcabace4`

This row is now the governed source for the next dual-model evaluation step.
The evidence must be frozen before model execution so both Class D models receive
the identical source passage and deterministic relationship context.
