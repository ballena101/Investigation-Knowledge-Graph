# IKG PoC — Authoritative functional specification

## 1. Product scope

The Investigation Knowledge Graph (IKG) PoC is a generic investigation-analysis
application. It is not a Commodore Clipper application.

The current PoC focus is the **Class D dual-model workflow** for protected or
confidential investigation material.

Commodore Clipper is retained only as:

- a controlled methodology reference;
- a first candidate benchmark case;
- an example of human-reviewed evidence-grounded graph structure.

## 2. Investigator workflow

For Class D, the investigator:

1. chooses the source mode:
   - 1–5 governed documents; or
   - direct text;
2. writes the investigation question/objective;
3. chooses the model execution:
   - GPT-OSS 20B;
   - Llama 3.3 70B Instruct;
   - both;
4. submits the analysis;
5. follows visible processing status;
6. reviews the resulting summary and graph;
7. when both models are selected, compares independent outputs side by side;
8. validates/rejects/amends graph relationships.

The two models must receive the same evidence passages and the same question.
Neither model sees the other model's output before the comparison is shown.

## 3. Why the second model is called Llama, not Ollama

**Ollama is a model runtime/serving tool, not the model itself.**

The larger open-weight model selected for the PoC comparison is:

**Meta Llama 3.3 70B Instruct**

It is commonly usable through Ollama in local environments. In this IKG
Databricks architecture, however, the Class D comparison should use an approved
dedicated Databricks serving route rather than introducing an Ollama server as
another data-processing boundary.

This distinction must remain explicit in the GUI and documentation:

- model: Llama 3.3 70B Instruct;
- runtime/serving for IKG: approved Databricks endpoint;
- Ollama: not an IKG production dependency.

## 4. Class D model routes

Environment identifiers:

- `CLASS_D_GPT20_ENDPOINT`
- `CLASS_D_LLAMA70_ENDPOINT`

Requested endpoints fail closed. There is no fallback to Class A/B/C models.

The exact endpoint/model identifier is persisted with every ModelRun.

Databricks currently documents both GPT-OSS 20B and Meta Llama 3.3 70B
Instruct among supported foundation/open-weight model families, subject to
workspace/region availability.

## 5. Side-by-side comparison

If **Both models** is selected:

```text
same evidence passages + same question
             │
      ┌──────┴──────┐
      ↓             ↓
 GPT-OSS 20B   Llama 3.3 70B
      ↓             ↓
 independent    independent
 summary/graph  summary/graph
      └──────┬──────┘
             ↓
 side-by-side investigator view
```

Each side must show:

- model/endpoint;
- run status;
- summary;
- findings;
- uncertainties;
- source conflicts;
- privacy-validation status;
- graph node/relationship counts;
- interactive graph;
- evidence provenance.

No automatic merged "winner" is produced.

## 6. Llama question quota

The larger Llama route has a PoC resource-control quota.

Default:

**5 Llama questions per user per calendar day**

Timezone:

`Europe/Lisbon`

Rules:

- Llama-only run = 1 Llama question;
- Both-model run = 1 Llama question;
- GPT-OSS 20B-only run = 0 Llama questions;
- at the limit, Llama and Both are blocked until the next day;
- the remaining count is visible before submission;
- only an identity listed in `IKG_ADMIN_USERS` may reset a counter;
- an administrator may reset today's counter for a specified user;
- resets are auditable with reset timestamp and admin identity.

Configuration:

`LLAMA_DAILY_QUESTION_LIMIT=5`

The value can later be changed to 10 without changing application code.

This is a PoC compute/cost control, not a model-safety rule.

## 7. Class D direct text

Direct text is encrypted in the App before temporary persistence.

```text
raw text
  ↓
Fernet encryption
  ↓
temporary encrypted DirectTextSource
  ↓
backend decryption
  ↓
governed Delta passages
  ↓
encrypted temporary payload purged
```

The encryption key is supplied through the approved secret:

`DIRECT_TEXT_ENCRYPTION_KEY`

Raw text must not be passed as a Lakeflow Job parameter.

## 8. Evidence and graph pipeline

```text
source documents / direct text
        ↓
deterministic evidence passages + provenance
        ↓
same question + same evidence
        ↓
independent model extraction
        ↓
candidate nodes / relationships
        ↓
cross-passage resolution
        ↓
privacy validation
        ↓
model-specific knowledge graph
        ↓
human review
```

Relationship semantics remain controlled:

- FOLLOWED_BY;
- RESULTED_IN;
- CONTRIBUTED_TO;
- AFFECTED;
- SUPPORTS;
- structural relationships where applicable.

Chronology must never be promoted to causality without evidence.

## 9. Model validation — what is and is not validated

### Already validated

The Commodore Clipper reference work validates parts of the **methodology**:

