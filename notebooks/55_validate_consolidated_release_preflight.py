# Databricks notebook source
# MAGIC %md
# MAGIC # 55 — Consolidated IKF release preflight
# MAGIC
# MAGIC Read-only, no-model preflight before the consolidated Databricks
# MAGIC deployment/runtime validation session.
# MAGIC
# MAGIC Checks:
# MAGIC - required Lakeflow Jobs;
# MAGIC - App resources and user API scopes;
# MAGIC - required MAIRA / IKF Delta tables;
# MAGIC - governed source roots;
# MAGIC - Neo4j connectivity;
# MAGIC - expected source-layer boundaries.
# MAGIC
# MAGIC This notebook does not trigger Jobs, call an LLM or modify application
# MAGIC data.

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1 databricks-sdk==0.139.0

# COMMAND ----------

import os

from databricks.sdk import WorkspaceClient
from neo4j import GraphDatabase

APP_NAME = "investigation-kg-poc"

REQUIRED_JOB_NAMES = (
    "Investigation KG - Automated Analysis",
    "Investigation KG - Class D Dual Model",
    "Investigation KG - Ask Processed Evidence",
    "Investigation KG - Propose EMCIP Mappings",
    "Investigation KG - SHIELD Proposals",
    "Investigation KG - Relationship Correction",
    "Investigation KG - Similar MAIRA Cases",
    "Investigation KG - Type D Audio Transcription",
)

# Keep this list aligned with every app.yaml `valueFrom` resource binding.
# Both CLASS_D_LLAMA70_ENDPOINT and the temporary legacy Ollama environment alias
# resolve to the same canonical App resource: class_d_llama70_endpoint.
REQUIRED_APP_RESOURCES = (
    "neo4j_uri",
    "neo4j_username",
    "neo4j_password",
    "analysis_job",
    "class_d_analysis_job",
    "ask_job",
    "emcip_mapping_job",
    "shield_proposal_job",
    "relationship_correction_job",
    "similar_cases_job",
    "transcription_job",
    "class_d_gpt20_endpoint",
    "class_d_llama70_endpoint",
    "direct_text_encryption_key",
    "ikg_admin_users",
)

REQUIRED_USER_SCOPES = {"files", "sql"}

CORE_TABLES = (
    "bdw_analysis_prod.maira.documents",
    "bdw_analysis_prod.maira.passages",
    "bdw_analysis_prod.maira.query_specifications",
    "bdw_analysis_prod.maira.query_spec_concepts",
    "bdw_analysis_prod.maira.terminology_normalisations",
    "bdw_analysis_prod.maira.emcip_operational_registry",
    "bdw_analysis_prod.kg_poc.analysis_passage",
)

INDEXED_GOVERNED_TABLES = (
    "bdw_analysis_prod.kg_poc.reference_document",
    "bdw_analysis_prod.kg_poc.reference_passage",
    "bdw_analysis_prod.kg_poc.shield_document",
    "bdw_analysis_prod.kg_poc.shield_passage",
)

SOURCE_ROOTS = {
    "IKF_INPUT": "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources",
    "MAIRA_INVESTIGATION": "/Volumes/bdw_analysis_prod/maira/source_documents",
    "REFERENCE_CONTEXT": "/Volumes/bdw_analysis_prod/kg_poc/reference_context",
}

w = WorkspaceClient()
errors = []
warnings = []
rows = []

# COMMAND ----------

# Lakeflow Jobs
jobs_payload = w.api_client.do("GET", "/api/2.2/jobs/list?limit=100")
job_by_name = {
    (job.get("settings") or {}).get("name"): job
    for job in jobs_payload.get("jobs", [])
}

for job_name in REQUIRED_JOB_NAMES:
    found = job_name in job_by_name
    rows.append({"area": "Lakeflow Job", "item": job_name, "status": "PASS" if found else "FAIL"})
    if not found:
        errors.append("Missing Lakeflow Job: " + job_name)

# COMMAND ----------

# Databricks App resources and user scopes
try:
    app = w.api_client.do("GET", f"/api/2.0/apps/{APP_NAME}")
except Exception as exc:
    app = None
    errors.append("Databricks App could not be read: " + str(exc))

if app is not None:
    resource_names = {
        resource.get("name")
        for resource in app.get("resources", [])
        if resource.get("name")
    }

    for resource_name in REQUIRED_APP_RESOURCES:
        found = resource_name in resource_names
        rows.append({
            "area": "App resource",
            "item": resource_name,
            "status": "PASS" if found else "FAIL",
        })
        if not found:
            errors.append("Missing App resource: " + resource_name)

    effective_scopes = set(
        app.get("effective_user_api_scopes")
        or app.get("user_api_scopes")
        or []
    )
    missing_scopes = REQUIRED_USER_SCOPES - effective_scopes
    rows.append({
        "area": "App user scopes",
        "item": ", ".join(sorted(REQUIRED_USER_SCOPES)),
        "status": "PASS" if not missing_scopes else "FAIL",
    })
    if missing_scopes:
        errors.append("Missing App user API scopes: " + ", ".join(sorted(missing_scopes)))

