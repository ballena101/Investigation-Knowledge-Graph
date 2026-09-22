# Databricks notebook source
# MAGIC %md
# MAGIC # 44 — Index IKF authoritative REFERENCE_CONTEXT
# MAGIC
# MAGIC Builds a governed REFERENCE_CONTEXT corpus from:
# MAGIC
# MAGIC 1. the Git-governed authoritative-source registry
# MAGIC    `config/reference_sources.json`; and
# MAGIC 2. optional manually supplied PDF/TXT/MD/DOCX files in the reference
# MAGIC    volume.
# MAGIC
# MAGIC Registry URLs remain the authoritative provenance. Remote content is
# MAGIC snapshotted into the governed Volume and indexed from that immutable
# MAGIC captured content so retrieval remains reproducible and page-citable.
# MAGIC
# MAGIC REFERENCE_CONTEXT remains separate from SOURCE_EVIDENCE, EMCIP
# MAGIC CONTROLLED_TAXONOMY and SHIELD.

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1 pymupdf==1.26.4 python-docx==1.2.0

# COMMAND ----------

import hashlib
import json
import os
import re
import urllib.request
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

REFERENCE_VOLUME_ROOT = (
    "/Volumes/bdw_analysis_prod/kg_poc/reference_context"
)
SNAPSHOT_ROOT = os.path.join(
    REFERENCE_VOLUME_ROOT,
    "_snapshots",
)
REFERENCE_DOCUMENT_TABLE = (
    "bdw_analysis_prod.kg_poc.reference_document"
)
REFERENCE_PASSAGE_TABLE = (
    "bdw_analysis_prod.kg_poc.reference_passage"
)

SOURCE_LAYER = "REFERENCE_CONTEXT"
INDEX_VERSION = "IKF_REFERENCE_CONTEXT_V0.2"
CHUNKING_VERSION = "REFERENCE_PAGE_CHUNK_V0.1"
REGISTRY_VERSION_EXPECTED = "IKF_REFERENCE_SOURCE_REGISTRY_V0.1"

SUPPORTED_SUFFIXES = {
    ".pdf",
    ".txt",
    ".md",
    ".docx",
}

# Resolve the Git-backed registry next to this notebook's repository.
current_notebook = (
    dbutils.notebook.entry_point
    .getDbutils()
    .notebook()
    .getContext()
    .notebookPath()
    .get()
)
repo_root = current_notebook.rsplit(
    "/notebooks/",
    1,
)[0]
REGISTRY_PATH = (
    "/Workspace"
    + repo_root
    + "/config/reference_sources.json"
)

# COMMAND ----------

