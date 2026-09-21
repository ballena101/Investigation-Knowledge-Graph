# Model validation and human-feedback loop

## 1. What has been validated so far

The Commodore Clipper work provides a **validated graph/evidence reference
case**, not yet a formal validation of GPT-OSS 20B or Llama 3.3 70B.

The reference work established:

- reviewed graph structure;
- evidence-grounded relationships;
- separation of chronology and causality;
- validated EMCIP mappings;
- human-review persistence.

This is valuable ground truth, but it must not be described as proof that the
new generic models perform correctly.

## 2. What the Class D PoC will validate

GPT-OSS 20B and Llama 3.3 70B will be evaluated independently on identical
evidence/question sets.

Validation dimensions:

### 2.1 Evidence grounding

For each generated claim/node/relationship:

- does supporting evidence exist?
- is the cited passage actually relevant?
- does the output remain faithful to the source?

Metrics:

- evidence-supported relationship rate;
- unsupported relationship rate;
- provenance accuracy.

### 2.2 Relationship correctness

Human reviewer decisions:

- VALIDATED;
- REJECTED;
- AMENDED.

Metrics:

- relationship acceptance rate;
- rejection rate;
- amendment rate;
- precision by relationship type.

### 2.3 Causal overreach

Critical model-safety metric:

- cases where chronology/proximity was incorrectly promoted to
  `RESULTED_IN` or `CONTRIBUTED_TO`.

Metric:

- causal-overreach false-positive rate.

Target principle:

**zero unsupported causal promotion**.

### 2.4 Graph completeness

Against a human-reviewed reference:

- relevant concepts missed;
- relevant relationships missed;
- excessive duplicate concepts;
- unsupported extra concepts.

Potential metrics:

- node recall/precision after canonical matching;
- relationship recall/precision;
- duplicate-resolution error rate.

### 2.5 Privacy/confidentiality

Evaluate whether analytical outputs expose:

- personal names;
- witness identities;
- emails/phones/IDs;
- health/sensitive data;
- re-identifying combinations.

Metrics:

- direct identifier leakage rate;
- privacy-validator redaction count;
- human privacy-review failures.

### 2.6 Stability

Repeat selected benchmark analyses with deterministic settings where possible.

Evaluate:

- graph structure consistency;
- relationship-label consistency;
- evidence-reference consistency.

### 2.7 Comparative usefulness

When both models are run:

- which findings are common?
- which are unique?
- where do models conflict?
- which model requires fewer human amendments?

No model is declared "better" solely because it produces more nodes or
relationships.

### 2.8 Efficiency

Each model run records, where available:

- elapsed processing time;
- prompt tokens;
- completion tokens;
- total tokens.

These metrics allow quality/privacy results to be interpreted together with
operational efficiency rather than in isolation.

## 3. Gold-standard validation dataset

The project should build a controlled benchmark from human-reviewed analyses.

Each benchmark item should contain:

- source evidence identifiers;
- investigation question;
- expected/canonical concepts;
- validated relationships;
- evidence passage links;
- rejected relationships;
- privacy expectations;
- reviewer metadata;
- benchmark version.

The Commodore Clipper case can become the first benchmark case, but additional
cases are needed before model-performance conclusions are credible.

## 4. Can validated graph knowledge be fed back into the model?

Yes, but through controlled mechanisms.

### 4.1 Evaluation ground truth

First and most important use:

validated graphs become gold-standard expected outputs.

This does not change the model. It measures it.

### 4.2 Retrieval / knowledge context

Validated knowledge can be retrieved at inference time and supplied as
controlled context, for example:

- relationship definitions;
- validated investigation patterns;
- taxonomy mappings;
- similar reviewed cases.

The model must still distinguish retrieved prior knowledge from evidence in the
current investigation.

Prior validated knowledge cannot be used as evidence that a relationship exists
in the current case.

### 4.3 Few-shot examples

Human-reviewed examples can be used in prompts to demonstrate:

- correct relationship semantics;
- acceptable evidence grounding;
- examples of rejected causal inference;
- desired de-identification.

This is useful before fine-tuning.

