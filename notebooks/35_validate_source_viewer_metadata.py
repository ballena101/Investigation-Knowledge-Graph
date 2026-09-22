# Databricks notebook source
# MAGIC %md
# MAGIC # 35 — Validate source-viewer metadata
# MAGIC
# MAGIC Read-only validation for the IKF/MAIRA embedded evidence viewer.
# MAGIC
# MAGIC This notebook does not modify Neo4j, Delta, source files or the App.
# MAGIC It checks whether one completed analysis has the metadata required to
# MAGIC render cited PDF pages in Findings & Knowledge.

# COMMAND ----------

dbutils.widgets.text(
    "analysis_id",
    "",
    "Analysis ID",
)

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1 pymupdf==1.26.4

# COMMAND ----------

import os
import re

import fitz
from neo4j import GraphDatabase

analysis_id = dbutils.widgets.get("analysis_id").strip()

if not re.fullmatch(r"analysis_[0-9a-f]{32}", analysis_id):
    raise ValueError(
        "Enter a normal IKF analysis_id in the form analysis_<32 hex>."
    )

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

# COMMAND ----------

with driver.session() as session:
    source_rows = [
        record.data()
        for record in session.run(
            """
            MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
                  -[:HAS_SOURCE]->
                  (d:SourceDocument)
            RETURN
                d.document_id AS document_id,
                d.filename AS filename,
                coalesce(
                    properties(d)["viewer_source_repository"],
                    properties(d)["source_managed_by"],
                    "IKF"
                ) AS repository,
                coalesce(
                    properties(d)["viewer_source_path"],
                    d.volume_path
                ) AS viewer_source_path,
                properties(d)["viewer_source_filename"] AS viewer_source_filename
            ORDER BY filename
            """,
            analysis_id=analysis_id,
        )
    ]

    node_rows = [
        record.data()
        for record in session.run(
            """
            MATCH (n:KGNode {analysis_id: $analysis_id})
            RETURN
                n.node_id AS item_id,
                "NODE" AS item_type,
                n.label AS label,
                coalesce(
                    properties(n)["evidence_references"],
                    []
                ) AS evidence_references,
                coalesce(
                    properties(n)["evidence_locations"],
                    []
                ) AS evidence_locations
            """,
            analysis_id=analysis_id,
        )
    ]

    edge_rows = [
        record.data()
        for record in session.run(
            """
            MATCH (s:KGNode {analysis_id: $analysis_id})
                  -[r]->
                  (t:KGNode {analysis_id: $analysis_id})
            RETURN
                r.edge_id AS item_id,
                "RELATIONSHIP" AS item_type,
                s.label + " — " + type(r) + " → " + t.label AS label,
                coalesce(
                    properties(r)["evidence_references"],
                    []
                ) AS evidence_references,
                coalesce(
                    properties(r)["evidence_locations"],
                    []
                ) AS evidence_locations
            """,
            analysis_id=analysis_id,
        )
    ]

driver.close()

if not source_rows:
    raise ValueError(
        "No SourceDocument is linked to this analysis. "
        "Direct-text analyses do not have a PDF viewer source."
    )

# COMMAND ----------

source_by_id = {
    row["document_id"]: row
    for row in source_rows
}

source_validation = []

for row in source_rows:
    path = row.get("viewer_source_path")
    exists = bool(path and os.path.exists(path))
    is_pdf = str(path or "").lower().endswith(".pdf")
    page_count = None
    open_error = None

    if exists and is_pdf:
        try:
            pdf = fitz.open(path)
            try:
                page_count = pdf.page_count
            finally:
                pdf.close()
        except Exception as exc:
            open_error = f"{type(exc).__name__}: {exc}"

    source_validation.append(
        {
            "document_id": row["document_id"],
            "filename": row["filename"],
            "repository": row["repository"],
            "viewer_source_path": path,
            "path_exists": exists,
            "is_pdf": is_pdf,
            "pdf_page_count": page_count,
            "open_error": open_error,
        }
    )