# COMMAND ----------

# Delta tables
for table_name in CORE_TABLES:
    found = spark.catalog.tableExists(table_name)
    rows.append({
        "area": "Core Delta table",
        "item": table_name,
        "status": "PASS" if found else "FAIL",
    })
    if not found:
        errors.append("Missing core Delta table: " + table_name)

for table_name in INDEXED_GOVERNED_TABLES:
    found = spark.catalog.tableExists(table_name)
    rows.append({
        "area": "Governed indexed table",
        "item": table_name,
        "status": "PASS" if found else "NOT_INDEXED",
    })
    if not found:
        warnings.append("Governed corpus table not indexed yet: " + table_name)

# COMMAND ----------

# Governed volume roots
for source_layer, root in SOURCE_ROOTS.items():
    found = os.path.isdir(root)
    rows.append({
        "area": "Governed source root",
        "item": source_layer + " → " + root,
        "status": "PASS" if found else "FAIL",
    })
    if not found:
        errors.append("Missing governed source root: " + source_layer + " → " + root)

shield_root = os.path.join(SOURCE_ROOTS["IKF_INPUT"], "SHIELD")
shield_exists = os.path.isdir(shield_root)
rows.append({
    "area": "Reserved governed source",
    "item": "SHIELD → " + shield_root,
    "status": "PASS" if shield_exists else "NOT_READY",
})
if not shield_exists:
    warnings.append("Persistent SHIELD folder is not available yet: " + shield_root)

# COMMAND ----------

# Neo4j connectivity and compact source-layer checks
try:
    NEO4J_URI = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_uri")
    NEO4J_USERNAME = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_username")
    NEO4J_PASSWORD = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_password")

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
    )
    driver.verify_connectivity()
    rows.append({"area": "Neo4j", "item": "Connectivity", "status": "PASS"})

    with driver.session() as session:
        source_counts = session.run(
            """
            MATCH (d:SourceDocument)
            RETURN coalesce(properties(d)["source_managed_by"], "IKF") AS source_managed_by,
                   count(*) AS documents
            ORDER BY source_managed_by
            """
        )
        print("SourceDocument ownership:")
        for record in source_counts:
            print(" -", record["source_managed_by"], record["documents"])

        accidental_reference_nodes = session.run(
            """
            MATCH (d:SourceDocument)
            WHERE properties(d)["source_managed_by"] = "REFERENCE_CONTEXT"
               OR properties(d)["source_repository"] = "REFERENCE_CONTEXT"
            RETURN count(d) AS n
            """
        ).single()["n"]
        rows.append({
            "area": "Source-layer boundary",
            "item": "REFERENCE_CONTEXT not stored as ordinary SourceDocument",
            "status": "PASS" if accidental_reference_nodes == 0 else "FAIL",
        })
        if accidental_reference_nodes:
            errors.append(
                "REFERENCE_CONTEXT documents were found in the ordinary SourceDocument catalogue."
            )

        accidental_shield_active = session.run(
            """
            MATCH (d:SourceDocument)
            WHERE coalesce(properties(d)["source_repository"], "") = "IKF_SHIELD"
              AND coalesce(properties(d)["catalogue_status"], "") = "AVAILABLE"
            RETURN count(d) AS n
            """
        ).single()["n"]
        rows.append({
            "area": "Source-layer boundary",
            "item": "SHIELD excluded from ordinary available catalogue",
            "status": "PASS" if accidental_shield_active == 0 else "FAIL",
        })
        if accidental_shield_active:
            errors.append(
                "SHIELD SourceDocument entries remain AVAILABLE in the ordinary document catalogue."
            )

    driver.close()
except Exception as exc:
    rows.append({"area": "Neo4j", "item": "Connectivity", "status": "FAIL"})
    errors.append("Neo4j preflight failed: " + str(exc))

# COMMAND ----------

display(spark.createDataFrame(rows).orderBy("area", "item"))

print("")
print("Warnings:", len(warnings))
for warning in warnings:
    print("WARNING —", warning)

print("")
print("Errors:", len(errors))
for error in errors:
    print("ERROR —", error)

if errors:
    raise RuntimeError(
        "IKF consolidated release preflight failed. "
        "Resolve the listed errors before the paid runtime validation session."
    )

print("")
print("PASS — IKF CONSOLIDATED RELEASE PREFLIGHT")
if warnings:
    print(
        "PASS with setup warnings. Complete the listed indexing steps before feature-specific validators."
    )
else:
    print("All checked release prerequisites are present.")