### 4.4 Fine-tuning / adaptation

A sufficiently large, representative, approved set of validated examples could
later be used for supervised fine-tuning or another adaptation technique.

This is **not part of the current PoC**.

Before fine-tuning, assess:

- confidentiality/data rights;
- representativeness;
- leakage;
- versioning;
- train/test separation;
- model licensing;
- reproducibility.

### 4.5 Active-learning feedback

Human review can feed a controlled improvement dataset:

```text
model candidate
   ↓
human VALIDATED / REJECTED / AMENDED
   ↓
versioned feedback example
   ↓
evaluation / retrieval / future training set
```

This feedback must be explicit and versioned; the model must not silently
self-train from user review events.

## 5. Avoiding circular validation

A case used as a prompt example or training item must not also be used as an
independent test case for the same model/version.

Maintain explicit splits:

- training/example set;
- development set;
- locked validation/test set.

The Commodore Clipper graph can be:

- a benchmark test case, or
- a teaching/few-shot example,

but not both simultaneously for the same formal evaluation.

## 6. Model/version traceability

Every evaluation must record:

- model developer;
- serving endpoint;
- model/version;
- prompt/pipeline version;
- privacy-output mode;
- evidence-extraction version;
- analysis question;
- date/time;
- benchmark version;
- human-review version.

Without this metadata, scores are not reproducible.

## 7. Current validation status

Current state:

- graph/evidence methodology: validated on controlled Commodore Clipper case;
- generic extraction pipeline: implemented, not yet formally benchmarked;
- GPT-OSS 20B Class D model service: connected; formal real-case performance benchmark pending;
- Llama 3.3 70B Class D model service: connected; formal real-case performance benchmark pending;
- first synthetic same-input dual-model validation cycle: completed and persisted;
- privacy validator: implemented at basic deterministic level, not yet
  sensitivity/recall benchmarked;
- dual-model comparison: connectivity and persistence path verified; formal locked benchmark pending;
- human-feedback learning loop: designed, not yet activated for model training.

The project must keep this distinction visible in the App/documentation.


## 8. PoC validation protocol

For the dual-model PoC, validation should be run as a controlled benchmark,
not by judging whichever answer looks more convincing.

For every benchmark item:

1. freeze the source evidence and investigation question;
2. freeze the extraction/passage version;
3. run GPT-OSS 20B and Llama 3.3 70B independently with the same evidence and
   prompt/pipeline version;
4. preserve each raw model result and generated graph separately;
5. compare each model against the human-reviewed benchmark graph;
6. human-review unsupported, missing and amended relationships;
7. run privacy-leakage checks;
8. repeat selected items to measure stability;
9. record model, endpoint, prompt, graph and benchmark versions.

Minimum reported measures per model:

| Dimension | Measure |
|---|---|
| Evidence grounding | supported relationships / generated relationships |
| Unsupported output | unsupported relationships / generated relationships |
| Relationship precision | validated relationships / reviewed generated relationships |
| Relationship recall | expected validated relationships recovered / expected relationships |
| Causal discipline | unsupported causal/contributory promotions |
| Concept coverage | expected canonical concepts recovered |
| Duplicate resolution | erroneous merges/splits |
| Provenance | relationships with correct supporting passage references |
| Privacy | direct/re-identifying leakage events |
| Human effort | rejected + amended items and review time |
| Stability | agreement across repeated runs |

The comparison view may display differences, but model-validation conclusions
must be based on the benchmark and human review rather than output volume.

## 9. Acceptance principle for causal relationships

The most important failure mode is unsupported causal promotion.

For `RESULTED_IN` and `CONTRIBUTED_TO`, the reviewer should verify:

1. the source passage supports more than chronology/proximity;
2. the relationship direction is correct;
3. the relationship label matches the strength of the evidence;
4. the cited evidence actually supports that relationship;
5. the model has not imported causal knowledge from another case.

The PoC target is zero unsupported causal promotions. A non-zero result is
recorded as a model/pipeline failure for that benchmark item, not silently
corrected before scoring.

## 10. Using graph validation to improve model behaviour