document_schema = StructType(
    [
        StructField("reference_document_id", StringType(), False),
        StructField("registry_key", StringType(), True),
        StructField("filename", StringType(), False),
        StructField("file_path", StringType(), False),
        StructField("file_sha256", StringType(), False),
        StructField("source_type", StringType(), False),
        StructField("source_layer", StringType(), False),
        StructField("source_authority", StringType(), True),
        StructField("canonical_url", StringType(), True),
        StructField("snapshot_url", StringType(), True),
        StructField("retrieval_origin", StringType(), False),
        StructField("source_language", StringType(), True),
        StructField("reference_family", StringType(), False),
        StructField("reference_code", StringType(), True),
        StructField("reference_title", StringType(), True),
        StructField("page_count", IntegerType(), True),
        StructField("index_version", StringType(), False),
        StructField("retrieved_at", TimestampType(), True),
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


def download_snapshot(source):
    snapshot_url = str(
        source.get("snapshot_url")
        or ""
    ).strip()
    filename = str(
        source.get("snapshot_filename")
        or ""
    ).strip()

    if not snapshot_url or not filename:
        raise ValueError(
            "Registry source requires snapshot_url and snapshot_filename: "
            + str(source.get("registry_key"))
        )

    request = urllib.request.Request(
        snapshot_url,
        headers={
            "User-Agent": (
                "IKF-ReferenceContext/0.2 "
                "(governed evidence snapshot)"
            )
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=60,
    ) as response:
        data = response.read()

    if not data:
        raise ValueError(
            "Downloaded empty authoritative source: "
            + snapshot_url
        )

    expected_type = str(
        source.get("source_type")
        or ""
    ).upper()

    if (
        expected_type == "PDF"
        and not data.startswith(b"%PDF")
    ):
        raise ValueError(
            "Authoritative snapshot is not a PDF: "
            + snapshot_url
        )

    os.makedirs(
        SNAPSHOT_ROOT,
        exist_ok=True,
    )
    path = os.path.join(
        SNAPSHOT_ROOT,
        filename,
    )

    with open(path, "wb") as handle:
        handle.write(data)

    return path, data


def load_registry():
    if not os.path.isfile(REGISTRY_PATH):
        raise FileNotFoundError(
            "Reference-source registry not found: "
            + REGISTRY_PATH
        )

    with open(
        REGISTRY_PATH,
        "r",
        encoding="utf-8",
    ) as handle:
        payload = json.load(handle)

    version = payload.get(
        "registry_version"
    )

    if version != REGISTRY_VERSION_EXPECTED:
        raise ValueError(
            "Unexpected reference registry version: "
            + str(version)
        )

    sources = payload.get("sources") or []

    keys = [
        source.get("registry_key")
        for source in sources
    ]

    if (
        not sources
        or any(not key for key in keys)
        or len(keys) != len(set(keys))
    ):
        raise ValueError(
            "Reference registry must contain unique non-empty registry_key values."
        )

    return sources

# COMMAND ----------

if not os.path.isdir(REFERENCE_VOLUME_ROOT):
    print("Reference-context volume does not exist yet:")
    print(REFERENCE_VOLUME_ROOT)
    dbutils.notebook.exit("REFERENCE_CONTEXT_ROOT_NOT_FOUND")

registry_sources = load_registry()

print(
    "Authoritative registry sources:",
    len(registry_sources),
)
print(
    "Registry:",
    REGISTRY_PATH,
)

retrieved_at = datetime.now(timezone.utc)

prepared_sources = []

for source in registry_sources:
    path, file_bytes = download_snapshot(
        source
    )

    prepared_sources.append(
        {
            "path": path,
            "file_bytes": file_bytes,
            "registry_key": source["registry_key"],
            "source_authority": source.get(
                "source_authority"
            ),
            "canonical_url": source.get(
                "canonical_url"
            ),
            "snapshot_url": source.get(
                "snapshot_url"
            ),
            "retrieval_origin": "AUTHORITATIVE_URL",
            "source_language": source.get(
                "language"
            ),
            "reference_family": source.get(
                "reference_family"
            ),
            "reference_code": source.get(
                "reference_code"
            ),
            "reference_title": source.get(
                "reference_title"
            ),
            "source_type": source.get(
                "source_type"
            ),
            "retrieved_at": retrieved_at,
        }
    )

# Optional manually governed files remain supported. Snapshot files created
# above are deliberately excluded from this scan to avoid duplicate documents.
manual_paths = sorted(
    str(path)
    for path in Path(REFERENCE_VOLUME_ROOT).rglob("*")
    if path.is_file()
    and "_snapshots" not in path.parts
    and path.suffix.casefold() in SUPPORTED_SUFFIXES
)

for path in manual_paths:
    with open(path, "rb") as handle:
        file_bytes = handle.read()

    family, code, title = classify_reference(
        os.path.basename(path)
    )

    prepared_sources.append(
        {
            "path": path,
            "file_bytes": file_bytes,
            "registry_key": None,
            "source_authority": None,
            "canonical_url": None,
            "snapshot_url": None,
            "retrieval_origin": "GOVERNED_LOCAL_FILE",
            "source_language": None,
            "reference_family": family,
            "reference_code": code,
            "reference_title": title,
            "source_type": Path(path).suffix.lstrip(".").upper(),
            "retrieved_at": None,
        }
    )

print(
    "Manual governed files:",
    len(manual_paths),
)
print(
    "Total reference sources prepared:",
    len(prepared_sources),
)

if not prepared_sources:
    dbutils.notebook.exit(
        "NO_REFERENCE_CONTEXT_DOCUMENTS"
    )

# COMMAND ----------

indexed_at = datetime.now(timezone.utc)
document_rows = []
passage_rows = []

for source in prepared_sources:
    path = source["path"]
    file_bytes = source["file_bytes"]
    file_sha256 = sha256_bytes(
        file_bytes
    )
    filename = os.path.basename(path)

    identity_seed = (
        str(source.get("registry_key") or "LOCAL")
        + "|"
        + file_sha256
    )

    reference_document_id = (
        "refdoc_"
        + hashlib.sha256(
            identity_seed.encode("utf-8")
        ).hexdigest()[:24]
    )

    pages = extract_pages(path)
    passage_number = 0

    for page in pages:
        page_number = page["page_number"]

        for chunk in split_text(
            page["text"]
        ):
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
                    created_at=indexed_at,
                )
            )

    document_rows.append(
        Row(
            reference_document_id=reference_document_id,
            registry_key=source.get(
                "registry_key"
            ),
            filename=filename,
            file_path=path,
            file_sha256=file_sha256,
            source_type=str(
                source.get("source_type")
                or Path(path).suffix.lstrip(".")
            ).upper(),
            source_layer=SOURCE_LAYER,
            source_authority=source.get(
                "source_authority"
            ),
            canonical_url=source.get(
                "canonical_url"
            ),
            snapshot_url=source.get(
                "snapshot_url"
            ),
            retrieval_origin=source[
                "retrieval_origin"
            ],
            source_language=source.get(
                "source_language"
            ),
            reference_family=source[
                "reference_family"
            ],
            reference_code=source.get(
                "reference_code"
            ),
            reference_title=source.get(
                "reference_title"
            ),
            page_count=len(pages),
            index_version=INDEX_VERSION,
            retrieved_at=source.get(
                "retrieved_at"
            ),
            indexed_at=indexed_at,
        )
    )

print(
    "Reference documents prepared:",
    len(document_rows),
)
print(
    "Reference passages prepared:",
    len(passage_rows),
)

# COMMAND ----------

spark.createDataFrame(
    document_rows,
    schema=document_schema,
).createOrReplaceTempView(
    "tmp_ikf_reference_document"
)

if not spark.catalog.tableExists(
    REFERENCE_DOCUMENT_TABLE
):
    spark.sql(
        f"""
        CREATE TABLE {REFERENCE_DOCUMENT_TABLE}
        USING DELTA
        AS
        SELECT *
        FROM tmp_ikf_reference_document
        WHERE 1 = 0
        """
    )
else:
    existing_columns = {
        field.name
        for field in spark.table(
            REFERENCE_DOCUMENT_TABLE
        ).schema.fields
    }
    required_column_sql = {
        "registry_key": "STRING",
        "source_authority": "STRING",
        "canonical_url": "STRING",
        "snapshot_url": "STRING",
        "retrieval_origin": "STRING",
        "source_language": "STRING",
        "retrieved_at": "TIMESTAMP",
    }

    for column_name, column_type in required_column_sql.items():
        if column_name not in existing_columns:
            spark.sql(
                f"""
                ALTER TABLE {REFERENCE_DOCUMENT_TABLE}
                ADD COLUMNS ({column_name} {column_type})
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

# Mirror compact reference metadata into Neo4j for App catalogue and viewer
# resolution only. Passage text remains governed in Delta.

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
        CREATE CONSTRAINT reference_document_id_unique
        IF NOT EXISTS
        FOR (d:ReferenceDocument)
        REQUIRE d.reference_document_id IS UNIQUE
        """
    ).consume()

    for row in document_rows:
        values = row.asDict(
            recursive=True
        )
        session.run(
            """
            MERGE (d:ReferenceDocument {
                reference_document_id: $reference_document_id
            })
            SET
                d.registry_key = $registry_key,
                d.filename = $filename,
                d.file_path = $file_path,
                d.file_sha256 = $file_sha256,
                d.source_type = $source_type,
                d.source_layer = 'REFERENCE_CONTEXT',
                d.source_authority = $source_authority,
                d.canonical_url = $canonical_url,
                d.snapshot_url = $snapshot_url,
                d.retrieval_origin = $retrieval_origin,
                d.source_language = $source_language,
                d.reference_family = $reference_family,
                d.reference_code = $reference_code,
                d.reference_title = $reference_title,
                d.page_count = $page_count,
                d.index_version = $index_version,
                d.viewer_source_repository = 'IKF',
                d.viewer_source_path = $file_path,
                d.viewer_source_filename = $filename,
                d.catalogue_status = 'AVAILABLE',
                d.retrieved_at = $retrieved_at,
                d.indexed_at = datetime()
            """,
            **values,
        ).consume()

driver.close()

# COMMAND ----------

print("")
print(
    "PASS — IKF AUTHORITATIVE REFERENCE_CONTEXT CORPUS INDEXED"
)
print(
    "Registry version:",
    REGISTRY_VERSION_EXPECTED,
)
print(
    "Authoritative URL sources:",
    len(registry_sources),
)
print(
    "Manual governed sources:",
    len(manual_paths),
)
print(
    "Documents:",
    len(document_rows),
)
print(
    "Passages:",
    len(passage_rows),
)
print(
    "Snapshot root:",
    SNAPSHOT_ROOT,
)
print(
    "Source layer:",
    SOURCE_LAYER,
)
