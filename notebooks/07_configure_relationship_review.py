# Databricks notebook source
# MAGIC %md
# MAGIC # 07 — Configure relationship review resources
# MAGIC
# MAGIC Creates the governed human-review table and atomically attaches:
# MAGIC
# MAGIC - the existing three Neo4j secret resources;
# MAGIC - one SQL warehouse resource with CAN_USE;
# MAGIC - the relationship review table with MODIFY.
# MAGIC
# MAGIC Note: some Databricks Runtime environments expose an Apps SDK model whose
# MAGIC generated enums lag the live Apps REST API. To avoid that mismatch, this
# MAGIC notebook sends the documented resource JSON directly through
# MAGIC WorkspaceClient.api_client.
# MAGIC
# MAGIC The app continues to use Neo4j only for graph projection. Human review is
# MAGIC stored in Delta / Unity Catalog.

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# COMMAND ----------

WAREHOUSE_ID = "372b5b52ba082619"
REVIEW_TABLE = "bdw_analysis_prod.kg_poc.relationship_human_review"

spark.sql("""
CREATE SCHEMA IF NOT EXISTS bdw_analysis_prod.kg_poc
""")

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {REVIEW_TABLE} (
    review_id STRING NOT NULL,
    case_id STRING NOT NULL,
    graph_version STRING,
    edge_id STRING NOT NULL,
    source_node_id STRING,
    source_label STRING,
    original_relationship STRING,
    target_node_id STRING,
    target_label STRING,
    assistant_review_status STRING,
    human_review_decision STRING NOT NULL,
    human_review_status STRING NOT NULL,
    amended_relationship STRING,
    reviewer_email STRING,
    reviewer_user_id STRING,
    reviewer_username STRING,
    reviewed_at TIMESTAMP NOT NULL,
    review_comment STRING
)
USING DELTA
""")

print("Review table ready:", REVIEW_TABLE)
print("Warehouse:", WAREHOUSE_ID)

# COMMAND ----------

APP_NAME = "investigation-kg-poc"
SECRET_SCOPE = "kg-poc-app"

payload = {
    "resources": [
        {
            "name": "neo4j_uri",
            "secret": {
                "scope": SECRET_SCOPE,
                "key": "neo4j_uri",
                "permission": "READ",
            },
        },
        {
            "name": "neo4j_username",
            "secret": {
                "scope": SECRET_SCOPE,
                "key": "neo4j_username",
                "permission": "READ",
            },
        },
        {
            "name": "neo4j_password",
            "secret": {
                "scope": SECRET_SCOPE,
                "key": "neo4j_password",
                "permission": "READ",
            },
        },
        {
            "name": "review_warehouse",
            "sql_warehouse": {
                "id": WAREHOUSE_ID,
                "permission": "CAN_USE",
            },
        },
        {
            "name": "relationship_review_table",
            "uc_securable": {
                "securable_full_name": REVIEW_TABLE,
                "securable_type": "TABLE",
                "permission": "MODIFY",
            },
        },
    ]
}

response = w.api_client.do(
    "PATCH",
    f"/api/2.0/apps/{APP_NAME}",
    body=payload,
)

print("App resources updated via Apps REST API.")

# COMMAND ----------

app_json = w.api_client.do(
    "GET",
    f"/api/2.0/apps/{APP_NAME}",
)

print("APP RESOURCES")
print("-------------")

resources = app_json.get("resources", [])
for resource in resources:
    print(resource)

expected = {
    "neo4j_uri",
    "neo4j_username",
    "neo4j_password",
    "review_warehouse",
    "relationship_review_table",
}

actual = {
    resource.get("name")
    for resource in resources
}

missing = expected - actual

if missing:
    raise RuntimeError(
        f"Missing app resources after update: {sorted(missing)}"
    )

print("All five required resources are attached.")
