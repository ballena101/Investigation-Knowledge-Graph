# Data Model

## Source

Minimum source-level concepts:

- `case_id`
- `source_id`
- `source_type`
- `document_id`
- `title`
- `author_or_speaker`
- `source_date`
- `provenance_uri`
- `source_hash`

## Evidence unit

For documents:

- `evidence_id`
- `source_id`
- `page_number`
- `section`
- `passage_id`
- `passage_text`

For interview or transcript material:

- `evidence_id`
- `source_id`
- `speaker`
- `timestamp_start`
- `timestamp_end`
- `utterance_id`
- `question`
- `answer`
- `utterance_text`

## Graph node

- `node_id`
- `case_id`
- `node_kind`
- `label`
- `graph_version`
- `mapping_disposition`

Potential node kinds include:

- Occurrence
- Vessel
- Event
- ContributingFactor
- Person
- Organisation
- Claim
- Finding
- SafetyIssue
- Recommendation
- Action
- Procedure
- System
- Equipment

## Graph relationship

- `edge_id`
- `case_id`
- `source_node_id`
- `target_node_id`
- `relationship`
- `edge_class`
- `evidence_status`
- `review_status`
- `graph_version`

## Evidence link

- `edge_id`
- `evidence_id`
- `support_type`
- `review_status`

## Taxonomy mapping

- `node_id`
- `taxonomy`
- `entity`
- `attribute`
- `value`
- `mapping_status`
- `review_status`

## Future cross-source analysis

The data model must support multiple sources contributing evidence to the same graph concept or relationship.
