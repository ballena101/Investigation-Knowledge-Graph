# Databricks notebook source
# MAGIC %md
# MAGIC # 44 — Index IKF reference-context documents
# MAGIC
# MAGIC Creates a governed REFERENCE_CONTEXT corpus for legal, IMO and
# MAGIC methodological/technical reference material.
# MAGIC
# MAGIC This corpus is deliberately separate from:
# MAGIC - occurrence SOURCE_EVIDENCE;
# MAGIC - EMCIP CONTROLLED_TAXONOMY;
# MAGIC - SHIELD classification material.
# MAGIC
# MAGIC Expected volume root:
# MAGIC `/Volumes/bdw_analysis_prod/kg_poc/reference_context`
# MAGIC
# MAGIC The notebook is safe to run when the folder does not yet exist: it
# MAGIC reports the missing source root and exits without modifying case data.

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1 pymupdf==1.26.4 python-docx==1.2.0

# COMMAND ----------

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import fitz
from docx import Document as DocxDocument
from neo4j import GraphDatabase
from pyspark.sql import Row
from pyspark.sql import functions as F
from pyspark.sql.types import (
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

REFERENCE_VOLUME_ROOT = (
    "/Volumes/bdw_analysis_prod/kg_poc/reference_context"
)
REFERENCE_DOCUMENT_TABLE = (
    "bdw_analysis_prod.kg_poc.reference_document"
)
REFERENCE_PASSAGE_TABLE = (
    "bdw_analysis_prod.kg_poc.reference_passage"
)

SOURCE_LAYER = "REFERENCE_CONTEXT"
INDEX_VERSION = "IKF_REFERENCE_CONTEXT_V0.1"
CHUNKING_VERSION = "REFERENCE_PAGE_CHUNK_V0.1"

SUPPORTED_SUFFIXES = {
    ".pdf",
    ".txt",
    ".md",
    ".docx",
}

# COMMAND ----------

document_schema = StructType(
    [
        StructField("reference_document_id", StringType(), False),
        StructField("filename", StringType(), False),
        StructField("file_path", StringType(), False),
        StructField("file_sha256", StringType(), False),
        StructField("source_type", StringType(), False),
        StructField("source_layer", StringType(), False),
        StructField("reference_family", StringType(), False),
        StructField("reference_code", StringType(), True),
        StructField("reference_title", StringType(), True),
        StructField("page_count", IntegerType(), True),
        StructField("index_version", StringType(), False),
        StructField("indexed_at", TimestampType(), False),
    ]
)

passage_schema = StructType(
    [
        StructField("reference_document_id", StringType(), False),
        StructField("reference_passage_id", StringType(), False),
        StructField("passage_number", IntegerType(), False),
        StructField("page_start", IntegerType(), True),
        StructField("page_end", IntegerType(), True),
        StructField("passage_text", StringType(), False),
        StructField("passage_text_sha256", StringType(), False),
        StructField("source_layer", StringType(), False),
        StructField("chunking_version", StringType(), False),
        StructField("created_at", TimestampType(), False),
    ]
)

# COMMAND ----------

def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def classify_reference(filename):
    name = filename.casefold()

    if "2009_18" in name or "2009-18" in name or "2009 18" in name:
        return (
            "EU_LEGISLATION",
            "Directive 2009/18/EC",
            "Directive 2009/18/EC",
        )

    if "2024_3017" in name or "2024-3017" in name or "2024 3017" in name:
        return (
            "EU_LEGISLATION",
            "Directive (EU) 2024/3017",
            "Directive (EU) 2024/3017",
        )

    if "msc.255" in name or "msc255" in name or "msc_255" in name:
        return (
            "IMO_FRAMEWORK",
            "MSC.255(84)",
            "Casualty Investigation Code",
        )

    if "a.1075" in name or "a1075" in name or "a_1075" in name:
        return (
            "IMO_FRAMEWORK",
            "A.1075(28)",
            "IMO Guidelines A.1075(28)",
        )

    return (
        "TECHNICAL_REFERENCE",
        None,
        Path(filename).stem.replace("_", " "),
    )


def split_text(text, max_chars=4500):
    normalized = "\n".join(
        line.rstrip()
        for line in str(text or "").splitlines()
    ).strip()

    if not normalized:
        return []

    paragraphs = [
        value.strip()
        for value in re.split(r"\n\s*\n", normalized)
        if value.strip()
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
            continue

        start = 0
        while start < len(paragraph):
            chunks.append(
                paragraph[start:start + max_chars]
            )
            start += max_chars

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
                    "text": pdf[index].get_text("text"),
                }
                for index in range(pdf.page_count)
            ]
        finally:
            pdf.close()

    if suffix in {".txt", ".md"}:
        with open(path, "r", encoding="utf-8") as handle:
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
                    for paragraph in doc.paragraphs
                    if paragraph.text.strip()
                ),
            }
        ]

    return []

# COMMAND ----------

if not os.path.isdir(REFERENCE_VOLUME_ROOT):
    print("Reference-context volume does not exist yet:")
    print(REFERENCE_VOLUME_ROOT)
    print("")
    print("Create it and place governed legal/IMO/technical reference files there.")
    dbutils.notebook.exit("REFERENCE_CONTEXT_ROOT_NOT_FOUND")

