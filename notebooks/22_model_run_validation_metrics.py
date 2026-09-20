# Databricks notebook source
# MAGIC %md
# MAGIC # 22 — Model-run validation metrics
# MAGIC
# MAGIC Computes human-review metrics for GPT-OSS 20B / Llama 3.3 70B
# MAGIC model-run graphs once generic model-run relationship reviews exist.
# MAGIC
# MAGIC This notebook does not create a model score from unreviewed output.

# COMMAND ----------

dbutils.widgets.text(
    "analysis_id",
    "",
    "Analysis ID (optional)",
)

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

from neo4j import GraphDatabase
from pyspark.sql import Row

analysis_id = dbutils.widgets.get(
    "analysis_id"
).strip()

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

model_run_query = """
MATCH (a:AnalysisGroup)-[:HAS_MODEL_RUN]->(m:ModelRun)
WHERE $analysis_id = ''
   OR a.analysis_id = $analysis_id
OPTIONAL MATCH (n:KGNode {
    analysis_id: a.analysis_id,
    model_run_id: m.model_run_id
})-[r]->(:KGNode {
    analysis_id: a.analysis_id,
    model_run_id: m.model_run_id
})
WITH
    a,
    m,
    count(DISTINCT r) AS generated_relationships
OPTIONAL MATCH (review:RelationshipReview)
WHERE review.analysis_id = a.analysis_id
  AND review.model_run_id = m.model_run_id
WITH
    a,
    m,
    generated_relationships,
    collect(review) AS reviews
RETURN
    a.analysis_id AS analysis_id,
    a.analysis_title AS analysis_title,
    m.model_run_id AS model_run_id,
    m.model_key AS model_key,
    m.model_label AS model_label,
    m.model_service AS model_service,
    generated_relationships,
    size(reviews) AS reviewed_relationships,
    size([
        x IN reviews
        WHERE x.human_review_decision = 'VALIDATED'
    ]) AS validated,
    size([
        x IN reviews
        WHERE x.human_review_decision = 'REJECTED'
    ]) AS rejected,
    size([
        x IN reviews
        WHERE x.human_review_decision = 'AMENDED'
    ]) AS amended,
    coalesce(
        properties(m)["privacy_redaction_count"],
        0
    ) AS privacy_redactions,
    properties(m)["privacy_validation_status"]
        AS privacy_validation_status
ORDER BY
    a.analysis_id,
    m.model_key
"""

with driver.session() as session:
    records = [
        record.data()
        for record in session.run(
            model_run_query,
            analysis_id=analysis_id,
        )
    ]

# COMMAND ----------

rows = []

for record in records:
    generated = int(
        record["generated_relationships"]
        or 0
    )
    reviewed = int(
        record["reviewed_relationships"]
        or 0
    )
    validated = int(
        record["validated"]
        or 0
    )
    rejected = int(
        record["rejected"]
        or 0
    )
    amended = int(
        record["amended"]
        or 0
    )

    acceptance_rate = (
        validated / reviewed
        if reviewed
        else None
    )
    rejection_rate = (
        rejected / reviewed
        if reviewed
        else None
    )
    amendment_rate = (
        amended / reviewed
        if reviewed
        else None
    )
    review_coverage = (
        reviewed / generated
        if generated
        else None
    )

    rows.append(
        Row(
            analysis_id=record[
                "analysis_id"
            ],
            model_run_id=record[
                "model_run_id"
            ],
            model_key=record[
                "model_key"
            ],
            model_label=record[
                "model_label"
            ],
            model_service=record[
                "model_service"
            ],
            generated_relationships=generated,
            reviewed_relationships=reviewed,
            review_coverage=review_coverage,
            validated=validated,
            rejected=rejected,
            amended=amended,
            acceptance_rate=acceptance_rate,
            rejection_rate=rejection_rate,
            amendment_rate=amendment_rate,
            privacy_redactions=int(
                record[
                    "privacy_redactions"
                ]
                or 0
            ),
            privacy_validation_status=record[
                "privacy_validation_status"
            ],
        )
    )

if rows:
    display(
        spark.createDataFrame(
            rows
        )
    )
else:
    print(
        "No ModelRun records found for the selected scope."
    )

# COMMAND ----------

print("")
print("VALIDATION INTERPRETATION")
print(
    "- No model-performance conclusion should be drawn until human-review "
    "coverage is sufficient."
)
print(
    "- Acceptance rate alone is not enough: causal-overreach, evidence "
    "grounding, privacy leakage and graph completeness must also be measured."
)
print(
    "- RelationshipReview records must include analysis_id and model_run_id "
    "for generic model-run validation."
)

driver.close()
