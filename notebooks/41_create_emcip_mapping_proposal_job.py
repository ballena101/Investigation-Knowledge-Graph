# Databricks notebook source
# MAGIC %md
# MAGIC # 41 — Create generic EMCIP mapping proposal Job
# MAGIC
# MAGIC One-time setup.
# MAGIC
# MAGIC Creates an on-demand one-task Lakeflow Job:
# MAGIC
# MAGIC 1. `40_propose_generic_emcip_mappings`
# MAGIC
# MAGIC The Job does not modify validated graph relationships or human reviews.

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
NOTEBOOK_40_PATH = (
    f"{notebooks_dir}/40_propose_generic_emcip_mappings"
)

JOB_NAME = (
    "Investigation KG - Propose EMCIP Mappings"
)

# COMMAND ----------

jobs = w.api_client.do(
    "GET",
    "/api/2.2/jobs/list?limit=100",
)

existing_job_id = None

for job in jobs.get("jobs", []):
    settings = job.get("settings") or {}
    if settings.get("name") == JOB_NAME:
        existing_job_id = job.get(
            "job_id"
        )
        break

print("Existing job:", existing_job_id)

# COMMAND ----------

job_settings = {
    "name": JOB_NAME,
    "description": (
        "On-demand generic EMCIP mapping proposals over one completed "
        "AnalysisGroup/ModelRun using the MAIRA taxonomy registry."
    ),
    "parameters": [
        {
            "name": "analysis_id",
            "default": "analysis_NOT_SET",
        },
        {
            "name": "model_run_id",
            "default": "model_run_NOT_SET",
        },
    ],
    "tasks": [
        {
            "task_key": "propose_emcip_mappings",
            "description": (
                "Create bounded assistant mapping proposals from the "
                "governed MAIRA EMCIP registry."
            ),
            "notebook_task": {
                "notebook_path": NOTEBOOK_40_PATH,
                "source": "WORKSPACE",
                "base_parameters": {
                    "analysis_id": (
                        "{{job.parameters.analysis_id}}"
                    ),
                    "model_run_id": (
                        "{{job.parameters.model_run_id}}"
                    ),
                },
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
    print("Updated job:", job_id)

# COMMAND ----------

print("")
print("EMCIP MAPPING PROPOSAL JOB READY")
print("job_id:", job_id)
print("resource key: emcip_mapping_job")
print("required App permission: Can manage run")
