# Class D dual-model Proof of Concept

## Objective

The Class D PoC evaluates two privacy-oriented model routes on the same
protected/confidential investigation analysis task:

- GPT-OSS 20B;
- Meta Llama 3.3 70B Instruct.

The user can provide either:

- 1–5 governed source documents; or
- direct text entered in the App.

The user also supplies the investigation question/objective.

The user may run:

- GPT-OSS 20B only;
- Llama 3.3 70B only;
- both models.

When both are selected, both models receive the same evidence passages and the
same question independently. Their outputs are stored separately and displayed
side by side.

## Model serving

Class D does not use the public/non-sensitive A/B model path.

Target endpoints:

- `CLASS_D_GPT20_ENDPOINT`
- `CLASS_D_LLAMA70_ENDPOINT`

Both are intended to be dedicated/custom Databricks Model Serving endpoints
approved for Class D use.

The App fails closed if a requested endpoint is unavailable.

## Direct-text protection

Direct text is encrypted in the App with Fernet before temporary storage.

The App never sends raw direct text as a Lakeflow Job parameter.

Processing path:

```text
user text
  ↓
App encryption
  ↓
temporary encrypted DirectTextSource
  ↓
backend Job decrypts
  ↓
Delta evidence passages
  ↓
temporary encrypted payload purged
```

The encryption key is provided through:

`DIRECT_TEXT_ENCRYPTION_KEY`

It must be stored as an approved Databricks secret/App resource and must never
be committed to GitHub.

## Dual-model execution

The Class D Lakeflow Job runs:

1. evidence extraction once;
2. GPT-OSS 20B analysis when selected;
3. Llama 3.3 70B analysis when selected;
4. final comparison completion check.

Each model run has its own:

- `ModelRun`;
- model-service identifier;
- summary;
- key findings;
- uncertainties;
- source conflicts;
- privacy-validation status;
- graph nodes/relationships;
- graph namespace.

A model cannot overwrite the other model's graph.

## Llama usage control

The PoC default limits Llama 3.3 70B to:

**5 questions per user per day**

The value is configurable with `LLAMA_DAILY_QUESTION_LIMIT`; it can be raised
to 10 later without changing application code. The current PoC default remains
5.

Timezone:

`Europe/Lisbon`

A run using "Both models" consumes one Llama question.

Usage is persisted in Neo4j as `ModelDailyUsage`.

When the limit is reached, the App blocks further Llama questions until the
next day.

Only a configured App administrator can reset the counter. An administrator
may reset today's counter for a specified user; the reset records the admin
identity and timestamp.

Administrator identities are supplied through:

`IKG_ADMIN_USERS`

No administrator email is hard-coded in source.

The daily limit is a PoC cost/resource-control rule, not a model-safety limit.

## Side-by-side comparison

When both models are selected, the completed analysis displays independent
columns for GPT-OSS 20B and Llama 3.3 70B.

Each column includes:

- exact model endpoint;
- status;
- analytical summary;
- key findings;
- uncertainties;
- source conflicts;
- graph node count;
- relationship count;
- privacy-validation outcome;
- automatic-redaction count;
- interactive graph.

The system must not merge the two model outputs before the investigator can
inspect them independently.

## Supported Llama model

The intended larger comparison model is:

**Meta Llama 3.3 70B Instruct**

Databricks endpoint/model family reference:

`databricks-meta-llama-3-3-70b-instruct`

For the Class D architecture the preferred route is a dedicated/custom
Databricks serving deployment rather than simply using the shared
pay-per-token Foundation Model API endpoint.

## Current implementation status

Implemented in repository:

- Class D model selection UI;
- GPT-OSS 20B / Llama 3.3 70B / Both;
- side-by-side result renderer;
- independent model-run graph namespaces;
- encrypted direct-text ingress;
- evidence extraction once per analysis;
- 5-question/day Llama quota;
- admin-only quota reset control;
- comparison finalizer;
- privacy validation before graph publication.

Still requiring environment setup/validation:

- deploy/approve GPT-OSS 20B endpoint;
- deploy/approve Llama 3.3 70B endpoint;
- configure App resources/secrets;
- create/update Class D Lakeflow Job;
- run end-to-end Class D validation;
- confirm private networking/logging/retention configuration.


## Ollama terminology

Ollama is a runtime, not the comparison model.

The larger model in this PoC is **Meta Llama 3.3 70B Instruct**. It can be run
through Ollama in other/local environments, but IKG's Class D design uses an
approved dedicated Databricks serving endpoint. This avoids adding an Ollama
server as another protected-data processing boundary.
