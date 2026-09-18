# Databricks notebook source
# MAGIC %md
# MAGIC # 13 — Register one analysis from a volume folder
# MAGIC
# MAGIC This is the preferred PoC ingestion route when the user can upload files
# MAGIC directly to a Unity Catalog volume but the Databricks App cannot be granted
# MAGIC access to that volume.
# MAGIC
# MAGIC **One source folder = one analysis group.**
# MAGIC
# MAGIC Example:
# MAGIC
# MAGIC `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/my_case_01`
# MAGIC
# MAGIC Upload all documents for one analysis into that folder before running this
# MAGIC notebook.

# COMMAND ----------

dbutils.widgets.text(
    "source_folder",
    "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/my_case_01",
    "1. Source folder",
)

dbutils.widgets.text(
    "analysis_title",
    "My document-group analysis",
    "2. Analysis title",
)

dbutils.widgets.text(
    "analysis_objective",
    "",
    "3. Analysis objective (optional)",
)

dbutils.widgets.dropdown(
    "language_mode",
    "Auto-detect per document",
    [
        "Auto-detect per document",
        "English",
        "Spanish",
        "Portuguese",
        "French",
        "German",
        "Italian",
        "Dutch",
        "Norwegian",
        "Icelandic",
        "Danish",
        "Swedish",
        "Finnish",
        "Polish",
        "Greek",
        "Other / mixed",
    ],
    "4. Source language handling",
)

dbutils.widgets.dropdown(
    "output_language",
    "English",
    [
        "English",
        "Spanish",
        "Portuguese",
        "French",
        "German",
        "Italian",
        "Dutch",
        "Norwegian",
        "Icelandic",
        "Danish",
        "Swedish",
        "Finnish",
        "Polish",
        "Greek",
    ],
    "5. Analysis output language",
)

# COMMAND ----------

import hashlib
import json
import mimetypes
import os
import uuid
from datetime import datetime, timezone

from pyspark.sql import Row

GROUP_TABLE = "bdw_analysis_prod.kg_poc.analysis_group"
DOCUMENT_TABLE = "bdw_analysis_prod.kg_poc.analysis_document"
PIPELINE_VERSION = "GROUP_ANALYSIS_V0.1"

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
}

source_folder = dbutils.widgets.get("source_folder").strip().rstrip("/")
analysis_title = dbutils.widgets.get("analysis_title").strip()
analysis_objective = dbutils.widgets.get("analysis_objective").strip()
language_mode = dbutils.widgets.get("language_mode").strip()
output_language = dbutils.widgets.get("output_language").strip()

if not source_folder.startswith("/Volumes/"):
    raise ValueError(
        "source_folder must use a Unity Catalog volume path beginning with "
        "'/Volumes/'."
    )

if not analysis_title:
    raise ValueError("analysis_title is required.")

if not os.path.isdir(source_folder):
    raise FileNotFoundError(
        f"Source folder does not exist or is not readable: {source_folder}"
    )

# COMMAND ----------

def sha256_file(path, chunk_size=1024 * 1024):
    digest = hashlib.sha256()

    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


source_files = []

for root, _, filenames in os.walk(source_folder):
    for filename in filenames:
        if filename == "manifest.json":
            continue

        extension = os.path.splitext(filename)[1].lower()

        if extension not in SUPPORTED_EXTENSIONS:
            continue

        path = os.path.join(root, filename)

        if os.path.isfile(path):
            source_files.append(path)

source_files = sorted(source_files)

if not source_files:
    raise ValueError(
        "No supported source documents were found. "
        "Current PoC registration supports PDF, DOCX and TXT."
    )

print(f"Supported source documents found: {len(source_files)}")

for path in source_files:
    print(" -", path)

# COMMAND ----------

analysis_id = f"analysis_{uuid.uuid4().hex}"
created_at = datetime.now(timezone.utc)
created_by = spark.sql("SELECT current_user() AS user").first()["user"]

