# Databricks notebook source
# MAGIC %md
# MAGIC # 11 — Enable user authorization while preserving Neo4j resources
# MAGIC
# MAGIC The generic upload workflow uses the interactive user's Databricks
# MAGIC permissions through the files + sql scopes.
# MAGIC
# MAGIC The existing Neo4j secret resources must remain attached because
# MAGIC app.yaml resolves NEO4J_URI / USERNAME / PASSWORD through valueFrom.

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

APP_NAME = "investigation-kg-poc"
SECRET_SCOPE = "kg-poc-app"

payload = {
    "user_api_scopes": [
        "files",
        "sql",
    ],
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
    ],
}

w.api_client.do(
    "PATCH",
    f"/api/2.0/apps/{APP_NAME}",
    body=payload,
)

check = w.api_client.do(
    "GET",
    f"/api/2.0/apps/{APP_NAME}",
)

print("Configured scopes:", check.get("user_api_scopes"))
print("Effective scopes:", check.get("effective_user_api_scopes"))

print("\nResources:")
for resource in check.get("resources", []):
    print(resource.get("name"), resource)
