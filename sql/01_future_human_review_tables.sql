-- Future PoC extension: human review layer.
-- Not required by the current graph viewer.

CREATE SCHEMA IF NOT EXISTS bdw_analysis_prod.kg_poc;

CREATE TABLE IF NOT EXISTS
bdw_analysis_prod.kg_poc.relationship_human_review (
    case_id STRING NOT NULL,
    edge_id STRING NOT NULL,
    assistant_review_status STRING,
    human_review_decision STRING NOT NULL,
    human_review_status STRING NOT NULL,
    reviewer STRING,
    reviewed_at TIMESTAMP NOT NULL,
    review_comment STRING
)
USING DELTA;

CREATE TABLE IF NOT EXISTS
bdw_analysis_prod.kg_poc.emcip_mapping_human_review (
    case_id STRING NOT NULL,
    node_id STRING NOT NULL,
    emcip_entity STRING,
    attribute_name STRING,
    code_value STRING,
    assistant_review_status STRING,
    human_review_decision STRING NOT NULL,
    human_review_status STRING NOT NULL,
    reviewer STRING,
    reviewed_at TIMESTAMP NOT NULL,
    review_comment STRING
)
USING DELTA;
