# Databricks notebook source
# MAGIC %md
# MAGIC # 37 — Create Ask / Compare Lakeflow Job
# MAGIC
# MAGIC One-time setup for scoped free-text questions against already processed
# MAGIC IKF evidence.
# MAGIC
# MAGIC The Job has one task only:
# MAGIC
# MAGIC 1. `36_ask_processed_evidence`
# MAGIC
# MAGIC It does **not** rerun evidence extraction and does **not** rebuild the
# MAGIC knowledge graph.

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
NOTEBOOK_36_PATH = f"{notebooks_dir}/36_ask_processed_evidence"

print("Ask notebook:", NOTEBOOK_36_PATH)

# COMMAND ----------

JOB_NAME = "Investigation KG - Ask Processed Evidence"

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

print("Existing job:", existing_job_id)

# COMMAND ----------

job_settings = {
    "name": JOB_NAME,
    "description": (
        "Scoped free-text question answering over already processed IKF "
        "evidence. Does not re-extract documents or rebuild the graph."
    ),
    "parameters": [
        {
            "name": "question_run_id",
            "default": "question_NOT_SET",
        },
    ],
    "tasks": [
        {
            "task_key": "answer_question",
            "description": (
                "Answer one persisted QuestionRun from the already prepared "
                "analysis passages and persist document/page citations."
            ),
            "notebook_task": {
                "notebook_path": NOTEBOOK_36_PATH,
                "source": "WORKSPACE",
                "base_parameters": {
                    "question_run_id": (
                        "{{job.parameters.question_run_id}}"
                    ),
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
print("ASK JOB READY")
print("job_id:", job_id)
print("name:", (job.get("settings") or {}).get("name"))
print("")
print("Next deployment setup:")
print(
    "Apps > investigation-kg-poc > Edit > Resources > "
    "Add resource > Job"
)
print("Select:", JOB_NAME)
print("Permission: Can manage run")
print("Resource key: ask_job")
