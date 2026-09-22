# Databricks notebook source
# MAGIC %md
# MAGIC # 11 — Enable user authorization safely
# MAGIC
# MAGIC Enables the Databricks Apps user scopes required by the IKF App while
# MAGIC preserving every resource already attached to the App.
# MAGIC
# MAGIC Current use:
# MAGIC - `files`: read governed Unity Catalog source documents on behalf of the
# MAGIC   logged-in investigator, including the IKF input-document volume and the
# MAGIC   MAIRA source-document volume;
# MAGIC - `sql`: governed user-context SQL access where required.
# MAGIC
# MAGIC The notebook deliberately does not grant the App service principal broad
# MAGIC read access to source volumes. Source-document viewing uses the forwarded
# MAGIC user token so existing Unity Catalog permissions remain authoritative.

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

APP_NAME = "investigation-kg-poc"

# COMMAND ----------

current = w.api_client.do(
    "GET",
    f"/api/2.0/apps/{APP_NAME}",
)

existing_resources = current.get(
    "resources",
    [],
)

print(
    "Existing App resources preserved:",
    len(existing_resources),
)

for resource in existing_resources:
    print(" -", resource.get("name"))

# COMMAND ----------

payload = {
    "user_api_scopes": [
        "files",
        "sql",
    ],
    "resources": existing_resources,
}

w.api_client.do(
    "PATCH",
    f"/api/2.0/apps/{APP_NAME}",
    body=payload,
)

# COMMAND ----------

check = w.api_client.do(
    "GET",
    f"/api/2.0/apps/{APP_NAME}",
)

print("Configured scopes:", check.get("user_api_scopes"))
print("Effective scopes:", check.get("effective_user_api_scopes"))

print("\nResources after update:")
for resource in check.get("resources", []):
    print(resource.get("name"), resource)

expected_names = {
    resource.get("name")
    for resource in existing_resources
}
actual_names = {
    resource.get("name")
    for resource in check.get("resources", [])
}

if not expected_names.issubset(actual_names):
    raise RuntimeError(
        "One or more existing App resources were not preserved."
    )

print("")
print("PASS — user authorization enabled without dropping App resources.")
