# Future Corpus Analysis

## Target

The real future target is not one-by-one document analysis.

The system should accept:

- one source;
- a group of sources for one investigation;
- a collection of investigations;
- a controlled corpus.

## Investigation-level analysis

Example questions:

- Which evidence supports this finding?
- Which interview statements corroborate the report?
- Which sources conflict on event timing?
- Which factors are supported by more than one independent source?
- Which analytical relationships still require review?

## Cross-case analysis

Example questions:

- Which contributing factors recur across investigations?
- Which events frequently precede a selected consequence?
- Which safety issues recur across authorities or vessel types?
- Which recommendations address similar causal patterns?
- Which investigations have structurally similar event chains?

## Review-at-scale

The future workflow should avoid requiring a human to review every extracted item.

Preferred model:

```text
corpus
  ↓
automated candidate extraction
  ↓
evidence grounding
  ↓
high-confidence supported items
  +
exception / uncertainty queue
  ↓
targeted human review
```

## LLM role

LLMs should support linguistic and semantic analysis:

- extracting candidate entities;
- extracting candidate relationships;
- normalising terminology;
- comparing claims;
- identifying candidate mappings.

Deterministic systems should handle:

- identifiers;
- provenance;
- storage;
- audit history;
- graph persistence;
- filtering;
- counts and metrics.
