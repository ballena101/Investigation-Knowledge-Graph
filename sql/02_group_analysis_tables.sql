-- Group-analysis metadata for Investigation Knowledge Graph PoC

CREATE SCHEMA IF NOT EXISTS bdw_analysis_prod.kg_poc;

CREATE TABLE IF NOT EXISTS bdw_analysis_prod.kg_poc.analysis_group (
    analysis_id STRING NOT NULL,
    analysis_title STRING NOT NULL,
    analysis_objective STRING,
    created_by STRING,
    created_at TIMESTAMP NOT NULL,
    status STRING NOT NULL,
    document_count INT,
    pipeline_version STRING,
    graph_version STRING,
    error_message STRING
)
USING DELTA;

CREATE TABLE IF NOT EXISTS bdw_analysis_prod.kg_poc.analysis_document (
    analysis_id STRING NOT NULL,
    document_id STRING NOT NULL,
    original_filename STRING NOT NULL,
    mime_type STRING,
    byte_size BIGINT,
    sha256 STRING NOT NULL,
    storage_uri STRING,
    source_type STRING,
    page_count INT,
    uploaded_by STRING,
    uploaded_at TIMESTAMP NOT NULL,
    extraction_status STRING,
    extraction_version STRING,
    error_message STRING
)
USING DELTA;

CREATE TABLE IF NOT EXISTS bdw_analysis_prod.kg_poc.analysis_passage (
    analysis_id STRING NOT NULL,
    document_id STRING NOT NULL,
    passage_id STRING NOT NULL,
    page_start INT,
    page_end INT,
    passage_order INT,
    passage_text STRING NOT NULL,
    text_sha256 STRING NOT NULL,
    extraction_version STRING,
    created_at TIMESTAMP NOT NULL
)
USING DELTA;

CREATE TABLE IF NOT EXISTS bdw_analysis_prod.kg_poc.analysis_run (
    run_id STRING NOT NULL,
    analysis_id STRING NOT NULL,
    run_type STRING NOT NULL,
    run_status STRING NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    model_endpoint STRING,
    model_version STRING,
    pipeline_version STRING,
    error_message STRING
)
USING DELTA;
