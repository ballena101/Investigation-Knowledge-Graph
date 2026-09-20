# Unified input modes and model-routing policy

## Purpose

The Investigation Knowledge Graph supports two ways to create one analytical
knowledge graph:

1. **Documents** — select 1–5 indexed source documents.
2. **Direct text** — write or paste text directly in the App.

Both routes converge on the same evidence-grounded analytical pipeline.

The source type and the privacy/model policy are separate concerns:

```text
INPUT SOURCE
  Documents | Direct text
          ↓
INFORMATION CLASS
  A | B | C | D
          ↓
MODEL POLICY
          ↓
EVIDENCE EXTRACTION / PASSAGING
          ↓
CANDIDATE EXTRACTION
          ↓
CROSS-DOCUMENT / CROSS-PASSAGE RESOLUTION
          ↓
PRIVACY VALIDATION
          ↓
KNOWLEDGE GRAPH
          ↓
HUMAN REVIEW
```

## 1. Input modes

### 1.1 Documents

The investigator can select 1–5 documents already indexed from the governed
Unity Catalog source library.

Documents remain in governed storage. The App stores the AnalysisGroup and
source links, then triggers the automated Lakeflow Job.

### 1.2 Direct text

The investigator can write or paste text directly and ask the IKG to construct
the knowledge graph from that material.

For Classes A/B/C:

1. the raw text is stored temporarily as a `DirectTextSource`;
2. a SHA-256 hash and source identifier are created;
3. the extraction Job converts the text into deterministic governed passages in
   Delta;
4. after successful persistence, `text_content` is removed from Neo4j;
5. the source node retains only metadata, hash, language, passage count and
   retention status.

Expected final retention state:

`RAW_TEXT_PURGED`

Direct text therefore uses Neo4j only as a temporary ingress buffer, not as a
permanent raw-evidence repository.

### 1.3 Class D direct text

The Class D PoC supports direct text through encrypted temporary ingress:

```text
direct text → App encryption → temporary encrypted source
→ backend decryption → governed Delta passages → encrypted payload purged
```

The key is supplied through `DIRECT_TEXT_ENCRYPTION_KEY` and must be managed
as an approved Databricks secret/App resource. Raw Class D text is not passed
as a Lakeflow Job parameter.

## 2. Information classification and model routing

The investigator declares the information class before analysis.

The class is a technical processing control, not merely metadata.

| Class | Description | Model path | Policy |
|---|---|---|---|
| A | Public / technical | `system.ai.gpt-5-6-sol` | Public/non-sensitive route |
| B | Published investigation material | `system.ai.gpt-5-6-sol` | Published-material route |
| C | Internal / restricted analytical material | `system.ai.gpt-oss-120b` | Databricks-hosted open-weight route |
| D | Article 9 / protected confidential evidence | GPT-OSS 20B, Llama 3.3 70B, or both | Dedicated endpoints; no A/B/C fallback |

### A/B

Model:

`system.ai.gpt-5-6-sol`

Developer: OpenAI  
Serving path: Databricks `system.ai` / Foundation Model API / ADI service.

A/B are the normal routes for public or published non-sensitive PoC material.

### C

Model:

`system.ai.gpt-oss-120b`

Developer: OpenAI  
Model type: open-weight  
Serving path: Databricks-hosted model service.

The purpose of the C route is to reduce external model-provider inference
exposure while retaining strong reasoning capability.

Databricks Foundation Model API controls and retention conditions still apply;
the C route is not described as zero-retention.

### D

Class D is the dual-model PoC route.

Available choices:

- **GPT-OSS 20B**
- **Meta Llama 3.3 70B Instruct**
- **Both models**

Target endpoints:

- `CLASS_D_GPT20_ENDPOINT`
- `CLASS_D_LLAMA70_ENDPOINT`

When Both is selected, the models receive the same governed evidence passages
and the same investigation question independently. Outputs use separate
model-run namespaces and are displayed side by side.

There is no fallback to GPT-5.6 Sol, GPT-OSS 120B or another model.

Llama 3.3 70B has a PoC quota of **5 questions per user per day**. A Both-model
run consumes one Llama question. Only configured `IKG_ADMIN_USERS` may reset
the daily counter.

