# Databricks notebook source
# MAGIC %md
# MAGIC # 34 — Governed MAIRA retrieval runtime preflight
# MAGIC
# MAGIC Read-only gate before activating governed MAIRA retrieval in the normal
# MAGIC IKF App workflow.
# MAGIC
# MAGIC This notebook validates the governed data/runtime inputs only. It does
# MAGIC not invoke an LLM, modify Neo4j, create retrieval results or change MAIRA.

# COMMAND ----------

dbutils.widgets.text(
    "query_id",
    "Q003",
    "Governed query ID",
)

# COMMAND ----------

from pyspark.sql import functions as F

QUERY_SPEC_TABLE = "bdw_analysis_prod.maira.query_specifications"
QUERY_CONCEPT_TABLE = "bdw_analysis_prod.maira.query_spec_concepts"
TERMINOLOGY_TABLE = "bdw_analysis_prod.maira.terminology_normalisations"
DOCUMENT_TABLE = "bdw_analysis_prod.maira.documents"
PASSAGE_TABLE = "bdw_analysis_prod.maira.passages"

SUPPORTED_DETERMINISTIC_RELATIONSHIPS = {
    "CONTRIBUTED_TO",
    "FOLLOWED_BY",
}

query_id = dbutils.widgets.get("query_id").strip()

if not query_id:
    raise ValueError("Enter a governed MAIRA query_id.")

# COMMAND ----------

required_tables = [
    QUERY_SPEC_TABLE,
    QUERY_CONCEPT_TABLE,
    TERMINOLOGY_TABLE,
    DOCUMENT_TABLE,
    PASSAGE_TABLE,
]

missing_tables = [
    table_name
    for table_name in required_tables
    if not spark.catalog.tableExists(table_name)
]

if missing_tables:
    raise RuntimeError(
        "Required MAIRA governed tables are missing: "
        + ", ".join(missing_tables)
    )

print("Governed MAIRA tables: ready")

# COMMAND ----------

spec_rows = (
    spark.table(QUERY_SPEC_TABLE)
    .filter(F.col("query_id") == query_id)
    .collect()
)

if len(spec_rows) != 1:
    raise ValueError(
        f"Expected exactly one governed query specification for {query_id}; "
        f"found {len(spec_rows)}."
    )

spec = spec_rows[0].asDict(recursive=True)
query_spec_id = spec["query_spec_id"]
relationship = spec["relationship"]

print("Query ID:", query_id)
print("Query spec ID:", query_spec_id)
print("Requested relationship:", relationship)

if relationship not in SUPPORTED_DETERMINISTIC_RELATIONSHIPS:
    raise NotImplementedError(
        "The governed query exists, but its relationship is not yet in the "
        "IKF deterministic-runtime allow-list: "
        + str(relationship)
    )

# COMMAND ----------

concepts = (
    spark.table(QUERY_CONCEPT_TABLE)
    .filter(F.col("query_spec_id") == query_spec_id)
)

concept_count = concepts.count()

if concept_count == 0:
    raise ValueError(
        "The governed query specification has no governed concepts."
    )

display(
    concepts.orderBy(
        "component_role",
        "code_idcode",
    )
)

roles = {
    row["component_role"]
    for row in concepts.select("component_role").distinct().collect()
}

print("Concept rows:", concept_count)
print("Component roles:", sorted(roles))

# COMMAND ----------

validated_normalisations = (
    spark.table(TERMINOLOGY_TABLE)
    .filter(F.col("review_status") == "HUMAN_VALIDATED")
)

validated_normalisation_count = validated_normalisations.count()

print(
    "Operational HUMAN_VALIDATED terminology normalisations:",
    validated_normalisation_count,
)

status_counts = (
    spark.table(TERMINOLOGY_TABLE)
    .groupBy("review_status")
    .count()
    .orderBy("review_status")
)

display(status_counts)

# COMMAND ----------

investigation_documents = (
    spark.table(DOCUMENT_TABLE)
    .filter(F.col("corpus_type") == "INVESTIGATION")
)

main_reports = investigation_documents.filter(
    F.col("document_role") == "MAIN_REPORT"
)

main_report_count = main_reports.count()

main_report_passages = (
    spark.table(PASSAGE_TABLE)
    .join(
        main_reports.select("document_id"),
        on="document_id",
        how="inner",
    )
)

passage_count = main_report_passages.count()
documents_with_passages = (
    main_report_passages
    .select("document_id")
    .distinct()
    .count()
)

print("MAIRA MAIN_REPORT documents:", main_report_count)
print("MAIN_REPORT documents with passages:", documents_with_passages)
print("Canonical MAIN_REPORT passages:", passage_count)

if passage_count == 0:
    raise RuntimeError(
        "No canonical MAIN_REPORT passages are available for governed retrieval."
    )

# COMMAND ----------

# Confirm the query's governed codes exist and identify how many
# HUMAN_VALIDATED source-language expressions are operational for them.

query_codes = [
    row["code_idcode"]
    for row in concepts.select("code_idcode").distinct().collect()
    if row["code_idcode"] is not None
]

operational_terms = (
    validated_normalisations
    .filter(F.col("target_code_idcode").isin(query_codes))
    .select(
        "source_expression",
        "target_code_idcode",
        "review_status",
    )
)

operational_term_count = operational_terms.count()

print(
    "HUMAN_VALIDATED terminology expressions relevant to this query:",
    operational_term_count,
)

if operational_term_count:
    display(
        operational_terms.orderBy(
            "target_code_idcode",
            "source_expression",
        )
    )

# COMMAND ----------

print("")
print("PASS — GOVERNED MAIRA RETRIEVAL DATA PREFLIGHT")
print("query_id:", query_id)
print("query_spec_id:", query_spec_id)
print("relationship:", relationship)
print("concept rows:", concept_count)
print("canonical passages:", passage_count)
print(
    "relevant HUMAN_VALIDATED terminology expressions:",
    operational_term_count,
)
print("")
print(
    "NEXT: validate the reusable deterministic relationship/retrieval code "
    "runtime before activating governed retrieval in the App."
)
