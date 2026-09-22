# Databricks notebook source
# MAGIC %md
# MAGIC # 33 — Sync MAIRA investigation catalogue to IKF
# MAGIC
# MAGIC Publishes MAIRA investigation-document metadata into the IKF Neo4j
# MAGIC `SourceDocument` catalogue so the App can offer MAIRA reports alongside
# MAGIC IKF input documents without copying source PDFs.
# MAGIC
# MAGIC Governance:
# MAGIC - MAIRA remains owner of canonical investigation source files/passages;
# MAGIC - MAIRA `document_id`, SHA-256, role, package and `file_path` are preserved;
# MAGIC - MAIRA catalogue nodes are marked `source_managed_by = 'MAIRA'`;
# MAGIC - no MAIRA PDF is copied into the IKF volume;
# MAGIC - IKF retention must not purge or mutate MAIRA-owned source files.

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1

# COMMAND ----------

from neo4j import GraphDatabase
from pyspark.sql import functions as F

MAIRA_DOCUMENT_TABLE = "bdw_analysis_prod.maira.documents"

NEO4J_URI = dbutils.secrets.get(
    scope="kg-poc-app",
    key="neo4j_uri",
)
NEO4J_USERNAME = dbutils.secrets.get(
    scope="kg-poc-app",
    key="neo4j_username",
)
NEO4J_PASSWORD = dbutils.secrets.get(
    scope="kg-poc-app",
    key="neo4j_password",
)

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
)
driver.verify_connectivity()

print("Neo4j connection: OK")

# COMMAND ----------

if not spark.catalog.tableExists(MAIRA_DOCUMENT_TABLE):
    driver.close()
    raise RuntimeError(
        f"MAIRA document registry not found: {MAIRA_DOCUMENT_TABLE}"
    )

maira_documents = (
    spark.table(MAIRA_DOCUMENT_TABLE)
    .filter(F.col("corpus_type") == "INVESTIGATION")
    .filter(F.col("file_path").isNotNull())
    .filter(F.col("sha256").isNotNull())
    .select(
        "document_id",
        "report_package_id",
        "parent_document_id",
        "document_role",
        "country_code",
        "investigation_body",
        "report_title",
        "vessel_name",
        "report_number",
        "occurrence_date",
        "publication_date",
        "vessel_type",
        "report_page_url",
        "source_url",
        "source_link_text",
        "source_filename",
        "file_path",
        "file_size_bytes",
        "sha256",
        "http_content_type",
        "processing_status",
        "ingestion_timestamp",
        "last_seen_timestamp",
    )
    .orderBy(
        "report_package_id",
        "document_role",
        "source_filename",
    )
    .collect()
)

print("MAIRA investigation documents found:", len(maira_documents))

if not maira_documents:
    driver.close()
    raise RuntimeError(
        "No MAIRA investigation documents with source files were found."
    )

# COMMAND ----------

with driver.session() as session:
    session.run(
        """
        CREATE CONSTRAINT source_document_id_unique
        IF NOT EXISTS
        FOR (d:SourceDocument)
        REQUIRE d.document_id IS UNIQUE
        """
    ).consume()

print("Neo4j SourceDocument constraint: ready")

# COMMAND ----------

SYNC_VERSION = "MAIRA_CATALOGUE_SYNC_V0.1"