Human validation is useful model input, but the project must keep three stores
conceptually separate:

```text
CURRENT-CASE EVIDENCE
        ↓
model inference
        ↓
CANDIDATE GRAPH
        ↓
human review
        ↓
VALIDATED KNOWLEDGE / FEEDBACK
```

Validated knowledge may later be retrieved into a new inference as
`REVIEWED_PRIOR_KNOWLEDGE`.

It must never be represented as `CURRENT_CASE_EVIDENCE` unless the underlying
source evidence is actually part of the current case.

Recommended first feedback mechanism:

- retrieve relationship definitions;
- retrieve reviewed positive examples;
- retrieve reviewed rejected examples, especially causal-overreach examples;
- include their provenance and benchmark/review version;
- instruct the model that examples teach semantics and do not establish facts
  in the current case.

This is preferable to immediate fine-tuning because it is inspectable,
reversible and versionable.

## 11. Validation-set contamination control

Once a reviewed graph is used as retrieval/few-shot input for a model run, that
same graph is no longer an independent blind benchmark for that run.

Maintain explicit flags such as:

- `BENCHMARK_LOCKED`
- `DEVELOPMENT`
- `FEW_SHOT_ELIGIBLE`
- `RETRIEVAL_ELIGIBLE`
- `TRAINING_ELIGIBLE`

A benchmark version should record which examples were visible to the model.


## 8. Validation data must not silently become model input

Human validation in the knowledge graph is authoritative feedback, but it is
not automatically inserted into future model prompts.

Three stores must remain logically separate:

1. **source evidence** — what the current investigation material says;
2. **validated analytical knowledge** — human-reviewed graph/review records;
3. **model-improvement assets** — explicitly curated benchmark, retrieval,
   few-shot or training examples.

A human-validated graph may be promoted from (2) to (3) only through an
explicit, versioned curation action.

This prevents a reviewed interpretation from being silently treated as source
evidence in another investigation.

## 9. Recommended PoC validation protocol

For each benchmark question, run GPT-OSS 20B and Llama 3.3 70B against
the **same frozen passages and same prompt/pipeline version**.

Record independently for each model:

- nodes proposed;
- relationships proposed;
- passage/evidence links;
- unsupported relationships;
- human VALIDATED / REJECTED / AMENDED decisions;
- missed gold-standard nodes/relationships;
- privacy leakage/redactions;
- runtime and failure/JSON-retry rate.

Primary PoC measures:

- relationship precision;
- relationship recall against the locked reviewed graph;
- unsupported causal relationship rate;
- evidence-grounding accuracy;
- node precision/recall after canonical matching;
- human amendment rate;
- privacy leakage rate;
- structured-output success rate.

The two model outputs must remain independent until scoring is complete.

## 10. Initial benchmark strategy

The Commodore Clipper controlled graph can seed the benchmark because it
already contains reviewed relationships and mappings. However, it is only one
case and cannot support a general performance claim.

For formal comparison:

- freeze a benchmark version;
- keep some cases completely unseen by prompt examples/retrieval;
- do not use a locked test case as few-shot context for the same evaluation;
- expand to several casualty/event patterns and source types;
- record reviewer and benchmark version.

The current project therefore validates **methodology and implementation**
before it validates model quality.


## 12. First persisted dual-model validation milestone

On 21 September 2026 the PoC completed its first end-to-end synthetic dual-model
validation cycle using GPT-OSS 20B and Llama 3.3 70B through Databricks Unity
Gateway. Both models received the same synthetic source text and question and
returned the expected contributing factor, `water ingress`.

The result was persisted in:

`bdw_analysis_prod.kg_poc.ikf_model_benchmark_results`

with benchmark identifier:

`ikf_benchmark_001`

and human validation state:

`validated`

This is a connectivity/persistence milestone only and must not be interpreted
as model-quality evidence. The first meaningful performance benchmark starts
with frozen real investigation passages, versioned prompts, independent model
outputs and explicit human review.

Implementation details are recorded in
`docs/21_class_d_model_services_and_first_benchmark.md`.
