# Methodology

## Analytical separation

The methodology separates three layers:

1. **Source evidence**
   - documents;
   - pages;
   - passages;
   - interview utterances;
   - timestamps;
   - provenance.

2. **Case graph**
   - occurrence;
   - vessel;
   - events;
   - contributing factors;
   - claims;
   - findings;
   - relationships.

3. **Analytical classification**
   - EMCIP mappings or other controlled taxonomies;
   - mapping disposition;
   - review status.

A taxonomy classification is not evidence that the source explicitly used that classification.

## Relationship semantics

Current relationship vocabulary:

- `HAS_VESSEL` — deterministic structural relationship;
- `FOLLOWED_BY` — chronology only;
- `RESULTED_IN` — causal/result relationship supported by evidence;
- `CONTRIBUTED_TO` — contributory relationship supported by evidence;
- `AFFECTED` — material effect without requiring stronger causal wording.

## Critical rule

Chronology does not establish causality.

The following are materially different:

```text
A FOLLOWED_BY B
A CONTRIBUTED_TO B
A RESULTED_IN B
The investigator CONCLUDED_THAT A CONTRIBUTED_TO B
```

## Evidence classes

The broader methodology may use:

- DIRECT;
- NORMALISED;
- INFERRED;
- SYNTHESISED;
- INSUFFICIENT_EVIDENCE.

## Review philosophy

The system should propose or structure analytical content but preserve the distinction between:

- machine-generated candidate;
- assistant-reviewed candidate;
- human-reviewed decision.

Unsupported concepts remain unresolved rather than being forced into a taxonomy value.
