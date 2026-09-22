# Databricks notebook source
# MAGIC %md
# MAGIC # 45 — Index persistent SHIELD taxonomy/reference corpus
# MAGIC
# MAGIC SHIELD is a governed classification resource, not case SOURCE_EVIDENCE
# MAGIC and not REFERENCE_CONTEXT.
# MAGIC
# MAGIC Default existing folder:
# MAGIC `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/SHIELD`
# MAGIC
# MAGIC The folder is persistent and must never inherit normal transient
# MAGIC SourceDocument retention.

# COMMAND ----------

dbutils.widgets.text(
    "shield_root",
    "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/SHIELD",
    "SHIELD corpus root",
)

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1 pymupdf==1.26.4 python-docx==1.2.0

# COMMAND ----------

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import fitz
from docx import Document as DocxDocument
from neo4j import GraphDatabase
from pyspark.sql import Row
from pyspark.sql.types import (
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

SHIELD_ROOT = (
    dbutils.widgets.get("shield_root")
    .strip()
    .rstrip("/")
)

SHIELD_DOCUMENT_TABLE = (
    "bdw_analysis_prod.kg_poc.shield_document"
)
SHIELD_PASSAGE_TABLE = (
    "bdw_analysis_prod.kg_poc.shield_passage"
)

SOURCE_LAYER = "SHIELD_TAXONOMY"
INDEX_VERSION = "IKF_SHIELD_CORPUS_V0.1"
CHUNKING_VERSION = "SHIELD_PAGE_CHUNK_V0.1"

SUPPORTED_SUFFIXES = {
    ".pdf",
    ".txt",
    ".md",
    ".docx",
}

if not SHIELD_ROOT.startswith("/Volumes/"):
    raise ValueError(
        "shield_root must be a Unity Catalog volume path."
    )

# COMMAND ----------

document_schema = StructType(
    [
        StructField("shield_document_id", StringType(), False),
        StructField("filename", StringType(), False),
        StructField("file_path", StringType(), False),
        StructField("file_sha256", StringType(), False),
        StructField("source_type", StringType(), False),
        StructField("source_layer", StringType(), False),
        StructField("page_count", IntegerType(), True),
        StructField("index_version", StringType(), False),
        StructField("corpus_snapshot_id", StringType(), False),
        StructField("indexed_at", TimestampType(), False),
    ]
)

passage_schema = StructType(
    [
        StructField("shield_document_id", StringType(), False),
        StructField("shield_passage_id", StringType(), False),
        StructField("passage_number", IntegerType(), False),
        StructField("page_start", IntegerType(), True),
        StructField("page_end", IntegerType(), True),
        StructField("passage_text", StringType(), False),
        StructField("passage_text_sha256", StringType(), False),
        StructField("source_layer", StringType(), False),
        StructField("chunking_version", StringType(), False),
        StructField("corpus_snapshot_id", StringType(), False),
        StructField("created_at", TimestampType(), False),
    ]
)

# COMMAND ----------

def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def split_text(text, max_chars=4000):
    text = str(text or "").strip()
    if not text:
        return []

    paragraphs = [
        item.strip()
        for item in re.split(
            r"\n\s*\n",
            text,
        )
        if item.strip()
    ]

    chunks = []
    current = ""

    for paragraph in paragraphs:
        proposed = (
            paragraph
            if not current
            else current + "\n\n" + paragraph
        )

        if len(proposed) <= max_chars:
            current = proposed
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(paragraph) <= max_chars:
            current = paragraph
        else:
            for start in range(
                0,
                len(paragraph),
                max_chars,
            ):
                chunks.append(
                    paragraph[
                        start:start + max_chars
                    ]
                )

    if current:
        chunks.append(current)

    return chunks


def extract_pages(path):
    suffix = Path(path).suffix.casefold()

    if suffix == ".pdf":
        pdf = fitz.open(path)
        try:
            return [
                {
                    "page_number": index + 1,
                    "text": pdf[index].get_text(
                        "text"
                    ),
                }
                for index in range(
                    pdf.page_count
                )
            ]
        finally:
            pdf.close()

    if suffix in {".txt", ".md"}:
        with open(
            path,
            "r",
            encoding="utf-8",
        ) as handle:
            return [
                {
                    "page_number": 1,
                    "text": handle.read(),
                }
            ]

    if suffix == ".docx":
        doc = DocxDocument(path)
        return [
            {
                "page_number": 1,
                "text": "\n".join(
                    paragraph.text
                    for paragraph
                    in doc.paragraphs
                    if paragraph.text.strip()
                ),
            }
        ]

    return []

# COMMAND ----------

if not os.path.isdir(SHIELD_ROOT):
    print("SHIELD folder not found:")
    print(SHIELD_ROOT)
    dbutils.notebook.exit(
        "SHIELD_ROOT_NOT_FOUND"
    )

paths = sorted(
    str(path)
    for path in Path(SHIELD_ROOT).rglob("*")
    if path.is_file()
    and path.suffix.casefold()
    in SUPPORTED_SUFFIXES
)

print("SHIELD files:", len(paths))

if not paths:
    dbutils.notebook.exit(
        "NO_SHIELD_DOCUMENTS"
    )

file_records = [
    {
        "path": path,
        "filename": os.path.basename(path),
        "sha256": sha256_file(path),
    }
    for path in paths
]

snapshot_payload = [
    {
        "filename": item["filename"],
        "sha256": item["sha256"],
    }
    for item in file_records
]

corpus_snapshot_id = (
    "shield_snapshot_"
    + hashlib.sha256(
        json.dumps(
            snapshot_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:32]
)

print(
    "SHIELD corpus snapshot:",
    corpus_snapshot_id,
)

# COMMAND ----------

created_at = datetime.now(timezone.utc)
document_rows = []
passage_rows = []

for item in file_records:
    path = item["path"]
    filename = item["filename"]
    file_sha256 = item["sha256"]

    shield_document_id = (
        "shield_doc_"
        + file_sha256[:24]
    )

    pages = extract_pages(path)
    passage_number = 0

    for page in pages:
        for chunk in split_text(
            page["text"]
        ):
            passage_number += 1
            text_hash = hashlib.sha256(
                chunk.encode("utf-8")
            ).hexdigest()
            passage_id = (
                "shield_passage_"
                + hashlib.sha256(
                    (
                        shield_document_id
                        + "|"
                        + str(
                            page[
                                "page_number"
                            ]
                        )
                        + "|"
                        + str(passage_number)
                        + "|"
                        + text_hash
                    ).encode("utf-8")
                ).hexdigest()[:24]
            )

            passage_rows.append(
                Row(
                    shield_document_id=shield_document_id,
                    shield_passage_id=passage_id,
                    passage_number=passage_number,
                    page_start=page[
                        "page_number"
                    ],
                    page_end=page[
                        "page_number"
                    ],
                    passage_text=chunk,
                    passage_text_sha256=text_hash,
                    source_layer=SOURCE_LAYER,
                    chunking_version=CHUNKING_VERSION,
                    corpus_snapshot_id=corpus_snapshot_id,
                    created_at=created_at,
                )
            )

    document_rows.append(
        Row(
            shield_document_id=shield_document_id,
            filename=filename,
            file_path=path,
            file_sha256=file_sha256,
            source_type=(
                Path(path)
                .suffix
                .lstrip(".")
                .upper()
            ),
            source_layer=SOURCE_LAYER,
            page_count=len(pages),
            index_version=INDEX_VERSION,
            corpus_snapshot_id=corpus_snapshot_id,
            indexed_at=created_at,
        )
    )

print(
    "SHIELD documents prepared:",
    len(document_rows),
)
print(
    "SHIELD passages prepared:",
    len(passage_rows),
)

# COMMAND ----------

spark.createDataFrame(
    document_rows,
    schema=document_schema,
).createOrReplaceTempView(
    "tmp_shield_document"
)

spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS
        {SHIELD_DOCUMENT_TABLE}
    USING DELTA
    AS
    SELECT *
    FROM tmp_shield_document
    WHERE 1 = 0
    """
)

spark.sql(
    f"""
    MERGE INTO {SHIELD_DOCUMENT_TABLE} t
    USING tmp_shield_document s
    ON t.shield_document_id = s.shield_document_id
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
    """
)

spark.createDataFrame(
    passage_rows,
    schema=passage_schema,
).createOrReplaceTempView(
    "tmp_shield_passage"
)

spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS
        {SHIELD_PASSAGE_TABLE}
    USING DELTA
    AS
    SELECT *
    FROM tmp_shield_passage
    WHERE 1 = 0
    """
)

spark.sql(
    f"""
    MERGE INTO {SHIELD_PASSAGE_TABLE} t
    USING tmp_shield_passage s
    ON t.shield_passage_id = s.shield_passage_id
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
    """
)

# COMMAND ----------

# Compact metadata only in Neo4j.
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
    auth=(
        NEO4J_USERNAME,
        NEO4J_PASSWORD,
    ),
)
driver.verify_connectivity()