paths = sorted(
    str(path)
    for path in Path(REFERENCE_VOLUME_ROOT).rglob("*")
    if path.is_file()
    and path.suffix.casefold() in SUPPORTED_SUFFIXES
)

print("Reference files found:", len(paths))

if not paths:
    dbutils.notebook.exit("NO_REFERENCE_CONTEXT_DOCUMENTS")

# COMMAND ----------

created_at = datetime.now(timezone.utc)
document_rows = []
passage_rows = []

for path in paths:
    with open(path, "rb") as handle:
        file_bytes = handle.read()

    file_sha256 = sha256_bytes(file_bytes)
    filename = os.path.basename(path)

    reference_document_id = (
        "refdoc_" + file_sha256[:24]
    )

    family, code, title = classify_reference(
        filename
    )

    pages = extract_pages(path)
    passage_number = 0

    for page in pages:
        page_number = page["page_number"]

        for chunk in split_text(page["text"]):
            passage_number += 1
            text_hash = hashlib.sha256(
                chunk.encode("utf-8")
            ).hexdigest()
            passage_id = (
                "refpassage_"
                + hashlib.sha256(
                    (
                        reference_document_id
                        + "|"
                        + str(page_number)
                        + "|"
                        + str(passage_number)
                        + "|"
                        + text_hash
                    ).encode("utf-8")
                ).hexdigest()[:24]
            )

            passage_rows.append(
                Row(
                    reference_document_id=reference_document_id,
                    reference_passage_id=passage_id,
                    passage_number=passage_number,
                    page_start=page_number,
                    page_end=page_number,
                    passage_text=chunk,
                    passage_text_sha256=text_hash,
                    source_layer=SOURCE_LAYER,
                    chunking_version=CHUNKING_VERSION,
                    created_at=created_at,
                )
            )

    document_rows.append(
        Row(
            reference_document_id=reference_document_id,
            filename=filename,
            file_path=path,
            file_sha256=file_sha256,
            source_type=Path(path).suffix.lstrip(".").upper(),
            source_layer=SOURCE_LAYER,
            reference_family=family,
            reference_code=code,
            reference_title=title,
            page_count=len(pages),
            index_version=INDEX_VERSION,
            indexed_at=created_at,
        )
    )

print("Reference documents prepared:", len(document_rows))
print("Reference passages prepared:", len(passage_rows))

# COMMAND ----------

spark.createDataFrame(
    document_rows,
    schema=document_schema,
).createOrReplaceTempView(
    "tmp_ikf_reference_document"
)

spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {REFERENCE_DOCUMENT_TABLE}
    USING DELTA
    AS
    SELECT *
    FROM tmp_ikf_reference_document
    WHERE 1 = 0
    """
)

spark.sql(
    f"""
    MERGE INTO {REFERENCE_DOCUMENT_TABLE} target
    USING tmp_ikf_reference_document source
    ON target.reference_document_id = source.reference_document_id
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
    """
)

spark.createDataFrame(
    passage_rows,
    schema=passage_schema,
).createOrReplaceTempView(
    "tmp_ikf_reference_passage"
)

spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {REFERENCE_PASSAGE_TABLE}
    USING DELTA
    AS
    SELECT *
    FROM tmp_ikf_reference_passage
    WHERE 1 = 0
    """
)

spark.sql(
    f"""
    MERGE INTO {REFERENCE_PASSAGE_TABLE} target
    USING tmp_ikf_reference_passage source
    ON target.reference_passage_id = source.reference_passage_id
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
    """
)

# COMMAND ----------

# Mirror compact reference metadata into Neo4j for App discovery only.
# Passage text remains in Delta.

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
    session.run(
        """
        CREATE CONSTRAINT reference_document_id_unique
        IF NOT EXISTS
        FOR (d:ReferenceDocument)
        REQUIRE d.reference_document_id IS UNIQUE
        """
    ).consume()

    for row in document_rows:
        values = row.asDict(recursive=True)
        session.run(
            """
            MERGE (d:ReferenceDocument {
                reference_document_id: $reference_document_id
            })
            SET
                d.filename = $filename,
                d.file_path = $file_path,
                d.file_sha256 = $file_sha256,
                d.source_type = $source_type,
                d.source_layer = 'REFERENCE_CONTEXT',
                d.reference_family = $reference_family,
                d.reference_code = $reference_code,
                d.reference_title = $reference_title,
                d.page_count = $page_count,
                d.index_version = $index_version,
                d.viewer_source_repository = 'IKF',
                d.viewer_source_path = $file_path,
                d.viewer_source_filename = $filename,
                d.catalogue_status = 'AVAILABLE',
                d.indexed_at = datetime()
            """,
            **values,
        ).consume()

driver.close()

print("")
print("PASS — IKF REFERENCE_CONTEXT CORPUS INDEXED")
print("Documents:", len(document_rows))
print("Passages:", len(passage_rows))
print("Source layer:", SOURCE_LAYER)
