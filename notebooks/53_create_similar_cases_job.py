# Databricks notebook source
# MAGIC %md
# MAGIC # 53 — Create Similar MAIRA Cases Lakeflow Job
# MAGIC
# MAGIC One-time setup for deterministic similar-case discovery.
# MAGIC
# MAGIC The Job runs notebook 52 only. It does not invoke an LLM.

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

NOTEBOOK_52_PATH = (
    f"{notebooks_dir}/52_find_similar_maira_cases"
)

JOB_NAME = (
    "Investigation KG - Similar MAIRA Cases"
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
        "Deterministic similar-case retrieval over MAIRA "
        "INVESTIGATION / MAIN_REPORT passages."
    ),
    "parameters": [
        {
            "name": "analysis_id",
            "default": "analysis_NOT_SET",
        },
    ],
    "tasks": [
        {
            "task_key":
                "find_similar_maira_cases",
            "notebook_task": {
                "notebook_path":
                    NOTEBOOK_52_PATH,
                "source":
                    "WORKSPACE",
                "base_parameters": {
                    "analysis_id":
                        "{{job.parameters.analysis_id}}",
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
    "SIMILAR MAIRA CASES JOB READY"
)
print(
    "job_id:",
    job_id,
)
print(
    "resource key: similar_cases_job"
)
print(
    "permission: Can manage run"
)
