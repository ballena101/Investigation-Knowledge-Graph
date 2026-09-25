# Project Charter — Investigation Knowledge Graph (IKG)

## Mission

Build an evidence-grounded investigation analysis environment that lets an
investigator submit source material, ask an investigation question, generate a
traceable knowledge graph, compare model behaviour, and retain human validation
without losing provenance to the source evidence.

## Current Proof of Concept

The current PoC is **not the Commodore Clipper case**. The current PoC is a
**Class D dual-model investigation-analysis workflow**.

For a Class D analysis, the investigator can:

1. choose 1–5 governed source documents or enter direct text;
2. enter the investigation question/objective;
3. choose GPT-OSS 20B, Meta Llama 3.3 70B Instruct, or both;
4. run the selected model(s) against the same evidence and same question;
5. inspect both outputs side by side when both are selected;
6. inspect evidence-grounded graphs and privacy-validation results;
7. human-review the analytical graph.

The Commodore Clipper 2010 material is retained only as a controlled
methodology/reference benchmark.

## Model terminology

The larger comparison model is **Meta Llama 3.3 70B Instruct**.

**Ollama is a runtime/serving tool, not a model name.** If Ollama is later used
to serve Llama, the runtime and model identity must be recorded separately.

## Class D processing flow

```text
Documents OR encrypted direct text
              ↓
Investigator question/objective
              ↓
Evidence extraction / deterministic passages
              ↓
Model choice
   ┌───────────────┬──────────────────┐
   │ GPT-OSS 20B   │ Llama 3.3 70B   │
   └───────┬───────┴────────┬─────────┘
           │                │
     independent       independent
      model run          model run
           │                │
     resolution         resolution
           │                │
   privacy validation  privacy validation
           │                │
       graph A            graph B
           └────────┬───────┘
                    ↓
          side-by-side review
                    ↓
             human validation
```

When only one model is selected, only that branch runs. When both are selected,
neither model receives the other model's result before comparison.

## Class D daily model quotas

GPT-OSS 20B is limited to **30 questions per user per day** and Llama 3.3
70B to **10 questions per user per day** in the PoC.

A Both-model analysis consumes one question from each counter. At a selected
model's limit, requests using that model are blocked until the next day.

Quota timezone: `Europe/Lisbon`.

Only identities configured in `IKG_ADMIN_USERS` may reset the current day's
model counter. No administrator email is hard-coded in source.

This is a PoC resource/cost control, not a model-safety characteristic.

## Privacy and Class D

Direct text is encrypted before temporary storage. The backend decrypts it for
evidence extraction, persists governed passages, then purges the temporary
encrypted payload.

Analytical outputs are de-identified by default and pass through privacy
validation before graph publication.

The project remains a PoC and does not claim legal/security certification.
Endpoint deployment, networking, logging, retention and organisational
authorisation must be validated before operational Class D use.

## Validation objective

The project distinguishes:

1. **graph-method validation** — graph representation, evidence links,
   relationship semantics and review;
2. **model validation** — fidelity, completeness, causal discipline, privacy,
   stability and reproducibility of a specific model/version;
3. **system validation** — end-to-end ingestion → model → graph → review.

The Commodore Clipper work supports graph-method validation and supplies a
candidate model benchmark. It does **not** yet prove GPT-OSS 20B or Llama 3.3
70B performance.

Formal methodology: `docs/18_model_validation_and_feedback.md`.

## Human-validated graph as model input

Human-validated graph knowledge can be reused through controlled mechanisms:

1. **gold-standard evaluation** — expected reviewed outputs;
2. **retrieval context** — reviewed definitions, taxonomy and prior-case
   knowledge;
3. **few-shot examples** — correct grounding and rejected causal overreach;
4. **future supervised adaptation** — only with a sufficiently large,
   approved/versioned dataset.

A reviewed graph from another case is prior knowledge, **not evidence for the
current case**.

A case used as prompt/training material must not simultaneously be an
independent validation case for the same model/version.

## Design principles

1. Evidence precedes interpretation.
2. Source evidence, model output, reviewed graph and EMCIP mapping remain
   distinguishable.
3. Causality is never inferred merely from chronology or textual proximity.
4. Unsupported relationships/mappings remain unresolved.
5. Model outputs remain reviewable.
6. Human review preserves provenance and model/version metadata.
7. Documents and direct text converge on the same evidence model.
8. Comparison models receive equivalent evidence/question input.
9. Privacy validation occurs before analytical graph publication.
10. Feedback is explicit and versioned; there is no silent self-training.

## Authoritative current documentation

Read these first:

- `01_current_poc_scope.md`
- `17_class_d_dual_model_poc.md`
- `18_model_validation_and_feedback.md`
- `15_data_protection_confidentiality.md`
- `08_roadmap.md`

Commodore Clipper-specific files are reference/benchmark documentation, not the
current product specification.


## Product positioning

The product is a **support tool for safety investigation**, not an autonomous
investigator and not a knowledge-graph product in isolation.

Its purpose is to support:

- structured analysis of documentary evidence;
- evidence-grounded AI assistance;
- knowledge structuring and graph representation;
- comparison of AI model outputs;
- preservation of source provenance;
- privacy/confidentiality controls;
- human validation and amendment.

The knowledge graph remains an internal analytical representation.

The product must not:

- replace the investigator's professional judgement;
- determine blame or liability;
- convert AI output directly into a formal investigation finding;
- imply legal compliance merely because technical controls exist.
