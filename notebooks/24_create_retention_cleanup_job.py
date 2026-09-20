# Databricks notebook source
# MAGIC %md
# MAGIC # 24 — Create derived-data retention cleanup Job
# MAGIC
# MAGIC One-time setup.
# MAGIC
# MAGIC Creates/updates an hourly Lakeflow Job that executes notebook 23 and
# MAGIC purges eligible derived analytical artefacts after the 72-hour window.
# MAGIC Analyses explicitly retained for validation are excluded.

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
PURGE_NOTEBOOK_PATH = (
    f"{notebooks_dir}/23_purge_expired_analysis_artifacts"
)

JOB_NAME = "Investigation KG - Retention Cleanup"

# COMMAND ----------

jobs = w.api_client.do(
    "GET",
    "/api/2.2/jobs/list?limit=100",
)

existing_job_id = None

for job in jobs.get("jobs", []):
    settings = job.get("settings") or {}
    if settings.get("name") == JOB_NAME:
        existing_job_id = job.get("job_id")
        break

job_settings = {
    "name": JOB_NAME,
    "description": (
        "Hourly cleanup of IKG derived/digested analytical artefacts "
        "after the default 72-hour retention window."
    ),
    "tasks": [
        {
            "task_key": "purge_expired_analysis_artifacts",
            "notebook_task": {
                "notebook_path": PURGE_NOTEBOOK_PATH,
                "source": "WORKSPACE",
            },
            "timeout_seconds": 0,
            "max_retries": 1,
        }
    ],
    "schedule": {
        "quartz_cron_expression": "0 15 * * * ?",
        "timezone_id": "Europe/Lisbon",
        "pause_status": "UNPAUSED",
    },
    "max_concurrent_runs": 1,
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

print("")
print("RETENTION CLEANUP JOB READY")
print("job_id:", job_id)
print("schedule: hourly at minute 15")
print("timezone: Europe/Lisbon")
print("default derived retention: 72 hours")
