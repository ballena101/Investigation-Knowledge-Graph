# Databricks notebook source
# MAGIC %md
# MAGIC # 62 — Validate Class-D App model resources
# MAGIC
# MAGIC Read-only validation of the two existing Class-D model services and the
# MAGIC Databricks App resource bindings used by `investigation-kg-poc`.
# MAGIC
# MAGIC This notebook **does not invoke either model**, create an endpoint, change
# MAGIC permissions, or update the App. Its purpose is to distinguish an existing
# MAGIC model service from a missing App resource binding before any billable
# MAGIC inference or endpoint creation is attempted.

# COMMAND ----------

from databricks.sdk import WorkspaceClient

APP_NAME = "investigation-kg-poc"
EXPECTED_RESOURCE_KEYS = {
    "GPT20": "class_d_gpt20_endpoint",
    "LLAMA70": "class_d_llama70_endpoint",
}

# Previously validated PoC service identifiers. The Serving UI may expose the
# short endpoint/service name while inference code records the governed FQN.
EXPECTED_SERVICE_IDENTIFIERS = {
    "GPT20": (
        "ikf-gpt-oss-20b-poc",
        "bdw_analysis_prod.kg_poc.ikf-gpt-oss-20b-poc",
    ),
    "LLAMA70": (
        "ikf-llama-3-3-70b-poc",
        "bdw_analysis_prod.kg_poc.ikf-llama-3-3-70b-poc",
    ),
}

w = WorkspaceClient()

# COMMAND ----------

print("IKF CLASS-D MODEL RESOURCE PREFLIGHT")
print("App:", APP_NAME)
print("Mode: READ ONLY — no model inference, endpoint creation, or permission changes")

app = w.apps.get(APP_NAME)
resources = list(app.resources or [])
resource_dicts = [resource.as_dict() for resource in resources]

print("\nAPP RESOURCES")
print("-------------")
if not resource_dicts:
    print("No App resources returned.")
else:
    for item in resource_dicts:
        print(item)

resource_by_name = {
    str(item.get("name") or ""): item
    for item in resource_dicts
    if item.get("name")
}

# COMMAND ----------

# Listing endpoint metadata is read-only and does not invoke model inference.
endpoint_response = w.api_client.do(
    "GET",
    "/api/2.0/serving-endpoints",
)
endpoint_rows = list(endpoint_response.get("endpoints") or [])

print("\nIKF-RELATED SERVING ENDPOINTS / MODEL SERVICES")
print("---------------------------------------------")
relevant = []
for row in endpoint_rows:
    name = str(row.get("name") or "")
    lowered = name.lower()
    if any(token in lowered for token in ("ikf", "gpt-oss", "llama")):
        relevant.append(row)
        print(
            {
                "name": name,
                "state": row.get("state"),
                "creator": row.get("creator"),
            }
        )

if not relevant:
    print("No IKF/GPT-OSS/Llama serving endpoint names were visible to this identity.")

# COMMAND ----------

print("\nBINDING CHECK")
print("-------------")
all_ok = True

for model_key, resource_key in EXPECTED_RESOURCE_KEYS.items():
    resource = resource_by_name.get(resource_key)
    expected_names = EXPECTED_SERVICE_IDENTIFIERS[model_key]
    matching_endpoints = [
        row
        for row in endpoint_rows
        if str(row.get("name") or "") in expected_names
        or any(
            candidate in str(row.get("name") or "")
            for candidate in expected_names
        )
    ]

    print("\n", model_key, sep="")
    print("  required App resource key:", resource_key)
    print("  known service identifiers:", expected_names)

    if resource is None:
        all_ok = False
        print("  App binding: MISSING")
    else:
        print("  App binding: PRESENT")
        print("  resource:", resource)

    if matching_endpoints:
        print(
            "  visible matching service(s):",
            [str(row.get("name") or "") for row in matching_endpoints],
        )
    else:
        print(
            "  visible matching service: NOT CONFIRMED from serving-endpoint list"
        )

print("\nRESULT")
print("------")
if all_ok:
    print("PASS — both required App resource keys are present.")
    print(
        "Next: redeploy/restart the App and verify that Class-D UI reports both model services."
    )
else:
    print("BINDING REQUIRED — one or both App resource keys are missing.")
    print("In Apps > investigation-kg-poc > Resources, add existing Serving endpoint resources:")
    print("  class_d_gpt20_endpoint  -> existing GPT-OSS 20B PoC service -> CAN QUERY")
    print("  class_d_llama70_endpoint -> existing Llama 3.3 70B PoC service -> CAN QUERY")
    print("Do not create a new endpoint merely because the App binding is missing.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Governance / cost note
# MAGIC
# MAGIC A Databricks App resource binding gives the App service principal the
# MAGIC minimum permission needed to query an existing serving endpoint. The
# MAGIC recommended permission is **CAN QUERY**. Do not grant CAN MANAGE unless
# MAGIC there is a separate administrative requirement.
# MAGIC
# MAGIC This notebook performs metadata reads only. It deliberately does not send
# MAGIC prompts, protected evidence, or synthetic test text to either model.
