# Databricks notebook source
# MAGIC %md
# MAGIC # 06 — Configure Databricks App resources
# MAGIC
# MAGIC Attaches the three Neo4j secrets to the existing Databricks App.
# MAGIC No secret values are written to source code.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.apps import (
    App,
    AppResource,
    AppResourceSecret,
    AppResourceSecretSecretPermission,
)

APP_NAME = "investigation-kg-poc"
SECRET_SCOPE = "kg-poc-app"

w = WorkspaceClient()

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
]

w.apps.update(
    name=APP_NAME,
    app=App(
        name=APP_NAME,
        resources=resources,
    ),
)

print("App resources updated.")

app = w.apps.get(APP_NAME)

print("APP RESOURCES")
print("-------------")
for r in app.resources or []:
    print(r.as_dict())
