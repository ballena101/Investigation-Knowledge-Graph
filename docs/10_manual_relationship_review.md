# Manual Relationship Review Workflow

## Purpose

The current PoC supports a human-validation layer inside the Databricks App.

The review workflow is deliberately separate from assistant review. A human decision is appended as a new review record rather than overwriting the original graph relationship or assistant provenance.

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
- original edge ID;
- source and target concept IDs and labels;
- original relationship;
- assistant review status;
- human decision and derived human-review status;
- amended relationship where applicable;
- reviewer email / user ID / preferred username;
- timestamp;
- optional review comment.

Reviewer identity is obtained from Databricks Apps forwarded identity headers.

## Current PoC storage

For the PoC, review decisions are stored in Neo4j as append-only `RelationshipReview` nodes.

Each review node is linked to the corresponding source and target KG nodes using:

- `REVIEWS_SOURCE`
- `REVIEWS_TARGET`

The original relationship is not altered.

This design uses the same Neo4j credentials already attached to the Databricks App, so no SQL warehouse or additional Databricks resource permissions are required.

## Governance note

Neo4j review storage is intentionally pragmatic for the PoC.

If the project later requires a governed institutional audit store, the review records can be exported to Delta / Unity Catalog from a controlled Databricks notebook or workflow under an authorised identity.

## Next step

After the relationship-review flow is tested successfully, apply the same pattern to EMCIP mapping review.
