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
- GPT-OSS 20B Class D performance: not yet benchmarked;
- Llama 3.3 70B Class D performance: not yet benchmarked;
- privacy validator: implemented at basic deterministic level, not yet
  sensitivity/recall benchmarked;
- dual-model comparison: implemented in code, pending deployed-endpoint test;
- human-feedback learning loop: designed, not yet activated for model training.

The project must keep this distinction visible in the App/documentation.
