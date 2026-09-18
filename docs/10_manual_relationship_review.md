# Manual Relationship Review Workflow

## Purpose

The current PoC now supports a human-validation layer inside the Databricks App.

The review workflow is deliberately separate from the assistant review. A human decision is appended as a new governed record rather than overwriting the original graph or assistant provenance.

## Reviewable relationships

The current Commodore Clipper graph contains 12 relationships.

- 11 report-derived relationships are reviewable.
- the structural `HAS_VESSEL` edge is excluded from manual evidence validation.

## Human decisions

The App supports:

- `VALIDATED`
- `REJECTED`
- `AMENDED`

An amended relationship may currently be changed to:

- `RESULTED_IN`
- `CONTRIBUTED_TO`
- `AFFECTED`
- `FOLLOWED_BY`

## Provenance

Each saved review stores:

- unique review ID;
- case and graph version;
- edge ID;
- source and target concept IDs and labels;
- original relationship;
- assistant review status;
- human decision and derived human-review status;
- amended relationship where applicable;
- reviewer email / user ID / preferred username;
- timestamp;
- optional review comment.

Reviewer identity is obtained from Databricks Apps forwarded identity headers.

## Storage

Authoritative review table:

`bdw_analysis_prod.kg_poc.relationship_human_review`

The table is append-only from the App perspective. This preserves review history and allows later decisions to supersede earlier ones without deleting provenance.

## App resources

The App needs:

- `review_warehouse` — SQL warehouse, `CAN_USE`;
- `relationship_review_table` — Unity Catalog table, `MODIFY`.

The existing Neo4j secret resources remain unchanged.

## Current architectural rule

Neo4j remains the graph projection/query layer.

Human review is written to governed Delta / Unity Catalog first. A later step may project human-review status back into Neo4j for visual highlighting, but Neo4j is not the authoritative audit store.

## Next step

After the relationship-review flow is tested successfully, the same pattern should be applied to EMCIP mapping review.
