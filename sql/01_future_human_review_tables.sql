-- Human review tables for the Investigation Knowledge Graph PoC.
-- Delta / Unity Catalog remains the authoritative review store.

CREATE SCHEMA IF NOT EXISTS bdw_analysis_prod.kg_poc;

CREATE TABLE IF NOT EXISTS
bdw_analysis_prod.kg_poc.relationship_human_review (
    review_id STRING NOT NULL,
    case_id STRING NOT NULL,
    graph_version STRING,
    edge_id STRING NOT NULL,
    source_node_id STRING,
    source_label STRING,
    original_relationship STRING,
    target_node_id STRING,
    target_label STRING,
    assistant_review_status STRING,
    human_review_decision STRING NOT NULL,
    human_review_status STRING NOT NULL,
    amended_relationship STRING,
    reviewer_email STRING,
    reviewer_user_id STRING,
    reviewer_username STRING,
    reviewed_at TIMESTAMP NOT NULL,
    review_comment STRING
)
USING DELTA;

CREATE TABLE IF NOT EXISTS
bdw_analysis_prod.kg_poc.emcip_mapping_human_review (
    review_id STRING NOT NULL,
    case_id STRING NOT NULL,
    graph_version STRING,
    node_id STRING NOT NULL,
    emcip_entity STRING,
    attribute_name STRING,
    code_value STRING,
    assistant_review_status STRING,
    human_review_decision STRING NOT NULL,
    human_review_status STRING NOT NULL,
    amended_emcip_entity STRING,
    amended_attribute_name STRING,
    amended_code_value STRING,
    reviewer_email STRING,
    reviewer_user_id STRING,
    reviewer_username STRING,
    reviewed_at TIMESTAMP NOT NULL,
    review_comment STRING
)
USING DELTA;