display(
    spark.createDataFrame(source_validation)
)

# COMMAND ----------

def parse_location(value):
    parts = str(value or "").split("|")
    if len(parts) != 3:
        return None

    def page(raw):
        raw = raw.strip()
        return int(raw) if raw.isdigit() else None

    return {
        "document_id": parts[0],
        "page_start": page(parts[1]),
        "page_end": page(parts[2]),
    }


evidence_validation = []

for item in node_rows + edge_rows:
    references = item.get("evidence_references") or []
    locations = item.get("evidence_locations") or []

    if not locations:
        evidence_validation.append(
            {
                "item_type": item["item_type"],
                "item_id": item["item_id"],
                "label": item["label"],
                "reference_count": len(references),
                "location": None,
                "document_id": None,
                "page_start": None,
                "page_end": None,
                "source_path_available": False,
                "page_range_valid": False,
                "validation_issue": "NO_EVIDENCE_LOCATION",
            }
        )
        continue

    for raw_location in locations:
        location = parse_location(raw_location)

        if location is None:
            evidence_validation.append(
                {
                    "item_type": item["item_type"],
                    "item_id": item["item_id"],
                    "label": item["label"],
                    "reference_count": len(references),
                    "location": raw_location,
                    "document_id": None,
                    "page_start": None,
                    "page_end": None,
                    "source_path_available": False,
                    "page_range_valid": False,
                    "validation_issue": "INVALID_LOCATION_FORMAT",
                }
            )
            continue

        source = source_by_id.get(
            location["document_id"]
        )

        source_path = (
            source.get("viewer_source_path")
            if source
            else None
        )

        page_count = None
        if source_path and os.path.exists(source_path):
            try:
                pdf = fitz.open(source_path)
                try:
                    page_count = pdf.page_count
                finally:
                    pdf.close()
            except Exception:
                page_count = None

        start = location["page_start"]
        end = location["page_end"] or start

        valid_range = bool(
            page_count
            and start
            and end
            and start >= 1
            and end >= start
            and end <= page_count
        )

        issue = None
        if source is None:
            issue = "DOCUMENT_NOT_LINKED"
        elif not source_path:
            issue = "NO_VIEWER_SOURCE_PATH"
        elif not os.path.exists(source_path):
            issue = "SOURCE_PATH_NOT_FOUND"
        elif not valid_range:
            issue = "INVALID_PAGE_RANGE"

        evidence_validation.append(
            {
                "item_type": item["item_type"],
                "item_id": item["item_id"],
                "label": item["label"],
                "reference_count": len(references),
                "location": raw_location,
                "document_id": location["document_id"],
                "page_start": start,
                "page_end": end,
                "source_path_available": bool(
                    source_path
                    and os.path.exists(source_path)
                ),
                "page_range_valid": valid_range,
                "validation_issue": issue,
            }
        )

display(
    spark.createDataFrame(evidence_validation)
)

# COMMAND ----------

source_failures = [
    row
    for row in source_validation
    if (
        not row["path_exists"]
        or not row["is_pdf"]
        or row["open_error"] is not None
    )
]

evidence_failures = [
    row
    for row in evidence_validation
    if row["validation_issue"] is not None
]

print("")
print("SOURCE DOCUMENTS:", len(source_validation))
print("SOURCE FAILURES:", len(source_failures))
print("GRAPH ITEMS:", len(node_rows) + len(edge_rows))
print("EVIDENCE LOCATION ROWS:", len(evidence_validation))
print("EVIDENCE FAILURES:", len(evidence_failures))

if source_failures or evidence_failures:
    raise RuntimeError(
        "Source-viewer metadata validation failed. "
        "Review the displayed rows before testing App rendering."
    )

print("")
print("PASS — SOURCE VIEWER METADATA AND PAGE RANGES ARE VALID")
print(
    "If the App still fails to render after this PASS, investigate "
    "Databricks Apps user authorization / files scope / Streamlit rendering."
)
