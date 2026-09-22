# Manual EMCIP Mapping Review Workflow

## Purpose

The App supports human review of the current Commodore Clipper EMCIP analytical mappings.

The review unit is one case concept plus one original EMCIP mapping. This matters because one concept can legitimately have more than one mapping; for example, Reduced vessel stability currently has two reviewed analytical mappings.

## Current mapping population

The current PoC exposes eight mapping rows across seven mapped concepts.

Examples include:

- Electrical cable overheating → Accident Event / System / Electrical equipment
- Vehicle deck drains blocked → Accident Event / System / Bilge, drain
- Reduced vessel stability → Accident Event / System / Stability
- Reduced vessel stability → Accident Event / Failure type / Insufficient stability
- Manoeuvring capability affected → Accident Event / System / Manoeuvrability
- Vessel design constraints → Contributing Factor / CF coding / Design
- Ineffective coordination → Contributing Factor / CF coding / Lack of communication & coordination
- Berthing significantly delayed → Accident Event / Task / Berthing

## Human decisions

The App supports:

- `VALIDATED`
- `REJECTED`
- `AMENDED`

For `AMENDED`, the user must enter a proposed replacement EMCIP mapping. The proposal is recorded but does not overwrite the original mapping.

## Provenance

Each saved review stores:

- unique review ID;
- case and graph version;
- deterministic mapping key;
- concept ID, label and type;
- proposed EMCIP entity;
- assistant mapping disposition;
- original mapping;
- human decision and derived human-review status;
- proposed amended mapping where applicable;
- reviewer identity from Databricks Apps forwarded headers;
- review timestamp;
- optional comment.

## Current PoC storage

Mapping review decisions are stored as append-only `EMCIPMappingReview` nodes in Neo4j and linked to the reviewed case concept through:

- `REVIEWS_MAPPING_OF`

The original KG node and its mapping remain unchanged.

## Governance note

This is a pragmatic PoC persistence layer. A later governed implementation can export review records to Delta / Unity Catalog without changing the review semantics or provenance model.


## Superseded operational status

The Commodore Clipper-specific mapping-review implementation documented above is
retained only as historical/reference material.

The operational generic workflow is now documented in:

`docs/26_generic_emcip_mapping_review.md`

New analyses use AnalysisGroup/ModelRun-scoped `EMCIPMappingProposal` records
generated from the MAIRA EMCIP operational registry. Human amendments must
select another governed shortlist candidate; they no longer use free-text
replacement taxonomy values.
