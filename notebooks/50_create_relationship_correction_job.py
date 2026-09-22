# Databricks notebook source
# MAGIC %md
# MAGIC # 50 — Create relationship-correction Lakeflow Job
# MAGIC
# MAGIC One-time setup for evidence-bounded LLM review of one existing graph
# MAGIC relationship. The Job creates proposals only; it never edits the graph.

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

current_notebook = (
    dbutils.notebook.entry_point
    .getDbutils()
    .notebook()
    .getContext()
    .notebookPath()
    .get()
)

notebooks_dir = current_notebook.rsplit(
    "/",
    1,
)[0]

NOTEBOOK_49_PATH = (
    f"{notebooks_dir}/49_propose_relationship_correction"
)

JOB_NAME = (
    "Investigation KG - Relationship Correction"
)

# COMMAND ----------

jobs = w.api_client.do(
    "GET",
    "/api/2.2/jobs/list?limit=100",
)

existing_job_id = None

for job in jobs.get(
    "jobs",
    [],
):
    settings = (
        job.get("settings")
        or {}
    )

    if settings.get(
        "name"
    ) == JOB_NAME:
        existing_job_id = (
            job.get("job_id")
        )
        break

job_settings = {
    "name": JOB_NAME,
    "description": (
        "Evidence-bounded LLM relationship correction proposals. "
        "No graph relationship is modified."
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
        {
            "name": "edge_id",
            "default": "edge_NOT_SET",
        },
    ],
    "tasks": [
        {
            "task_key":
                "propose_relationship_correction",
            "notebook_task": {
                "notebook_path":
                    NOTEBOOK_49_PATH,
                "source":
                    "WORKSPACE",
                "base_parameters": {
                    "analysis_id":
                        "{{job.parameters.analysis_id}}",
                    "model_run_id":
                        "{{job.parameters.model_run_id}}",
                    "edge_id":
                        "{{job.parameters.edge_id}}",
                },
            },
            "timeout_seconds": 0,
            "max_retries": 0,
        },
    ],
    "max_concurrent_runs": 8,
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
    job_id = created[
        "job_id"
    ]
    print(
        "Created job:",
        job_id,
    )
else:
    w.api_client.do(
        "POST",
        "/api/2.2/jobs/reset",
        body={
            "job_id":
                existing_job_id,
            "new_settings":
                job_settings,
        },
    )
    job_id = existing_job_id
    print(
        "Updated job:",
        job_id,
    )

print("")
print(
    "RELATIONSHIP CORRECTION JOB READY"
)
print(
    "job_id:",
    job_id,
)
print(
    "resource key: relationship_correction_job"
)
print(
    "permission: Can manage run"
)