- evidence-linked graph representation;
- relationship semantics;
- separation of chronology and causality;
- reviewed relationship decisions;
- reviewed EMCIP mappings;
- review provenance.

It does **not** validate GPT-OSS 20B or Llama 3.3 70B performance.

### Model validation still to execute

Both models must be tested on the same locked benchmark items.

Core metrics:

1. **Evidence grounding**
   - evidence-supported relationship rate;
   - unsupported relationship rate;
   - provenance/citation accuracy.

2. **Relationship correctness**
   - human VALIDATED / REJECTED / AMENDED;
   - precision by relationship type.

3. **Causal overreach**
   - unsupported RESULTED_IN / CONTRIBUTED_TO false-positive rate.
   - target principle: zero unsupported causal promotion.

4. **Graph completeness**
   - node precision/recall;
   - relationship precision/recall;
   - missed concepts;
   - duplicate-resolution errors.

5. **Privacy**
   - identifier leakage;
   - sensitive-information leakage;
   - automatic-redaction count;
   - human privacy-review failures.

6. **Stability**
   - repeated-run graph consistency;
   - relationship consistency;
   - evidence-reference consistency.

7. **Human effort**
   - amendments/rejections required;
   - review time where measurable.

8. **Dual-model disagreement**
   - common concepts/relationships;
   - model-unique outputs;
   - conflicting outputs.

Model validation must record model/version, endpoint, prompt/pipeline version,
question, evidence version, privacy mode, benchmark version and review version.

## 10. Can validated graph review improve the model?

Yes. Human validation is valuable model feedback, but it must be used in a
controlled way.

### A. Evaluation ground truth — first priority

Validated/rejected/amended graph relationships become expected benchmark
outputs.

This measures the model without changing it.

### B. Retrieval context

Validated knowledge can be retrieved at inference time to provide:

- relationship definitions;
- reviewed examples;
- taxonomy mappings;
- previously validated investigation patterns.

Important: prior graph knowledge is **context**, not evidence that the same
relationship exists in the current investigation.

### C. Few-shot examples

Reviewed graph examples can teach the model:

- correct causal/contributory distinctions;
- evidence-grounding format;
- rejected causal-overreach examples;
- de-identification expectations.

### D. Versioned feedback dataset

Every human review can become a structured feedback example:

```text
question + evidence
      ↓
model candidate
      ↓
VALIDATED / REJECTED / AMENDED
      ↓
versioned feedback record
```

This can support evaluation, retrieval and later adaptation.

### E. Fine-tuning — later, optional

Fine-tuning should not be the first feedback mechanism.

It requires enough representative approved examples, train/test separation,
confidentiality/legal review, model-licence review and reproducible versioning.

## 11. Avoid circular validation

A reviewed case cannot simultaneously be:

- a prompt/training example; and
- an independent test case

for the same model/version evaluation.

Maintain explicit:

- training/example set;
- development set;
- locked validation/test set.

If Commodore Clipper is used as a few-shot teaching example, it must be removed
from the locked test set for that evaluation.

## 12. Persistence of human feedback

Human review must remain append-only and preserve:

- analysis_id;
- model_run_id;
- model/version;
- node/edge ID;
- original model output;
- decision;
- amended value when applicable;
- reviewer;
- timestamp;
- comment;
- evidence passage IDs;
- prompt/pipeline version.

The original model output is not overwritten.

## 13. Current implementation status

Implemented in repository:

- documents/direct-text Class D inputs;
- required investigation question;
- GPT-OSS 20B / Llama 3.3 70B / Both selection;
- encrypted direct-text ingress;
- independent model-run namespaces;
- side-by-side rendering;
- configurable Llama daily quota, default 5;
- administrator-only quota reset;
- privacy validation;
- evidence-grounded graph pipeline;
- human-review methodology;
- model-validation specification.

Still requiring environment execution:

- deploy/approve both Class D endpoints;
- attach/configure the Class D Lakeflow Job;
- configure secrets/App resources;
- validate networking/logging/retention;
- execute the locked benchmark;
- generalise the existing human-review UI from the reference graph to every
  model-run graph;
- persist model-run feedback as the formal benchmark/learning dataset.

## 14. Documentation hierarchy

For the current PoC, read in this order:

1. **This document** — authoritative functional specification.
2. `docs/18_model_validation_and_feedback.md` — validation and learning loop.
3. `docs/15_data_protection_confidentiality.md` — privacy/confidentiality.
4. `docs/13_automated_analysis_orchestration.md` — processing orchestration.
5. `docs/02_methodology.md` — graph/evidence semantics.
6. `docs/09_commodore_clipper_case.md` — reference case only.

The Commodore Clipper document is deliberately subordinate to the generic PoC
specification.
