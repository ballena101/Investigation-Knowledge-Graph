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

## Authoritative-source registry and indexing

REFERENCE_CONTEXT no longer depends on manually uploading every legal/IMO
document.

The Git-governed registry is:

`config/reference_sources.json`

Each approved remote source records:

- a stable registry key;
- source authority;
- reference family/code/title;
- language;
- canonical authoritative URL;
- deterministic snapshot URL;
- snapshot filename and format.

The initial governed registry contains:

- Directive 2009/18/EC — EUR-Lex;
- Directive (EU) 2024/3017 — EUR-Lex;
- MSC.255(84) Casualty Investigation Code — IMO;
- A.1075(28) investigator guidelines — IMO.

For EU legislation, the canonical EUR-Lex ELI/HTML page is retained as
authoritative provenance while the official EUR-Lex PDF is captured as the
indexed snapshot. This preserves a human-readable authoritative link while
retaining deterministic page-level evidence for retrieval and citations.

For the IMO instruments, the official IMO-hosted resolution PDF is both the
authoritative source and the indexed snapshot.

Notebook `44_index_reference_context.py`:

1. reads the Git-governed registry;
2. downloads each approved authoritative snapshot;
3. validates expected PDF content;
4. stores the captured bytes under
   `/Volumes/bdw_analysis_prod/kg_poc/reference_context/_snapshots`;
5. hashes the captured content;
6. extracts page text deterministically;
7. indexes document/passages in the governed Delta tables;
8. mirrors compact catalogue/provenance metadata into Neo4j.

The document registry preserves:

- registry key;
- source authority;
- canonical URL;
- snapshot URL;
- retrieval origin;
- source language;
- captured source path;
- captured-file SHA-256;
- reference family/code/title;
- page count;
- retrieval/index timestamps;
- source layer `REFERENCE_CONTEXT`;
- index version.

Passages preserve page numbers, passage text, passage SHA-256 and the governed
source layer.

Optional manually governed PDF/TXT/MD/DOCX files in the volume remain
supported. Files generated under `_snapshots` are excluded from the manual
scan so an authoritative URL source cannot be indexed twice.

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

The PDF viewer opens the captured cited page through the same user-authorised
Databricks Files API path. For registry-backed REFERENCE_CONTEXT material, the
App also exposes the source authority and an **Open authoritative source** link
to the canonical official URL.

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

1. keep the IKF `reference_context` Volume available;
2. ensure the Git-governed source registry is reviewed;
3. run notebook 44 and require:
   `PASS — IKF AUTHORITATIVE REFERENCE_CONTEXT CORPUS INDEXED`;
3. deploy accumulated App/Job changes once;
4. run one question with reference context disabled;
5. run one question with reference context enabled;
6. confirm visible separation of case and reference citations;
7. confirm source-page rendering from both layers;
8. run notebook 38 and require the source-layer PASS marker.