documents = []

for path in source_files:
    filename = os.path.basename(path)
    extension = os.path.splitext(filename)[1].lower()
    sha256 = sha256_file(path)
    document_id = f"doc_{sha256[:24]}"
    mime_type, _ = mimetypes.guess_type(filename)
    byte_size = os.path.getsize(path)

    documents.append(
        {
            "analysis_id": analysis_id,
            "document_id": document_id,
            "original_filename": filename,
            "mime_type": mime_type,
            "byte_size": byte_size,
            "sha256": sha256,
            "storage_uri": path,
            "source_type": extension.lstrip(".").upper(),
            "page_count": None,
            "uploaded_by": created_by,
            "uploaded_at": created_at,
            "extraction_status": "PENDING",
            "extraction_version": None,
            "error_message": None,
            "detected_language": None,
            "language_confidence": None,
        }
    )

print("Analysis ID:", analysis_id)
print("Created by:", created_by)

# COMMAND ----------

group_row = Row(
    analysis_id=analysis_id,
    analysis_title=analysis_title,
    analysis_objective=analysis_objective or None,
    created_by=created_by,
    created_at=created_at,
    status="UPLOADED",
    document_count=len(documents),
    pipeline_version=PIPELINE_VERSION,
    graph_version=None,
    error_message=None,
    language_mode=language_mode,
    output_language=output_language,
)

group_df = spark.createDataFrame(
    [group_row],
    schema=spark.table(GROUP_TABLE).schema,
)

document_rows = [
    Row(**document)
    for document in documents
]

documents_df = spark.createDataFrame(
    document_rows,
    schema=spark.table(DOCUMENT_TABLE).schema,
)

group_df.write.mode("append").saveAsTable(GROUP_TABLE)
documents_df.write.mode("append").saveAsTable(DOCUMENT_TABLE)

print("Analysis metadata registered.")

# COMMAND ----------

manifest = {
    "analysis_id": analysis_id,
    "analysis_title": analysis_title,
    "analysis_objective": analysis_objective or None,
    "created_by": created_by,
    "created_at_utc": created_at.isoformat(),
    "status": "UPLOADED",
    "document_count": len(documents),
    "pipeline_version": PIPELINE_VERSION,
    "language_mode": language_mode,
    "output_language": output_language,
    "source_folder": source_folder,
    "documents": [
        {
            "document_id": d["document_id"],
            "original_filename": d["original_filename"],
            "mime_type": d["mime_type"],
            "byte_size": d["byte_size"],
            "sha256": d["sha256"],
            "storage_uri": d["storage_uri"],
            "source_type": d["source_type"],
            "extraction_status": d["extraction_status"],
        }
        for d in documents
    ],
}

manifest_path = os.path.join(
    source_folder,
    "manifest.json",
)

with open(
    manifest_path,
    "w",
    encoding="utf-8",
) as handle:
    json.dump(
        manifest,
        handle,
        ensure_ascii=False,
        indent=2,
    )

print("Manifest written:", manifest_path)

# COMMAND ----------

display(
    spark.sql(
        f"""
        SELECT
            analysis_id,
            analysis_title,
            status,
            document_count,
            language_mode,
            output_language,
            created_by,
            created_at
        FROM {GROUP_TABLE}
        WHERE analysis_id = '{analysis_id}'
        """
    )
)

display(
    spark.sql(
        f"""
        SELECT
            document_id,
            original_filename,
            source_type,
            byte_size,
            extraction_status,
            storage_uri
        FROM {DOCUMENT_TABLE}
        WHERE analysis_id = '{analysis_id}'
        ORDER BY original_filename
        """
    )
)

# COMMAND ----------

print("")
print("READY FOR EXTRACTION")
print("analysis_id:", analysis_id)
print("source_folder:", source_folder)
print("documents:", len(documents))
print("next step: extract and passage all documents for this analysis_id")
