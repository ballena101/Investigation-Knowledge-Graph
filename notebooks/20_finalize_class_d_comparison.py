# Databricks notebook source
# MAGIC %md
# MAGIC # 20 — Finalize Class D dual-model comparison
# MAGIC
# MAGIC Marks the Class D analysis complete only after the requested model run(s)
# MAGIC have completed successfully.

# COMMAND ----------

dbutils.widgets.text("analysis_id", "", "Analysis ID")
dbutils.widgets.dropdown(
    "model_selection",
    "BOTH",
    ["GPT20", "LLAMA70", "BOTH"],
    "Model selection",
)

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

from neo4j import GraphDatabase

analysis_id = dbutils.widgets.get("analysis_id").strip()
model_selection = dbutils.widgets.get("model_selection").strip()

expected_keys = {
    "GPT20": {"GPT20"},
    "LLAMA70": {"LLAMA70"},
    "BOTH": {"GPT20", "LLAMA70"},
}[model_selection]

NEO4J_URI = dbutils.secrets.get(
    scope="kg-poc-app",
    key="neo4j_uri",
)
NEO4J_USERNAME = dbutils.secrets.get(
    scope="kg-poc-app",
    key="neo4j_username",
)
NEO4J_PASSWORD = dbutils.secrets.get(
    scope="kg-poc-app",
    key="neo4j_password",
)

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
)
driver.verify_connectivity()

# COMMAND ----------

with driver.session() as session:
    records = [
        record.data()
        for record in session.run(
            """
            MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
            OPTIONAL MATCH (a)-[:HAS_MODEL_RUN]->(m:ModelRun)
            RETURN
                m.model_key AS model_key,
                m.status AS status,
                properties(m)["model_service"] AS model_service,
                properties(m)["graph_node_count"] AS graph_node_count,
                properties(m)["graph_relationship_count"] AS graph_relationship_count
            """,
            analysis_id=analysis_id,
        )
        if record["model_key"] is not None
    ]

runs = {
    record["model_key"]: record
    for record in records
}

missing = sorted(
    expected_keys - set(runs)
)
failed = sorted(
    key
    for key in expected_keys
    if runs.get(key, {}).get("status") == "FAILED"
)
incomplete = sorted(
    key
    for key in expected_keys
    if runs.get(key, {}).get("status") != "COMPLETED"
)

if missing or failed or incomplete:
    message = (
        f"missing={missing}; failed={failed}; incomplete={incomplete}"
    )

    with driver.session() as session:
        session.run(
            """
            MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
            SET
                a.status = 'FAILED',
                a.processing_stage = 'MODEL_COMPARISON_FAILED',
                a.processing_error = $message,
                a.processing_updated_at = datetime()
            """,
            analysis_id=analysis_id,
            message=message,
        ).consume()

    driver.close()
    raise RuntimeError(
        "Class D comparison did not complete successfully: "
        + message
    )

# COMMAND ----------

with driver.session() as session:
    session.run(
        """
        MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
        SET
            a.status = 'COMPLETED',
            a.processing_stage = 'COMPLETED',
            a.comparison_mode = $comparison_mode,
            a.model_run_count = $model_run_count,
            a.completed_at = datetime(),
            a.processing_updated_at = datetime(),
            a.processing_error = NULL
        """,
        analysis_id=analysis_id,
        comparison_mode=model_selection,
        model_run_count=len(expected_keys),
    ).consume()

print("CLASS D COMPARISON COMPLETE")
print("analysis_id:", analysis_id)
print("model_selection:", model_selection)

for key in sorted(expected_keys):
    run = runs[key]
    print(
        key,
        "| nodes:",
        run.get("graph_node_count"),
        "| relationships:",
        run.get("graph_relationship_count"),
    )

driver.close()
