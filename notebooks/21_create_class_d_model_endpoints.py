# Databricks notebook source
# MAGIC %md
# MAGIC # 21 — Create/validate dedicated Class D model endpoints
# MAGIC
# MAGIC Administrative helper for the two Class D models:
# MAGIC
# MAGIC - GPT-OSS 20B
# MAGIC - Meta Llama 3.3 70B Instruct
# MAGIC
# MAGIC This notebook assumes the approved open-weight models have already been
# MAGIC registered in Unity Catalog as custom/MLflow models.
# MAGIC
# MAGIC It does **not** download model weights from the internet.
# MAGIC
# MAGIC Endpoint creation is disabled by default. Review the registered model
# MAGIC names, versions, GPU workload types and governance settings first.

# COMMAND ----------

dbutils.widgets.text(
    "gpt20_uc_model",
    "",
    "GPT-OSS 20B UC model",
)
dbutils.widgets.text(
    "gpt20_version",
    "",
    "GPT-OSS 20B version",
)
dbutils.widgets.text(
    "gpt20_endpoint",
    "ikg-class-d-gpt-oss-20b",
    "GPT-OSS 20B endpoint",
)
dbutils.widgets.text(
    "gpt20_workload_type",
    "GPU_LARGE",
    "GPT-OSS 20B workload type",
)

dbutils.widgets.text(
    "llama70_uc_model",
    "",
    "Llama 3.3 70B UC model",
)
dbutils.widgets.text(
    "llama70_version",
    "",
    "Llama 3.3 70B version",
)
dbutils.widgets.text(
    "llama70_endpoint",
    "ikg-class-d-llama-3-3-70b",
    "Llama 3.3 70B endpoint",
)
dbutils.widgets.text(
    "llama70_workload_type",
    "GPU_LARGE_4",
    "Llama 3.3 70B workload type",
)

dbutils.widgets.dropdown(
    "create_endpoints",
    "false",
    ["false", "true"],
    "Create endpoints",
)

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

gpt20_uc_model = dbutils.widgets.get(
    "gpt20_uc_model"
).strip()
gpt20_version = dbutils.widgets.get(
    "gpt20_version"
).strip()
gpt20_endpoint = dbutils.widgets.get(
    "gpt20_endpoint"
).strip()
gpt20_workload_type = dbutils.widgets.get(
    "gpt20_workload_type"
).strip()

llama70_uc_model = dbutils.widgets.get(
    "llama70_uc_model"
).strip()
llama70_version = dbutils.widgets.get(
    "llama70_version"
).strip()
llama70_endpoint = dbutils.widgets.get(
    "llama70_endpoint"
).strip()
llama70_workload_type = dbutils.widgets.get(
    "llama70_workload_type"
).strip()

create_endpoints = (
    dbutils.widgets.get(
        "create_endpoints"
    ) == "true"
)

# COMMAND ----------

def endpoint_exists(name):
    try:
        return w.api_client.do(
            "GET",
            f"/api/2.0/serving-endpoints/{name}",
        )
    except Exception:
        return None


def create_endpoint(
    *,
    endpoint_name,
    entity_name,
    entity_version,
    workload_type,
):
    if not entity_name or not entity_version:
        raise ValueError(
            f"Unity Catalog model/version missing for {endpoint_name}."
        )

    return w.api_client.do(
        "POST",
        "/api/2.0/serving-endpoints",
        body={
            "name": endpoint_name,
            "config": {
                "served_entities": [
                    {
                        "entity_name": entity_name,
                        "entity_version": entity_version,
                        "workload_type": workload_type,
                        "workload_size": "Small",
                        "scale_to_zero_enabled": True,
                    }
                ]
            },
            "tags": [
                {
                    "key": "project",
                    "value": "investigation-kg",
                },
                {
                    "key": "information_class",
                    "value": "D",
                },
            ],
        },
    )


# COMMAND ----------

models = [
    {
        "label": "GPT-OSS 20B",
        "endpoint": gpt20_endpoint,
        "entity_name": gpt20_uc_model,
        "entity_version": gpt20_version,
        "workload_type": gpt20_workload_type,
    },
    {
        "label": "Llama 3.3 70B",
        "endpoint": llama70_endpoint,
        "entity_name": llama70_uc_model,
        "entity_version": llama70_version,
        "workload_type": llama70_workload_type,
    },
]

for model in models:
    print("")
    print(model["label"])
    print("endpoint:", model["endpoint"])
    print("UC model:", model["entity_name"])
    print("version:", model["entity_version"])
    print("workload:", model["workload_type"])

    existing = endpoint_exists(
        model["endpoint"]
    )

    if existing:
        print("status: endpoint already exists")
        print("state:", existing.get("state"))
        continue

    print("status: endpoint does not exist")

    if create_endpoints:
        created = create_endpoint(
            endpoint_name=model["endpoint"],
            entity_name=model["entity_name"],
            entity_version=model["entity_version"],
            workload_type=model["workload_type"],
        )
        print(
            "created:",
            created.get("name")
            or model["endpoint"],
        )
    else:
        print(
            "creation disabled. Review configuration and set "
            "create_endpoints=true when approved."
        )

# COMMAND ----------

print("")
print("CLASS D CONFIGURATION AFTER APPROVAL")
print(
    "CLASS_D_GPT20_ENDPOINT="
    + gpt20_endpoint
)
print(
    "CLASS_D_LLAMA70_ENDPOINT="
    + llama70_endpoint
)
print("")
print(
    "Important: endpoint existence is not sufficient approval. "
    "Validate model identity, networking, logging/retention, access "
    "permissions and Class D governance before enabling the App."
)
