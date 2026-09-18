# Databricks notebook source
# MAGIC %md
# MAGIC # 14 — Index volume documents to Neo4j
# MAGIC
# MAGIC Scans a Unity Catalog volume folder under the current Databricks user's
# MAGIC permissions and publishes **document metadata only** to Neo4j.
# MAGIC
# MAGIC The App never needs access to the source files themselves.
# MAGIC
# MAGIC Default library:
# MAGIC
# MAGIC `/Volumes/bdw_analysis_prod/kg_poc/investigation_sources`

# COMMAND ----------

dbutils.widgets.text(
    "library_root",
    "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources",
    "Document library root",
)

library_root = dbutils.widgets.get("library_root").strip().rstrip("/")

if not library_root.startswith("/Volumes/"):
    raise ValueError(
        "library_root must be a Unity Catalog volume path beginning with "
        "'/Volumes/'."
    )

print("Document library:", library_root)

# COMMAND ----------

import hashlib
import mimetypes
import os
from datetime import datetime, timezone

from neo4j import GraphDatabase

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
}

# Prefer existing notebook variables if they are already defined.
try:
    NEO4J_URI
    NEO4J_USERNAME
    NEO4J_PASSWORD
except NameError:
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

def sha256_file(path, chunk_size=1024 * 1024):
    digest = hashlib.sha256()

    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


def discover_documents(root):
    rows = []

    for current_root, _, filenames in os.walk(root):
        for filename in filenames:
            if filename == "manifest.json":
                continue

            extension = os.path.splitext(filename)[1].lower()

            if extension not in SUPPORTED_EXTENSIONS:
                continue

            path = os.path.join(current_root, filename)

            if not os.path.isfile(path):
                continue

            stat = os.stat(path)
            sha256 = sha256_file(path)
            document_id = f"doc_{sha256[:24]}"
            mime_type, _ = mimetypes.guess_type(filename)

            relative_path = os.path.relpath(
                path,
                root,
            )

            rows.append(
                {
                    "document_id": document_id,
                    "filename": filename,
                    "volume_path": path,
                    "relative_path": relative_path,
                    "library_root": root,
                    "source_type": (
                        extension.lstrip(".").upper()
                    ),
                    "mime_type": mime_type,
                    "byte_size": stat.st_size,
                    "sha256": sha256,
                    "file_modified_at": datetime.fromtimestamp(
                        stat.st_mtime,
                        tz=timezone.utc,
                    ).isoformat(),
                }
            )

    return sorted(
        rows,
        key=lambda row: (
            row["filename"].lower(),
            row["volume_path"],
        ),
    )


documents = discover_documents(library_root)

print("Supported documents found:", len(documents))

for document in documents:
    print(
        " -",
        document["filename"],
        "→",
        document["document_id"],
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
    )

    session.run(
        """
        CREATE CONSTRAINT analysis_group_id_unique
        IF NOT EXISTS
        FOR (a:AnalysisGroup)
        REQUIRE a.analysis_id IS UNIQUE
        """
    )

print("Neo4j constraints: ready")

# COMMAND ----------

INDEX_VERSION = "SOURCE_LIBRARY_V0.1"

query = """
MERGE (d:SourceDocument {document_id: $document_id})
ON CREATE SET
    d.first_indexed_at = datetime()
SET
    d.filename = $filename,
    d.volume_path = $volume_path,
    d.relative_path = $relative_path,
    d.library_root = $library_root,
    d.source_type = $source_type,
    d.mime_type = $mime_type,
    d.byte_size = $byte_size,
    d.sha256 = $sha256,
    d.file_modified_at = $file_modified_at,
    d.index_version = $index_version,
    d.indexed_at = datetime(),
    d.catalogue_status = 'AVAILABLE'
RETURN d.document_id AS document_id
"""

indexed_ids = []

with driver.session() as session:
    for document in documents:
        params = dict(document)
        params["index_version"] = INDEX_VERSION

        record = session.run(
            query,
            **params,
        ).single()

        if record:
            indexed_ids.append(record["document_id"])

print("Indexed documents:", len(indexed_ids))

# COMMAND ----------

with driver.session() as session:
    rows = [
        record.data()
        for record in session.run(
            """
            MATCH (d:SourceDocument)
            WHERE d.library_root = $library_root
            RETURN
                d.document_id AS document_id,
                d.filename AS filename,
                d.relative_path AS relative_path,
                d.source_type AS source_type,
                d.byte_size AS byte_size,
                d.detected_language AS detected_language,
                toString(d.indexed_at) AS indexed_at
            ORDER BY d.filename, d.relative_path
            """,
            library_root=library_root,
        )
    ]

display(spark.createDataFrame(rows))

# COMMAND ----------

driver.close()

print("")
print("DOCUMENT LIBRARY READY")
print("Documents available to App:", len(indexed_ids))
print("")
print(
    "Next: redeploy/open the App and use New analysis → "
    "Available documents."
)
