# Databricks notebook source
# MAGIC %md
# MAGIC # 65 — Type D audio transcription / publication job
# MAGIC
# MAGIC Reusable Lakeflow Job entry point used by the investigation App.
# MAGIC
# MAGIC Supported transcription technologies:
# MAGIC - faster-whisper 1.2.1 — Whisper large-v3-turbo / large-v3;
# MAGIC - NVIDIA Parakeet TDT 0.6B v3 — via Hugging Face Transformers.
# MAGIC
# MAGIC The App passes only an opaque `transcription_run_id` or `review_id`.
# MAGIC Protected source paths and reviewed transcript text are resolved inside the
# MAGIC governed worker and are **not** exposed as Lakeflow Job parameters.
# MAGIC
# MAGIC Actions:
# MAGIC - `TRANSCRIBE` — transcribe the audio attached to a governed TranscriptionRun;
# MAGIC - `PUBLISH_REVIEW` — publish a human-reviewed transcript as a normal Class D
# MAGIC   SourceDocument backed by a governed TXT file.
# MAGIC
# MAGIC No LLM is called and no graph knowledge is created by this Job.

# COMMAND ----------

# Parakeet's Transformers route requires PyTorch. The current serverless runtime
# does not provide torch, so use the CPU wheel source explicitly. This keeps the
# environment compatible with the validated CPU-first transcription design and
# avoids installing unused CUDA packages.
# MAGIC %pip install "torch>=2.6,<3" --index-url https://download.pytorch.org/whl/cpu

# COMMAND ----------

# Transformers 5.17.0 is pinned because the current NVIDIA Parakeet model is
# supported by the Transformers automatic-speech-recognition pipeline.
# Version-range requirements are quoted because Databricks executes %pip through
# a shell and unquoted '<' / '>' can be interpreted as shell redirection.
# MAGIC %pip install faster-whisper==1.2.1 transformers==5.17.0 "safetensors>=0.4" "huggingface-hub>=0.34,<2" neo4j==6.3.1 cryptography==46.0.2

# COMMAND ----------

# Load the freshly installed transcription dependencies before creating widgets
# or reading any protected job parameters.
dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.dropdown(
    "action",
    "TRANSCRIBE",
    ["TRANSCRIBE", "PUBLISH_REVIEW"],
    "Action",
)
dbutils.widgets.text("transcription_run_id", "", "Transcription run ID")
dbutils.widgets.text("review_id", "", "Transcript review ID")

# COMMAND ----------

import os
import sys

current_notebook_path = (
    dbutils.notebook.entry_point
    .getDbutils()
    .notebook()
    .getContext()
    .notebookPath()
    .get()
)
workspace_notebook_path = (
    "/Workspace" + current_notebook_path
    if current_notebook_path.startswith("/Users/")
    else current_notebook_path
)
ikf_repo_root = workspace_notebook_path.rsplit("/notebooks/", 1)[0]
ikf_src_path = os.path.join(ikf_repo_root, "src")
if ikf_src_path not in sys.path:
    sys.path.insert(0, ikf_src_path)

from ikf.transcription_worker import run_transcription_action

ACTION = dbutils.widgets.get("action").strip().upper()
TRANSCRIPTION_RUN_ID = dbutils.widgets.get("transcription_run_id").strip()
REVIEW_ID = dbutils.widgets.get("review_id").strip()

NEO4J_URI = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_uri")
NEO4J_USERNAME = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_username")
NEO4J_PASSWORD = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_password")
DIRECT_TEXT_ENCRYPTION_KEY = dbutils.secrets.get(
    scope="kg-poc-app",
    key="direct_text_encryption_key",
)

HF_TOKEN = None
if ACTION == "TRANSCRIBE":
    HF_TOKEN = dbutils.secrets.get(
        catalog="bdw_analysis_prod",
        schema="kg_poc",
        key="huggingface_read_token",
    )

result = run_transcription_action(
    action=ACTION,
    transcription_run_id=TRANSCRIPTION_RUN_ID,
    review_id=REVIEW_ID,
    neo4j_uri=NEO4J_URI,
    neo4j_username=NEO4J_USERNAME,
    neo4j_password=NEO4J_PASSWORD,
    encryption_key=DIRECT_TEXT_ENCRYPTION_KEY,
    hf_token=HF_TOKEN,
)

print("Type D transcription action completed")
print(result)
