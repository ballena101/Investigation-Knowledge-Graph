# Databricks notebook source
# MAGIC %md
# MAGIC # 17 — Create automated analysis Lakeflow Job
# MAGIC
# MAGIC One-time setup.
# MAGIC
# MAGIC Creates a two-task Lakeflow Job:
# MAGIC
# MAGIC 1. 15_extract_analysis_evidence
# MAGIC 2. 16_analyse_evidence_and_build_graph
# MAGIC
# MAGIC The App will trigger this Job automatically with one job parameter:
# MAGIC `analysis_id`.
# MAGIC
# MAGIC Notebook tasks use serverless compute by omitting cluster configuration.

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# COMMAND ----------

current_notebook = (
    dbutils.notebook.entry_point
    .getDbutils()
    .notebook()
    .getContext()
    .notebookPath()
    .get()
)

notebooks_dir = current_notebook.rsplit("/", 1)[0]

NOTEBOOK_15_PATH = f"{notebooks_dir}/15_extract_analysis_evidence"
NOTEBOOK_16_PATH = f"{notebooks_dir}/16_analyse_evidence_and_build_graph"

print("Notebook 15:", NOTEBOOK_15_PATH)
print("Notebook 16:", NOTEBOOK_16_PATH)

# COMMAND ----------

JOB_NAME = "Investigation KG - Automated Analysis"

existing_job_id = None

jobs = w.api_client.do(
    "GET",
    "/api/2.2/jobs/list?limit=100",
)

for job in jobs.get("jobs", []):
    settings = job.get("settings") or {}
    if settings.get("name") == JOB_NAME:
        existing_job_id = job.get("job_id")
        break

print("Existing job:", existing_job_id)

# COMMAND ----------

job_settings = {
    "name": JOB_NAME,
    "description": (
        "Automated document-group processing for the Investigation "
        "Knowledge Graph PoC."
    ),
    "parameters": [
        {
            "name": "analysis_id",
            "default": "analysis_NOT_SET",
        },
        {
            "name": "model_service",
            "default": "system.ai.meta-llama-3-3-70b-instruct",
        }
    ],
    "tasks": [
        {
            "task_key": "extract_evidence",
            "description": (
                "Extract deterministic evidence passages and provenance "
                "from the selected analysis documents."
            ),
            "notebook_task": {
                "notebook_path": NOTEBOOK_15_PATH,
                "source": "WORKSPACE",
            },
            "timeout_seconds": 0,
            "max_retries": 0,
        },
        {
            "task_key": "analyse_and_build_graph",
            "description": (
                "Analyse the evidence group, resolve concepts and build "
                "the generic Neo4j graph."
            ),
            "depends_on": [
                {
                    "task_key": "extract_evidence",
                }
            ],
            "notebook_task": {
                "notebook_path": NOTEBOOK_16_PATH,
                "source": "WORKSPACE",
            },
            "timeout_seconds": 0,
            "max_retries": 0,
        },
    ],
    "max_concurrent_runs": 4,
    "queue": {
        "enabled": True,
    },
}

if existing_job_id is None:
    created = w.api_client.do(
        "POST",
        "/api/2.2/jobs/create",
        body=job_settings,
    )

    job_id = created["job_id"]
    print("Created job:", job_id)

else:
    w.api_client.do(
        "POST",
        "/api/2.2/jobs/reset",
        body={
            "job_id": existing_job_id,
            "new_settings": job_settings,
        },
    )

    job_id = existing_job_id
    print("Updated existing job:", job_id)

# COMMAND ----------

job = w.api_client.do(
    "GET",
    f"/api/2.2/jobs/get?job_id={job_id}",
)

print("")
print("AUTOMATED ANALYSIS JOB READY")
print("job_id:", job_id)
print("name:", (job.get("settings") or {}).get("name"))
print("run_as_user:", job.get("run_as_user_name"))

print("")
print("Next step:")
print(
    "Apps > investigation-kg-poc > Edit > Resources > "
    "Add resource > Job"
)
print("Select:", JOB_NAME)
print("Permission: Can manage run")
print("Resource key: analysis_job")
