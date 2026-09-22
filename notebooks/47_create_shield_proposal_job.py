# Databricks notebook source
# MAGIC %md
# MAGIC # 47 — Create SHIELD proposal Lakeflow Job
# MAGIC
# MAGIC One-time setup.
# MAGIC
# MAGIC Generates SHIELD assistant proposals only for contributing factors that
# MAGIC already passed Gate 1 human validation.

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

NOTEBOOK_46_PATH = (
    f"{notebooks_dir}/46_propose_shield_classifications"
)

JOB_NAME = (
    "Investigation KG - SHIELD Proposals"
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
        "Generate assistant SHIELD classification proposals only for "
        "human-validated contributing factors."
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
            "task_key":
                "propose_shield_classifications",
            "notebook_task": {
                "notebook_path":
                    NOTEBOOK_46_PATH,
                "source":
                    "WORKSPACE",
                "base_parameters": {
                    "analysis_id":
                        "{{job.parameters.analysis_id}}",
                    "model_run_id":
                        "{{job.parameters.model_run_id}}",
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
    "SHIELD PROPOSAL JOB READY"
)
print(
    "job_id:",
    job_id,
)
print(
    "resource key: shield_proposal_job"
)
print(
    "permission: Can manage run"
)
