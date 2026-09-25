# Databricks notebook source
# MAGIC %md
# MAGIC # 55 — Reconcile MAIRA PDFs, registry, passages and IKF catalogue
# MAGIC
# MAGIC Read-only inventory. It identifies PDFs present in the MAIRA source
# MAGIC Volume but absent from `maira.documents`, registered reports without
# MAGIC passages, and MAIRA documents absent from the IKF Neo4j selector.
# MAGIC No sync, download, table write, model call or App deployment occurs.

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1

# COMMAND ----------

from collections import deque
import pandas as pd
from neo4j import GraphDatabase
from pyspark.sql import functions as F

DOCUMENTS = "bdw_analysis_prod.maira.documents"
PASSAGES = "bdw_analysis_prod.maira.passages"
ROOT = "/Volumes/bdw_analysis_prod/maira/source_documents/investigation_reports"
MAX_ENTRIES = 50000

for table in (DOCUMENTS, PASSAGES):
    if not spark.catalog.tableExists(table):
        raise RuntimeError(f"Required MAIRA table is missing: {table}")

docs = (
    spark.table(DOCUMENTS)
    .filter(F.col("corpus_type") == "INVESTIGATION")
    .select(
        "document_id", "report_package_id", "document_role", "country_code",
        "investigation_body", "report_title", "source_filename", "file_path",
        "processing_status", "sha256",
    )
    .collect()
)
counts = {
    row["document_id"]: int(row["passage_count"])
    for row in (
        spark.table(PASSAGES)
        .groupBy("document_id")
        .agg(F.countDistinct("passage_id").alias("passage_count"))
        .collect()
    )
}
doc_by_id = {row["document_id"]: row.asDict() for row in docs}
if len(doc_by_id) != len(docs):
    raise RuntimeError("MAIRA registry has duplicate document IDs.")

# COMMAND ----------

driver = GraphDatabase.driver(
    dbutils.secrets.get(scope="kg-poc-app", key="neo4j_uri"),
    auth=(
        dbutils.secrets.get(scope="kg-poc-app", key="neo4j_username"),
        dbutils.secrets.get(scope="kg-poc-app", key="neo4j_password"),
    ),
)
try:
    driver.verify_connectivity()
    with driver.session() as session:
        ikf = {
            row["document_id"]: row.data()
            for row in session.run("""
                MATCH (d:SourceDocument)
                WHERE d.source_managed_by = 'MAIRA'
                RETURN d.document_id AS document_id,
                       d.catalogue_status AS catalogue_status,
                       d.sha256 AS sha256,
                       d.viewer_source_path AS viewer_source_path,
                       d.maira_document_role AS document_role
            """)
        }
finally:
    driver.close()

# COMMAND ----------

# Walk only the MAIRA investigation-report Volume. The cap prevents an
# accidental unbounded inventory on a large production Volume.
def volume_path(path):
    return path.removeprefix("dbfs:").rstrip("/")


queue = deque([ROOT])
pdf_paths = set()
entries_seen = 0
while queue:
    folder = queue.popleft()
    for entry in dbutils.fs.ls(folder):
        entries_seen += 1
        if entries_seen > MAX_ENTRIES:
            raise RuntimeError(
                f"Volume inventory exceeded {MAX_ENTRIES} entries; narrow the scan."
            )
        if entry.isDir():
            queue.append(volume_path(entry.path))
        elif entry.path.lower().endswith(".pdf"):
            pdf_paths.add(volume_path(entry.path))

registered_paths = {
    volume_path(str(item["file_path"]))
    for item in doc_by_id.values() if item.get("file_path")
}
unregistered_pdfs = sorted(pdf_paths - registered_paths)
missing_source_files = sorted(registered_paths - pdf_paths)

# COMMAND ----------

rows = []
for document_id, item in doc_by_id.items():
    role = item.get("document_role")
    passage_count = counts.get(document_id, 0)
    catalog = ikf.get(document_id)
    in_selector = bool(catalog and catalog["catalogue_status"] == "AVAILABLE")
    reasons = []
    if not item.get("file_path"):
        reasons.append("NO_REGISTERED_PATH")
    elif volume_path(item["file_path"]) not in pdf_paths:
        reasons.append("REGISTERED_FILE_NOT_IN_VOLUME")
    if not in_selector:
        reasons.append("MISSING_OR_UNAVAILABLE_IN_IKF_CATALOGUE")
    elif str(catalog.get("sha256") or "").lower() != str(item.get("sha256") or "").lower():
        reasons.append("IKF_CATALOGUE_HASH_DIFFERS")
    if role == "MAIN_REPORT" and passage_count == 0:
        reasons.append("MAIN_REPORT_WITHOUT_PASSAGES")
    if role != "MAIN_REPORT":
        reasons.append("SUPPLEMENTARY_NOT_IN_SIMILAR_CASE_SEARCH")
    rows.append({
        "document_id": document_id,
        "country_code": item.get("country_code"),
        "investigation_body": item.get("investigation_body"),
        "report_title": item.get("report_title"),
        "document_role": role,
        "passages": passage_count,
        "ikf_selector": in_selector,
        "file_path": item.get("file_path"),
        "status": ", ".join(reasons) or "READY",
    })

audit = pd.DataFrame(rows, columns=[
    "document_id", "country_code", "investigation_body", "report_title",
    "document_role", "passages", "ikf_selector", "file_path", "status",
])
main = audit[audit["document_role"] == "MAIN_REPORT"]
print("PDFs in MAIRA investigation Volume:", len(pdf_paths))
print("PDFs not registered in MAIRA documents:", len(unregistered_pdfs))
print("Registered investigation documents:", len(audit))
print("Registered MAIN_REPORT documents:", len(main))
print("MAIN_REPORT documents with passages:", int((main["passages"] > 0).sum()))
print("MAIRA documents available in IKF selector:", int(audit["ikf_selector"].sum()))
print("Registered source paths missing from Volume:", len(missing_source_files))
print("Stale IKF MAIRA catalogue IDs:", len(set(ikf) - set(doc_by_id)))

def show_nonempty(label, frame):
    if frame.empty:
        print(f"{label}: none")
    else:
        print(f"{label}: {len(frame)} row(s)")
        display(frame)


show_nonempty(
    "Registered investigation documents",
    audit.sort_values(["status", "country_code", "report_title", "document_id"]),
)
show_nonempty(
    "Unregistered PDFs",
    pd.DataFrame({"pdf_path_unregistered": unregistered_pdfs}),
)
show_nonempty(
    "Registered paths absent from Volume",
    pd.DataFrame({"registered_path_not_in_volume": missing_source_files}),
)
show_nonempty(
    "Stale IKF catalogue IDs",
    pd.DataFrame({"stale_ikf_maira_document_id": sorted(set(ikf) - set(doc_by_id))}),
)

print(
    "Next: if catalogue IDs are missing, run IKF notebook 33 and refresh the App; "
    "if MAIN_REPORT passages are missing, complete MAIRA extraction/passage processing; "
    "if PDFs are unregistered, first review their source provenance and register them in MAIRA."
)
