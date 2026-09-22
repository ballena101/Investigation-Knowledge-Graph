# Databricks notebook source
# MAGIC %md
# MAGIC # 32 — Validate MAIRA-first App evidence
# MAGIC
# MAGIC Validates that a normal IKF App analysis which used MAIRA canonical
# MAGIC evidence preserved MAIRA passage identity, exact text and text hashes.
# MAGIC
# MAGIC This notebook is read-only. It does not invoke a model or modify Neo4j.

# COMMAND ----------

dbutils.widgets.text(
    "analysis_id",
    "",
    "Analysis ID",
)

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1

# COMMAND ----------

import re

from neo4j import GraphDatabase
from pyspark.sql import functions as F

from maira.integration.ikf_passage_contract import (
    PASSAGE_CONTRACT_VERSION,
)

ANALYSIS_PASSAGE_TABLE = "bdw_analysis_prod.kg_poc.analysis_passage"
MAIRA_DOCUMENT_TABLE = "bdw_analysis_prod.maira.documents"
MAIRA_PASSAGE_TABLE = "bdw_analysis_prod.maira.passages"

analysis_id = dbutils.widgets.get("analysis_id").strip()

if not re.fullmatch(r"analysis_[0-9a-f]{32}", analysis_id):
    raise ValueError(
        "Enter a normal IKF App analysis_id in the form analysis_<32 hex>."
    )

print("Analysis:", analysis_id)
print("Contract:", PASSAGE_CONTRACT_VERSION)

# COMMAND ----------

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

with driver.session() as session:
    analysis_record = session.run(
        """
        MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
        OPTIONAL MATCH (a)-[:HAS_SOURCE]->(d:SourceDocument)
        RETURN
            properties(a)["evidence_source_mode"] AS evidence_source_mode,
            collect(
                CASE
                    WHEN d IS NULL THEN NULL
                    ELSE {
                        ikf_document_id: d.document_id,
                        filename: d.filename,
                        sha256: d.sha256,
                        extraction_status: properties(d)["extraction_status"],
                        maira_document_id: properties(d)["maira_document_id"],
                        maira_report_package_id: properties(d)["maira_report_package_id"],
                        passage_contract_version: properties(d)["passage_contract_version"]
                    }
                END
            ) AS documents
        """,
        analysis_id=analysis_id,
    ).single()

if analysis_record is None:
    driver.close()
    raise ValueError(f"AnalysisGroup not found: {analysis_id}")

evidence_source_mode = analysis_record["evidence_source_mode"]
documents = [
    item
    for item in (analysis_record["documents"] or [])
    if item is not None
]

print("Evidence source mode:", evidence_source_mode)
print("Documents:", len(documents))

if not documents:
    driver.close()
    raise ValueError(
        "This validation is for document-based App analyses; no source documents found."
    )

# COMMAND ----------

canonical_documents = [
    item
    for item in documents
    if item.get("extraction_status") == "MAIRA_CANONICAL"
]

fallback_documents = [
    item
    for item in documents
    if item.get("extraction_status") != "MAIRA_CANONICAL"
]

print("MAIRA canonical documents:", len(canonical_documents))
print("Temporary fallback documents:", len(fallback_documents))

if not canonical_documents:
    display(
        spark.createDataFrame(
            [
                {
                    "filename": item.get("filename"),
                    "ikf_document_id": item.get("ikf_document_id"),
                    "extraction_status": item.get("extraction_status"),
                }
                for item in fallback_documents
            ]
        )
    )
    driver.close()
    dbutils.notebook.exit(
        "NO MAIRA CANONICAL DOCUMENTS — this App analysis used only the temporary IKF fallback."
    )

# COMMAND ----------

validation_rows = []
errors = []

