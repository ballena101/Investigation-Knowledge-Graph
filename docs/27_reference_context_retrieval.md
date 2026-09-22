# Reference-context retrieval

## Purpose

IKF separates occurrence evidence from legal, methodological and technical
context when answering investigator questions.

The three analytical source layers are:

```text
SOURCE_EVIDENCE
    occurrence-specific report/direct evidence

REFERENCE_CONTEXT
    legal, methodological or technical background

CONTROLLED_TAXONOMY
    governed EMCIP analytical vocabulary
```

These layers are not interchangeable.

## Source ownership

### SOURCE_EVIDENCE

Primary case evidence comes from the selected processed AnalysisGroup:

- Class B investigation reports use MAIRA canonical passages;
- Classes A/C/D use the appropriate IKF-managed inputs;
- direct text uses the existing controlled ingress.

Only SOURCE_EVIDENCE may support a statement that a case event, condition,
factor or relationship actually occurred.

### REFERENCE_CONTEXT

Reference context is owned by IKF as a dedicated reusable corpus rather than as
a second AnalysisGroup.

Volume root:

`/Volumes/bdw_analysis_prod/kg_poc/reference_context`

Governed Delta tables:

- `bdw_analysis_prod.kg_poc.reference_document`;
- `bdw_analysis_prod.kg_poc.reference_passage`.

Compact catalogue metadata is mirrored to Neo4j `ReferenceDocument` nodes for
App discovery/viewer resolution. Reference passage text remains in Delta.

Typical material includes:

- Directive 2009/18/EC;
- Directive (EU) 2024/3017;
- IMO Casualty Investigation Code MSC.255(84);
- IMO Guidelines A.1075(28);
- governed public technical/methodological material.

SHIELD documents are not part of REFERENCE_CONTEXT; SHIELD remains a separate
classification/taxonomy workflow.

Reference context may explain:

- legal or procedural requirements;
- definitions;
- methodological principles;
- technical background.

It must never be presented as evidence that an accident fact occurred.

### CONTROLLED_TAXONOMY

EMCIP remains owned by MAIRA and is used as controlled analytical vocabulary.
It is not occurrence evidence and is not merged into either passage layer.

## Indexing

Notebook `44_index_reference_context.py` deterministically indexes supported
PDF/TXT/MD/DOCX files from the IKF reference-context volume.

It preserves:

- reference document identity from source-file SHA-256;
- source path and file hash;
- reference family/code/title;
- page number where available;
- passage text;
- passage SHA-256;
- source layer `REFERENCE_CONTEXT`;
- chunking/index versions.

Known references are identified conservatively from filenames. Unrecognised
files remain `TECHNICAL_REFERENCE`; they are not silently assigned a legal or
IMO identity.

The source corpus is reusable and is not subject to per-analysis question
retention cleanup.

## App interaction

Ask / Compare LLMs exposes an optional:

`Include legal / IMO / technical reference context`

control.

The control is available only when the ReferenceDocument catalogue contains
indexed material.

Reference context is retrieved automatically from the governed reference corpus
for the current question. The user does not need to create a fake Class-A
analysis merely to make a Directive or IMO document available.

## Independent retrieval

Primary case evidence and reference context have independent retrieval.

Primary retrieval may use:

- `SCOPED_ALL_PASSAGES`;
- `DETERMINISTIC_FREE_TEXT_LEXICAL_V0.1`;
- `GOVERNED_RELATIONSHIP_EVIDENCE`.

Reference context uses MAIRA's reusable deterministic free-text lexical method
over the IKF reference passages.

Current controlled reference budget:

- maximum 24 whole passages;
- maximum 30,000 characters;
- no silent passage truncation.

Reference retrieval persists its own:

- retrieval mode;
- selected reference passage IDs;
- deterministic reference retrieval snapshot ID;
- selected passage count.

## Prompt contract

Every supplied passage is labelled explicitly:

```text
[SOURCE_LAYER: SOURCE_EVIDENCE]
...
```

or:

```text
[SOURCE_LAYER: REFERENCE_CONTEXT]
...
```

The answer contract returns two provenance arrays:

- `source_evidence_passage_ids`;
- `reference_context_passage_ids`.

The model is instructed that:

- case-specific factual claims require SOURCE_EVIDENCE;
- REFERENCE_CONTEXT cannot prove a case fact;
- legal/technical/framework statements may cite REFERENCE_CONTEXT;
- chronology does not itself establish causality.

Returned IDs are validated against the correct layer before persistence.

## Persistence and UI

QuestionModelRun stores separately:

- source-evidence passage IDs/references/locations;
- reference-context passage IDs/references/locations.

The App renders separate sections:

- **Case evidence — SOURCE_EVIDENCE**
- **Reference context — REFERENCE_CONTEXT**

The PDF viewer can open a cited reference page through the same user-authorised
Databricks Files API path, now including the governed IKF reference-context
volume root.

## Validation

Notebook `38_validate_scoped_ask_run.py` validates both layers.

It verifies:

- primary answer IDs stay inside the selected case scope/retrieval snapshot;
- reference answer IDs exist in the governed reference corpus;
- reference answer IDs stay inside the independent reference retrieval snapshot;
- one passage ID cannot be attributed to both layers;
- page locations are backed by passages from the correct layer;
- combined legacy passage IDs equal the union of the two explicit layers;
- governed MAIRA query metadata remains valid when present.

Required success marker:

`PASS — SCOPED ASK / COMPARE PRESERVES SOURCE_EVIDENCE AND REFERENCE_CONTEXT BOUNDARIES`

## Retention

QuestionRun and QuestionModelRun layer-specific passage IDs, references and page
locations are scrubbed by the analysis retention cleanup when analytical content
expires.

The reusable REFERENCE_CONTEXT source corpus itself is not deleted by
per-analysis cleanup.

## Runtime status

Implementation is complete in source and intentionally not yet deployed.

The next consolidated Databricks test session must include:

1. create/populate the IKF `reference_context` folder;
2. run notebook 44 and require:
   `PASS — IKF REFERENCE_CONTEXT CORPUS INDEXED`;
3. deploy accumulated App/Job changes once;
4. run one question with reference context disabled;
5. run one question with reference context enabled;
6. confirm visible separation of case and reference citations;
7. confirm source-page rendering from both layers;
8. run notebook 38 and require the source-layer PASS marker.