**Terminology:** Ollama is a runtime/serving layer, not the model. The larger
comparison model is Llama 3.3 70B Instruct. If Ollama is later used to host it,
runtime and model identity are recorded separately.


## 3. Disclosure before processing

Before the user submits an analysis, the App displays:

- chosen information class;
- explanation of that class;
- exact policy-selected model path;
- model/deployment description;
- data-flow/retention caveat;
- de-identification rule;
- Class D availability/blocking status.

The user does not normally choose arbitrary models. Model selection follows the
information-class policy.

## 4. Privacy-by-design output

All model routes use:

`DE_IDENTIFIED_BY_DEFAULT`

The LLM instructions require:

- functional roles instead of personal names where possible;
- omission of unnecessary emails, phones, addresses, personal IDs, dates of
  birth and health details;
- no unnecessary witness identities;
- avoidance of re-identifying combinations;
- evidence-grounded output only.

Original evidence is not rewritten or anonymised. De-identification applies to
the analytical derivative.

## 5. Privacy validation stage

Before graph publication, the generic analysis pipeline enters:

`PRIVACY_VALIDATION`

Current deterministic checks redact direct identifiers including:

- email addresses;
- telephone-number patterns;
- explicitly labelled personal-ID patterns.

The analysis stores:

- `privacy_output_mode`;
- `privacy_validation_status`;
- `privacy_redaction_count`.

The App displays the privacy-validation stage and final redaction count.

This deterministic layer complements, but does not replace, model instructions.
Future production hardening should add evaluated person-name/NER and
re-identification-risk validation.

## 6. Visible lifecycle

The App displays the complete ordered lifecycle:

1. Analysis created
2. Workflow queued
3. Evidence extraction
4. Evidence ready
5. Candidate extraction
6. Cross-document resolution
7. Privacy validation
8. Knowledge graph construction
9. Completed

Every stage is shown as Pending, Running, Completed or Failed.

## 7. One graph pipeline, not multiple products

The IKG does not have one "document LLM" and another unrelated "text graph"
feature.

There is one analytical product:

```text
source evidence
   ↓
normalised evidence passages
   ↓
policy-selected analytical model
   ↓
evidence-grounded candidates
   ↓
resolved concepts/relationships
   ↓
privacy validation
   ↓
knowledge graph
```

Documents and direct text are simply different source-ingress methods.

## 8. Human-authored text vs model-authored graph

Direct text means the user supplies the source content.

The system may then construct the graph from that content using the same
evidence-grounded analytical rules.

The graph must not introduce causal relationships merely because they are
plausible. The direct-text route follows the same relationship vocabulary,
provenance and causality restrictions as document analysis.

## 9. Lovable

Lovable is **not part of the IKG architecture**.

The project uses:

- GitHub as source of truth;
- Databricks Apps / Streamlit for UI;
- Lakeflow Jobs for orchestration;
- Unity Catalog / Delta for governed evidence and analytical persistence;
- Neo4j for graph projection/traversal;
- Databricks model services for authorised model inference.

No IKG source evidence or application dependency is routed through Lovable.

## 10. Current implementation status

Implemented:

- unified New analysis GUI;
- Documents / Direct text input choice;
- A/B/C/D classification selector;
- model selected by policy;
- pre-submission processing disclosure;
- A/B → GPT-5.6 Sol;
- C → GPT-OSS 120B;
- Class D fail-closed dual-model routing;
- GPT-OSS 20B / Llama 3.3 70B / Both selection;
- encrypted Class D direct-text ingress;
- temporary direct-text payload purge after Delta persistence;
- 5-question/day Llama quota with admin-only reset;
- side-by-side Class D result presentation;
- de-identified-by-default model instructions;
- deterministic privacy-validation stage;
- process timeline;
- exact model disclosure in completed analysis.

Pending:

- deploy and approve the dedicated GPT-OSS 20B endpoint;
- deploy and approve the dedicated Llama 3.3 70B endpoint;
- configure `CLASS_D_GPT20_ENDPOINT` and `CLASS_D_LLAMA70_ENDPOINT`;
- validate the Class D networking/logging/retention configuration;
- add secure direct-text ingress for Class D if operationally required;
- strengthen deterministic privacy validation with evaluated PII/NER controls.
