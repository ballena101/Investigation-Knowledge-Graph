# Databricks notebook source
# MAGIC %md
# MAGIC # 19 — Create Class D dual-model Lakeflow Job
# MAGIC
# MAGIC One-time setup for the Class D PoC.
# MAGIC
# MAGIC Workflow:
# MAGIC 1. extract evidence once;
# MAGIC 2. run GPT-OSS 20B against the same evidence/question when selected;
# MAGIC 3. run Llama 3.3 70B through its Databricks model service against the same evidence/question when selected;
# MAGIC 4. finalize only after the requested model runs complete.

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
NOTEBOOK_20_PATH = f"{notebooks_dir}/20_finalize_class_d_comparison"

JOB_NAME = "Investigation KG - Class D Dual Model"

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

print("Existing job:", existing_job_id)

# COMMAND ----------

job_settings = {
    "name": JOB_NAME,
    "description": (
        "Class D PoC: one evidence extraction followed by independent "
        "GPT-OSS 20B and/or Llama 3.3 70B Databricks model-service runs."
    ),
    "parameters": [
        {
            "name": "analysis_id",
            "default": "analysis_NOT_SET",
        },
        {
            "name": "model_selection",
            "default": "BOTH",
        },
        {
            "name": "gpt20_endpoint",
            "default": "__SKIP__",
        },
        {
            "name": "llama70_endpoint",
            "default": "__SKIP__",
        },
    ],
    "tasks": [
        {
            "task_key": "extract_evidence",
            "notebook_task": {
                "notebook_path": NOTEBOOK_15_PATH,
                "source": "WORKSPACE",
                "base_parameters": {
                    "analysis_id": "{{job.parameters.analysis_id}}",
                },
            },
            "timeout_seconds": 0,
            "max_retries": 0,
        },
        {
            "task_key": "analyse_gpt20",
            "depends_on": [
                {"task_key": "extract_evidence"}
            ],
            "notebook_task": {
                "notebook_path": NOTEBOOK_16_PATH,
                "source": "WORKSPACE",
                "base_parameters": {
                    "analysis_id": "{{job.parameters.analysis_id}}",
                    "model_service": "{{job.parameters.gpt20_endpoint}}",
                    "model_run_key": "GPT20",
                    "model_label": "GPT-OSS 20B",
                },
            },
            "timeout_seconds": 0,
            "max_retries": 0,
        },
        {
            "task_key": "analyse_llama70",
            "depends_on": [
                {"task_key": "extract_evidence"}
            ],
            "notebook_task": {
                "notebook_path": NOTEBOOK_16_PATH,
                "source": "WORKSPACE",
                "base_parameters": {
                    "analysis_id": "{{job.parameters.analysis_id}}",
                    "model_service": "{{job.parameters.llama70_endpoint}}",
                    "model_run_key": "LLAMA70",
                    "model_label": "Llama 3.3 70B",
                },
            },
            "timeout_seconds": 0,
            "max_retries": 0,
        },
        {
            "task_key": "finalize_comparison",
            "depends_on": [
                {"task_key": "analyse_gpt20"},
                {"task_key": "analyse_llama70"},
            ],
            "run_if": "ALL_DONE",
            "notebook_task": {
                "notebook_path": NOTEBOOK_20_PATH,
                "source": "WORKSPACE",
                "base_parameters": {
                    "analysis_id": "{{job.parameters.analysis_id}}",
                    "model_selection": "{{job.parameters.model_selection}}",
                },
            },
            "timeout_seconds": 0,
            "max_retries": 0,
        },
    ],
    "max_concurrent_runs": 4,
    "queue": {"enabled": True},
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
print("CLASS D DUAL-MODEL JOB READY")
print("job_id:", job_id)
print("resource key: class_d_analysis_job")
print("required App permission: Can manage run")
