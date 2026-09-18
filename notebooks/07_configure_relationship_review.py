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
# MAGIC The app continues to use Neo4j only for graph projection. Human review is stored in Delta / Unity Catalog.

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

warehouse_rows = [
    (
        wh.id,
        wh.name,
        str(wh.state) if wh.state is not None else None,
    )
    for wh in w.warehouses.list()
]

display(
    spark.createDataFrame(
        warehouse_rows,
        ["warehouse_id", "warehouse_name", "state"],
    )
)

# COMMAND ----------

# Enter the warehouse ID from the table above in the widget.
dbutils.widgets.text("warehouse_id", "")
WAREHOUSE_ID = dbutils.widgets.get("warehouse_id").strip()

if not WAREHOUSE_ID:
    raise ValueError(
        "Set the warehouse_id widget to the SQL warehouse you want the app to use, "
        "then rerun this cell."
    )

print("Selected warehouse:", WAREHOUSE_ID)

# COMMAND ----------

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

# COMMAND ----------

from databricks.sdk.service.apps import (
    App,
    AppResource,
    AppResourceSecret,
    AppResourceSecretSecretPermission,
    AppResourceSqlWarehouse,
    AppResourceSqlWarehouseSqlWarehousePermission,
    AppResourceUcSecurable,
    AppResourceUcSecurableUcSecurablePermission,
    AppResourceUcSecurableUcSecurableType,
)

APP_NAME = "investigation-kg-poc"
SECRET_SCOPE = "kg-poc-app"

resources = [
    AppResource(
        name="neo4j_uri",
        secret=AppResourceSecret(
            scope=SECRET_SCOPE,
            key="neo4j_uri",
            permission=AppResourceSecretSecretPermission.READ,
        ),
    ),
    AppResource(
        name="neo4j_username",
        secret=AppResourceSecret(
            scope=SECRET_SCOPE,
            key="neo4j_username",
            permission=AppResourceSecretSecretPermission.READ,
        ),
    ),
    AppResource(
        name="neo4j_password",
        secret=AppResourceSecret(
            scope=SECRET_SCOPE,
            key="neo4j_password",
            permission=AppResourceSecretSecretPermission.READ,
        ),
    ),
    AppResource(
        name="review_warehouse",
        sql_warehouse=AppResourceSqlWarehouse(
            id=WAREHOUSE_ID,
            permission=AppResourceSqlWarehouseSqlWarehousePermission.CAN_USE,
        ),
    ),
    AppResource(
        name="relationship_review_table",
        uc_securable=AppResourceUcSecurable(
            securable_full_name=REVIEW_TABLE,
            securable_type=AppResourceUcSecurableUcSecurableType.TABLE,
            permission=AppResourceUcSecurableUcSecurablePermission.MODIFY,
        ),
    ),
]

w.apps.update(
    name=APP_NAME,
    app=App(
        name=APP_NAME,
        resources=resources,
    ),
)

print("App resources updated atomically.")

# COMMAND ----------

app = w.apps.get(APP_NAME)

print("APP RESOURCES")
print("-------------")
for resource in app.resources or []:
    print(resource.as_dict())

expected = {
    "neo4j_uri",
    "neo4j_username",
    "neo4j_password",
    "review_warehouse",
    "relationship_review_table",
}

actual = {
    resource.name
    for resource in app.resources or []
}

missing = expected - actual

if missing:
    raise RuntimeError(
        f"Missing app resources after update: {sorted(missing)}"
    )

print("All five required resources are attached.")
