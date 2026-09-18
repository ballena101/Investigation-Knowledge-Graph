# Architecture

## Current PoC

```text
Existing reviewed Delta tables
        ↓
Neo4j publication notebooks
        ↓
Neo4j AuraDB
        ↓
Databricks App
        ↓
Interactive graph exploration
```

Databricks / Delta remains the governed analytical source. Neo4j is a graph projection and traversal layer.

## Future architecture

```text
SOURCE MATERIAL
  ├─ investigation report
  ├─ interview transcript
  ├─ witness statement
  ├─ VDR transcript
  ├─ procedure/manual
  ├─ correspondence
  └─ technical evidence
          ↓
DOCUMENT / EVIDENCE INGESTION
          ↓
pages / passages / utterances / timestamps
          ↓
LLM-ASSISTED ANALYTICAL EXTRACTION
          ↓
candidate entities / events / factors / claims
          ↓
candidate relationships
          ↓
EVIDENCE CHECK
          ↓
review queue
          ↓
reviewed case graph
          ↓
normalisation / EMCIP mapping
          ↓
Delta governed storage
          ↓
Neo4j graph projection
          ↓
investigator application
```

## MAIRA reuse

Future generic document ingestion should reuse MAIRA components where appropriate rather than duplicating:

- PDF extraction;
- page/passage generation;
- provenance;
- retrieval.

The graph project remains a separate analytical layer and repository.

## Technology responsibilities

### Databricks / Delta
- authoritative analytical records;
- provenance;
- review records;
- mappings;
- auditability.

### Neo4j
- graph projection;
- traversal;
- pattern queries;
- neighbourhood exploration;
- future cross-case graph queries.

### Databricks App
- investigator-facing interaction;
- graph exploration;
- evidence inspection;
- future review decisions.

### LLM
Future analytical assistant only:
- concept extraction;
- candidate relation extraction;
- claim normalisation;
- candidate taxonomy mapping;
- evidence comparison.

The LLM is not the authority.


## Tooling reference

The authoritative list of project tools, dependencies, responsibilities and
current status is maintained in:

`docs/14_tooling_inventory.md`

Architecture documentation should explain how components interact. The tooling
inventory should be used to answer which technologies are actually in use,
which are transitional, and which are only optional/reusable references.

## Source-control principle

GitHub repository `ballena101/Investigation-Knowledge-Graph` is the target
single source of truth for application code, processing notebooks and
documentation.

The existing workspace App source folder is transitional and must be retired
only after Git-backed deployment, Lakeflow execution, resources/secrets and one
end-to-end analysis have been validated.
