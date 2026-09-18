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

The review history should remain auditable.

## Proposed future app workflow

For relationships:

```text
source → relationship → target
supporting evidence
assistant status
[Validate] [Reject] [Amend]
comment
```

For taxonomy mappings:

```text
case concept
candidate mapping
supporting rationale/evidence
assistant status
[Validate] [Reject] [Change]
comment
```

## Authoritative store

Manual review decisions should be written to governed Delta / Unity Catalog tables.

Neo4j should receive the reviewed projection but should not be the sole audit store.
