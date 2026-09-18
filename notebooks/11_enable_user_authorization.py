# Databricks notebook source
# MAGIC %md
# MAGIC # 11 — Enable user authorization for generic analyses
# MAGIC
# MAGIC The generic upload workflow uses the interactive user's existing
# MAGIC Databricks permissions instead of granting a SQL warehouse or Unity
# MAGIC Catalog volume to the App service principal.
# MAGIC
# MAGIC Required scopes:
# MAGIC
# MAGIC - files
# MAGIC - sql

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

APP_NAME = "investigation-kg-poc"

before = w.api_client.do(
    "GET",
    f"/api/2.0/apps/{APP_NAME}",
)

print("Before:")
print("user_api_scopes:", before.get("user_api_scopes"))
print(
    "effective_user_api_scopes:",
    before.get("effective_user_api_scopes"),
)

# COMMAND ----------

updated = w.api_client.do(
    "PATCH",
    f"/api/2.0/apps/{APP_NAME}",
    body={
        "user_api_scopes": [
            "files",
            "sql",
        ]
    },
)

print("Requested user authorization scopes:", updated.get("user_api_scopes"))

# COMMAND ----------

after = w.api_client.do(
    "GET",
    f"/api/2.0/apps/{APP_NAME}",
)

print("After:")
print("user_api_scopes:", after.get("user_api_scopes"))
print(
    "effective_user_api_scopes:",
    after.get("effective_user_api_scopes"),
)