with driver.session() as session:
    session.run(
        """
        CREATE CONSTRAINT shield_document_id_unique
        IF NOT EXISTS
        FOR (d:ShieldDocument)
        REQUIRE d.shield_document_id IS UNIQUE
        """
    ).consume()

    for row in document_rows:
        values = row.asDict(
            recursive=True
        )
        session.run(
            """
            MERGE (d:ShieldDocument {
                shield_document_id:
                    $shield_document_id
            })
            SET
                d.filename = $filename,
                d.file_path = $file_path,
                d.file_sha256 = $file_sha256,
                d.source_type = $source_type,
                d.source_layer = 'SHIELD_TAXONOMY',
                d.page_count = $page_count,
                d.index_version = $index_version,
                d.corpus_snapshot_id =
                    $corpus_snapshot_id,
                d.viewer_source_repository =
                    'IKF_SHIELD',
                d.viewer_source_path =
                    $file_path,
                d.viewer_source_filename =
                    $filename,
                d.catalogue_status =
                    'AVAILABLE',
                d.retention_policy =
                    'PERSISTENT_GOVERNED_RESOURCE',
                d.indexed_at = datetime()
            """,
            **values,
        ).consume()

driver.close()

print("")
print(
    "PASS — PERSISTENT SHIELD CORPUS INDEXED"
)
print(
    "snapshot:",
    corpus_snapshot_id,
)
print(
    "documents:",
    len(document_rows),
)
print(
    "passages:",
    len(passage_rows),
)