for document in canonical_documents:
    ikf_document_id = document["ikf_document_id"]
    maira_document_id = document.get("maira_document_id")
    sha256 = str(document.get("sha256") or "").lower()

    if document.get("passage_contract_version") != PASSAGE_CONTRACT_VERSION:
        errors.append(
            f"{ikf_document_id}: unexpected passage contract version "
            f"{document.get('passage_contract_version')}"
        )

    maira_doc_rows = (
        spark.table(MAIRA_DOCUMENT_TABLE)
        .filter(F.col("document_id") == maira_document_id)
        .filter(F.lower(F.col("sha256")) == sha256)
        .select("document_id", "report_package_id", "sha256")
        .collect()
    )

    if len(maira_doc_rows) != 1:
        errors.append(
            f"{ikf_document_id}: expected exactly one MAIRA document/hash match, "
            f"found {len(maira_doc_rows)}"
        )
        continue

    ikf_passages = (
        spark.table(ANALYSIS_PASSAGE_TABLE)
        .filter(F.col("analysis_id") == analysis_id)
        .filter(F.col("document_id") == ikf_document_id)
        .select(
            "passage_id",
            "passage_order",
            "page_start",
            "page_end",
            "passage_text",
            F.lower(F.col("text_sha256")).alias("text_sha256"),
            "extraction_version",
        )
        .alias("ikf")
    )

    maira_passages = (
        spark.table(MAIRA_PASSAGE_TABLE)
        .filter(F.col("document_id") == maira_document_id)
        .select(
            "passage_id",
            F.col("passage_number").alias("passage_order"),
            F.col("start_page").alias("page_start"),
            F.col("end_page").alias("page_end"),
            "passage_text",
            F.lower(F.col("passage_text_sha256")).alias("text_sha256"),
        )
        .alias("maira")
    )

    ikf_count = ikf_passages.count()
    maira_count = maira_passages.count()

    comparison = ikf_passages.join(
        maira_passages,
        on="passage_id",
        how="full",
    ).select(
        "passage_id",
        F.col("ikf.passage_order").alias("ikf_passage_order"),
        F.col("maira.passage_order").alias("maira_passage_order"),
        F.col("ikf.page_start").alias("ikf_page_start"),
        F.col("maira.page_start").alias("maira_page_start"),
        F.col("ikf.page_end").alias("ikf_page_end"),
        F.col("maira.page_end").alias("maira_page_end"),
        F.col("ikf.passage_text").alias("ikf_text"),
        F.col("maira.passage_text").alias("maira_text"),
        F.col("ikf.text_sha256").alias("ikf_hash"),
        F.col("maira.text_sha256").alias("maira_hash"),
        F.col("ikf.extraction_version").alias("ikf_extraction_version"),
    )

    mismatches = comparison.filter(
        F.col("ikf_passage_order").isNull()
        | F.col("maira_passage_order").isNull()
        | (F.col("ikf_passage_order") != F.col("maira_passage_order"))
        | (F.col("ikf_page_start") != F.col("maira_page_start"))
        | (F.col("ikf_page_end") != F.col("maira_page_end"))
        | (F.col("ikf_text") != F.col("maira_text"))
        | (F.col("ikf_hash") != F.col("maira_hash"))
        | (F.col("ikf_extraction_version") != PASSAGE_CONTRACT_VERSION)
        | (F.sha2(F.col("ikf_text"), 256) != F.col("ikf_hash"))
    )

    mismatch_count = mismatches.count()

    validation_rows.append(
        {
            "filename": document.get("filename"),
            "ikf_document_id": ikf_document_id,
            "maira_document_id": maira_document_id,
            "ikf_passages": ikf_count,
            "maira_passages": maira_count,
            "mismatches": mismatch_count,
        }
    )

    if ikf_count != maira_count:
        errors.append(
            f"{ikf_document_id}: IKF/MAIRA passage count differs "
            f"({ikf_count} vs {maira_count})"
        )

    if mismatch_count:
        display(mismatches)
        errors.append(
            f"{ikf_document_id}: {mismatch_count} canonical passage mismatch(es)"
        )

# COMMAND ----------

display(
    spark.createDataFrame(validation_rows).orderBy("filename")
)

if errors:
    print("")
    print("VALIDATION ERRORS")
    for error in errors:
        print(" -", error)
    driver.close()
    raise ValueError(
        "MAIRA-first App evidence validation failed."
    )

print("")
print("PASS — NORMAL APP ANALYSIS PRESERVES", PASSAGE_CONTRACT_VERSION)
print("Evidence source mode:", evidence_source_mode)
print("Canonical documents validated:", len(canonical_documents))

if fallback_documents:
    print(
        "NOTE —",
        len(fallback_documents),
        "document(s) used temporary IKF fallback and are outside the canonical subset."
    )

driver.close()
