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

Reference context is selected from separately processed **completed Class-A IKF
analyses**.

Typical material includes:
- Directive 2009/18/EC;
- Directive (EU) 2024/3017;
- IMO Casualty Investigation Code MSC.255(84);
- IMO Guidelines A.1075(28);
- governed public technical/methodological material.

Reference context may explain:
- legal or procedural requirements;
- definitions;
- methodological principles;
- technical background.

It must not be presented as evidence that an accident fact occurred.

### CONTROLLED_TAXONOMY

EMCIP remains owned by MAIRA and is used as controlled analytical vocabulary.
It is not occurrence evidence and is not merged into either passage layer.

## App interaction

Ask / Compare LLMs contains an optional:

`Reference context (optional)`

selector.

The selector:
- shows completed Class-A analyses only;
- excludes the primary case analysis;
- currently permits up to three reference analyses;
- stores selected IDs on the QuestionRun.

Reference analyses are reusable; selecting reference context does not rerun their
document extraction.

## Independent retrieval

Primary case evidence and reference context have independent retrieval.

Primary retrieval may use:
- `SCOPED_ALL_PASSAGES`;
- `DETERMINISTIC_FREE_TEXT_LEXICAL_V0.1`;
- `GOVERNED_RELATIONSHIP_EVIDENCE`.

Reference context always uses MAIRA's reusable deterministic free-text lexical
retrieval method over the selected Class-A analysis passages.

Current controlled reference budget:
- maximum 24 whole passages;
- maximum 30,000 characters;
- no silent passage truncation.

Reference retrieval persists its own:
- retrieval mode;
- selected passage IDs;
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
- general legal/technical context can cite REFERENCE_CONTEXT;
- chronology does not itself establish causality.

Returned IDs are validated against the correct layer before persistence.

## Persistence and UI

QuestionModelRun stores separately:
- source-evidence passage IDs/references/locations;
- reference-context passage IDs/references/locations.

The App renders separate sections:

- **Case evidence — SOURCE_EVIDENCE**
- **Reference context — REFERENCE_CONTEXT**

The PDF viewer can open a cited page from either the primary analysis or the
selected reference analyses using the same user-authorised Databricks Files API
path.

## Validation

Notebook `38_validate_scoped_ask_run.py` now validates both layers.

It verifies:
- primary answer IDs stay inside the primary retrieval snapshot;
- every reference analysis is completed Class A;
- reference answer IDs stay inside the independent reference snapshot;
- one passage ID cannot be attributed to both layers;
- page locations are backed by passages from the correct layer;
- combined legacy passage IDs equal the union of the two explicit layers.

Required success marker:

`PASS — SCOPED ASK / COMPARE PRESERVES SOURCE_EVIDENCE AND REFERENCE_CONTEXT BOUNDARIES`

## Retention

Layer-specific QuestionModelRun passage IDs, references and page locations are
scrubbed by the existing analysis retention cleanup when the analytical content
expires.

Reference-analysis IDs and snapshot identifiers may remain as compact audit
metadata; substantive passage content and citations are not retained through the
content purge.

## Runtime status

Implementation is complete in source and intentionally not yet deployed.

The next consolidated Databricks test session must include:
1. one Class-B MAIRA case analysis;
2. one completed Class-A reference analysis;
3. one question using that Class-A analysis as REFERENCE_CONTEXT;
4. visible separation of case and reference citations;
5. source-page rendering from both layers;
6. notebook 38 PASS.
