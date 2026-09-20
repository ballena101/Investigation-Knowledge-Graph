# Current PoC Scope

## Primary PoC

The current PoC is a **Class D dual-model investigation knowledge-graph
analysis workflow**.

The Commodore Clipper 2010 case is no longer the scope boundary. It is retained
as a controlled reference/benchmark case.

## In scope

The PoC supports:

- 1–5 indexed source documents, or direct text;
- encrypted temporary handling of direct text;
- an investigator-defined question/objective;
- information classification;
- Class D protected/confidential analysis;
- GPT-OSS 20B;
- Meta Llama 3.3 70B Instruct;
- one model or both models;
- identical evidence/question input for model comparison;
- side-by-side result presentation;
- evidence-grounded nodes and relationships;
- prohibition on causal inference from chronology alone;
- privacy validation before graph publication;
- de-identified output by default;
- model/version/provenance traceability;
- Llama 3.3 70B daily usage control;
- human-review provenance;
- Neo4j graph projection;
- Databricks App interaction.

## Class D comparison question

For every Class D analysis, the user provides a question/objective.

When both models are selected:

```text
same evidence
+ same question
      ↓
GPT-OSS 20B      Llama 3.3 70B
      ↓                 ↓
independent result   independent result
      ↓                 ↓
side-by-side review
```

The models do not see or merge each other's outputs before comparison.

## Llama PoC quota

Llama 3.3 70B is limited to:

**5 questions per user per day**

Running both models consumes one Llama question.

Only configured App administrators may reset the counter.

## Direct-text confidentiality

Direct text is encrypted before temporary storage.

After the backend creates governed Delta passages, the temporary encrypted
payload is purged.

Raw direct text is not sent as a Lakeflow Job parameter.

## Reference demonstrator

The Commodore Clipper case remains available in the App as a reference
demonstrator and benchmark source.

It provides:

- 17 nodes;
- 12 relationships;
- 11 report-derived evidence-supported relationships;
- reviewed EMCIP mappings;
- an example of evidence-grounded relationship validation.

It must not be confused with formal validation of GPT-OSS 20B or Llama 3.3 70B.

## Current limitations

Still pending:

- deployment/approval of both dedicated Class D endpoints;
- environment-level private-network/logging/retention validation;
- generic human-review UI for model-run graphs;
- formal benchmark execution;
- stronger PII/NER privacy validation;
- production-grade secure deletion/retention policy;
- GitHub-native Databricks deployment replacing the transitional workspace
  source folder.

## Validation

Model-validation methodology is defined in:

`docs/18_model_validation_and_feedback.md`

Current status must remain explicit:

- graph methodology: validated on Commodore Clipper;
- GPT-OSS 20B: not yet formally benchmarked;
- Llama 3.3 70B: not yet formally benchmarked.