merge_query = """
MERGE (d:SourceDocument {document_id: $document_id})
ON CREATE SET
    d.first_indexed_at = datetime()
SET
    d.filename = $filename,
    d.volume_path = $file_path,
    d.relative_path = $relative_path,
    d.library_root = $library_root,
    d.source_type = $source_type,
    d.mime_type = $mime_type,
    d.byte_size = $byte_size,
    d.sha256 = $sha256,
    d.catalogue_status = 'AVAILABLE',

    d.source_managed_by = 'MAIRA',
    d.source_repository = 'MAIRA',
    d.viewer_source_repository = 'MAIRA',
    d.viewer_source_path = $file_path,
    d.viewer_source_filename = $filename,

    d.maira_document_id = $document_id,
    d.maira_report_package_id = $report_package_id,
    d.maira_parent_document_id = $parent_document_id,
    d.maira_document_role = $document_role,
    d.maira_processing_status = $processing_status,

    d.country_code = $country_code,
    d.investigation_body = $investigation_body,
    d.report_title = $report_title,
    d.vessel_name = $vessel_name,
    d.report_number = $report_number,
    d.occurrence_date = $occurrence_date,
    d.publication_date = $publication_date,
    d.vessel_type = $vessel_type,
    d.report_page_url = $report_page_url,
    d.source_url = $source_url,
    d.source_link_text = $source_link_text,

    d.index_version = $sync_version,
    d.indexed_at = datetime(),

    d.source_retention_hours = NULL,
    d.source_expires_at = NULL,
    d.source_purge_status = 'EXEMPT_MAIRA_CANONICAL'
RETURN d.document_id AS document_id
"""

synced = []

with driver.session() as session:
    for row in maira_documents:
        item = row.asDict(recursive=True)
        file_path = item["file_path"]
        filename = (
            item.get("source_filename")
            or file_path.rsplit("/", 1)[-1]
        )

        mime_type = item.get("http_content_type") or ""
        extension = (
            filename.rsplit(".", 1)[-1].upper()
            if "." in filename
            else "UNKNOWN"
        )
        source_type = (
            "PDF"
            if "pdf" in mime_type.lower() or extension == "PDF"
            else extension
        )

        params = {
            **item,
            "filename": filename,
            "relative_path": file_path,
            "library_root": "/Volumes/bdw_analysis_prod/maira/source_documents",
            "source_type": source_type,
            "mime_type": mime_type or None,
            "byte_size": item.get("file_size_bytes"),
            "sync_version": SYNC_VERSION,
        }

        record = session.run(
            merge_query,
            **params,
        ).single()

        if record:
            synced.append(record["document_id"])

print("MAIRA documents synced:", len(synced))

# COMMAND ----------

# Mark MAIRA catalogue entries no longer present in the current MAIRA registry
# as unavailable. Do not delete historical catalogue nodes because analyses may
# still reference them.

current_ids = set(synced)

with driver.session() as session:
    existing_maira_ids = [
        record["document_id"]
        for record in session.run(
            """
            MATCH (d:SourceDocument)
            WHERE d.source_managed_by = 'MAIRA'
            RETURN d.document_id AS document_id
            """
        )
    ]

stale_ids = sorted(
    set(existing_maira_ids) - current_ids
)

if stale_ids:
    with driver.session() as session:
        session.run(
            """
            UNWIND $document_ids AS document_id
            MATCH (d:SourceDocument {document_id: document_id})
            WHERE d.source_managed_by = 'MAIRA'
            SET
                d.catalogue_status = 'UNAVAILABLE',
                d.catalogue_unavailable_at = datetime()
            """,
            document_ids=stale_ids,
        ).consume()

print("Stale MAIRA catalogue entries marked unavailable:", len(stale_ids))

# COMMAND ----------

with driver.session() as session:
    rows = [
        record.data()
        for record in session.run(
            """
            MATCH (d:SourceDocument)
            WHERE d.source_managed_by = 'MAIRA'
              AND d.catalogue_status = 'AVAILABLE'
            RETURN
                d.document_id AS document_id,
                d.maira_report_package_id AS report_package_id,
                d.maira_document_role AS document_role,
                d.report_title AS report_title,
                d.filename AS filename,
                d.vessel_name AS vessel_name,
                d.source_type AS source_type,
                d.sha256 AS sha256,
                d.viewer_source_path AS viewer_source_path
            ORDER BY report_title, document_role, filename
            """
        )
    ]

if rows:
    display(spark.createDataFrame(rows))

print("")
print("PASS — MAIRA INVESTIGATION CATALOGUE SYNCED")
print("Available MAIRA source documents:", len(rows))
print("No MAIRA source PDF was copied into IKF.")

driver.close()
