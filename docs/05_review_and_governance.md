# Review and Governance

## Provenance principle

Review provenance must state who or what made the decision.

Examples:

### Assistant review

```text
review_decision = VALIDATED
review_status = ASSISTANT_VALIDATED
reviewer_type = AI_ASSISTANT
review_authority = USER_DELEGATED
```

### Human review

```text
review_decision = VALIDATED | REJECTED | AMENDED
review_status = HUMAN_VALIDATED | HUMAN_REJECTED | HUMAN_AMENDED
reviewer_type = HUMAN
reviewed_at = timestamp
review_comment = optional
```

## Important rule

Human validation must not overwrite or masquerade as assistant validation.

The review history remains append-only and auditable.

## Current App workflow

For relationships:

```text
source → relationship → target
supporting evidence
assistant status
[Validate] [Reject] [Amend]
comment
```

For EMCIP mappings:

```text
case concept
original EMCIP mapping
assistant mapping disposition
[Validate] [Reject] [Amend]
proposed replacement when amended
comment
```

## Current PoC persistence

For the controlled Commodore Clipper PoC:

- relationship reviews are stored as `RelationshipReview` nodes in Neo4j;
- EMCIP mapping reviews are stored as `EMCIPMappingReview` nodes in Neo4j;
- original graph relationships and original mappings are not overwritten;
- reviewer identity is captured from Databricks Apps forwarded identity headers.

Neo4j review persistence is deliberately pragmatic for the PoC because the existing App credentials already provide the required write path.

## Future governed audit store

If required for institutional deployment, the append-only review records can be exported to governed Delta / Unity Catalog tables from a controlled Databricks notebook or workflow. The current Neo4j review model should not be treated as the final production governance architecture.
