# Unified input modes and model-routing policy

## Purpose

IKG has one analytical pipeline and two source-ingress methods:

1. **Documents** — select 1–5 indexed documents.
2. **Direct text** — write or paste text in the App.

The information class controls the permitted model route.

```text
INPUT
Documents | Direct text
        ↓
QUESTION / OBJECTIVE
        ↓
INFORMATION CLASS
A | B | C | D
        ↓
MODEL POLICY
        ↓
EVIDENCE PASSAGES
        ↓
MODEL RUN(S)
        ↓
PRIVACY VALIDATION
        ↓
KNOWLEDGE GRAPH(S)
        ↓
HUMAN REVIEW
```

## A/B/C routes

| Class | Model path | Normal use |
|---|---|---|
| A | `system.ai.gpt-5-6-sol` | Public / technical |
| B | `system.ai.gpt-5-6-sol` | Published investigation material |
| C | `system.ai.gpt-oss-120b` | Internal/restricted analytical material |

A/B use GPT-5.6 Sol through Databricks.

C uses the Databricks-hosted open-weight GPT-OSS 120B route.

## Class D dual-model PoC

Class D is the current PoC focus.

The investigator may select:

- **GPT-OSS 20B**
- **Llama 3.3 70B**
- **Both models**

The models run independently against the same evidence passages and the same
question.

Target endpoints:

- `CLASS_D_GPT20_ENDPOINT`
- `CLASS_D_LLAMA70_ENDPOINT`

The App fails closed if a requested endpoint is unavailable.

There is no fallback from Class D to A/B/C model routes.

## Class D direct text

Direct text is supported for Class D through encrypted temporary ingress.

Processing:

```text
user text
  ↓
Fernet encryption in App
  ↓
temporary encrypted DirectTextSource
  ↓
backend Job decrypts
  ↓
governed Delta passages
  ↓
temporary encrypted payload purged
```

The encryption key is supplied through:

`DIRECT_TEXT_ENCRYPTION_KEY`

Raw direct text is never sent as a Lakeflow Job parameter.

## Class D comparison

When both models are selected:

```text
same evidence + same question
        ↓
 ┌───────────────┬─────────────────┐
 │ GPT-OSS 20B   │ Llama 3.3 70B  │
 └───────────────┴─────────────────┘
        ↓                 ↓
 independent summary   independent summary
 independent graph     independent graph
 privacy validation    privacy validation
        ↓                 ↓
        side-by-side App view
```

Each model run receives its own `ModelRun` and graph namespace.

One model cannot overwrite the other model's result.

## Llama daily quota

Llama 3.3 70B is limited to:

**5 questions per user per day**

Timezone:

`Europe/Lisbon`

Running "Both models" consumes one Llama question.

Usage is persisted in Neo4j as `ModelDailyUsage`.

Only users listed in:

`IKG_ADMIN_USERS`

may reset the daily quota.

The administrator can reset any user's current-day quota.

## Model disclosure

Before submission, the App displays:

- information class;
- selected Class D model(s);
- endpoint availability;
- data-flow policy;
- de-identification rule;
- Llama quota where applicable.

After completion, the App displays the actual model endpoint for every
`ModelRun`.

## Privacy validation

Every model run uses:

`DE_IDENTIFIED_BY_DEFAULT`

Before graph publication, outputs pass through `PRIVACY_VALIDATION`.

Current deterministic checks include:

- email patterns;
- telephone-number patterns;
- explicitly labelled personal-ID patterns.

The model run records:

- privacy-output mode;
- privacy-validation status;
- automatic-redaction count.

This is a PoC privacy layer, not yet a complete PII/NER guarantee.

## Visible lifecycle

For generic runs:

1. Analysis created
2. Workflow queued
3. Evidence extraction
4. Evidence ready
5. Candidate extraction
6. Resolution
7. Privacy validation
8. Graph construction
9. Completed

For Class D dual-model runs, the App additionally exposes the independent
model-run results.

## One product, not separate tools

Documents and direct text are source-ingress alternatives.

GPT-OSS 20B and Llama 3.3 70B are analytical alternatives within the same Class
D pipeline.

The knowledge graph is the common analytical output.

## Lovable

Lovable is not part of the IKG architecture or data flow.

## Validation

Model validation is defined separately in:

`docs/18_model_validation_and_feedback.md`

The Commodore Clipper graph is a reference/benchmark candidate, not proof that
either Class D model is validated.
