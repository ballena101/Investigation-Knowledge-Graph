# Databricks notebook source
# MAGIC %md
# MAGIC # 18 — Validate Class D GPT-OSS 20B endpoint
# MAGIC
# MAGIC One-time administrative validation for the protected-data model route.
# MAGIC
# MAGIC The normal investigator never runs this notebook.
# MAGIC
# MAGIC It verifies that a dedicated Databricks Model Serving endpoint exists
# MAGIC and records the endpoint name to be supplied to the App as
# MAGIC `CLASS_D_MODEL_ENDPOINT`.
# MAGIC
# MAGIC The endpoint must be independently reviewed/approved for:
# MAGIC - GPT-OSS 20B serving configuration;
# MAGIC - no external provider inference path;
# MAGIC - networking/private-access requirements;
# MAGIC - logging/retention;
# MAGIC - service-principal permissions;
# MAGIC - Article 9 / Class D use.

# COMMAND ----------

dbutils.widgets.text(
    "endpoint_name",
    "",
    "Dedicated Class D endpoint name",
)

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

endpoint_name = dbutils.widgets.get(
    "endpoint_name"
).strip()

if not endpoint_name:
    raise ValueError(
        "Enter the dedicated GPT-OSS 20B Model Serving endpoint name."
    )

# COMMAND ----------

endpoint = w.api_client.do(
    "GET",
    f"/api/2.0/serving-endpoints/{endpoint_name}",
)

print("Endpoint found:", endpoint_name)
print("State:", endpoint.get("state"))
print("Creator:", endpoint.get("creator"))
print("Config:")
print(endpoint.get("config"))

# COMMAND ----------

config_text = str(
    endpoint.get("config") or ""
).lower()

if "20b" not in config_text and "gpt-oss" not in config_text:
    print("")
    print(
        "WARNING: the endpoint metadata does not clearly identify GPT-OSS 20B. "
        "Do not approve this endpoint for Class D until the served model has "
        "been independently verified."
    )

print("")
print("CLASS D ENDPOINT VALIDATION CHECKLIST")
print("1. Served model is the approved GPT-OSS 20B deployment")
print("2. No external provider inference path")
print("3. Approved networking/private access")
print("4. Logging/retention reviewed")
print("5. App service principal has only query permission")
print("6. Security/data-protection/legal approval recorded")
print("")
print("After approval, configure the Databricks App environment:")
print(f"CLASS_D_MODEL_ENDPOINT={endpoint_name}")
print("")
print(
    "The App remains fail-closed for Class D until this environment "
    "variable is present."
)
