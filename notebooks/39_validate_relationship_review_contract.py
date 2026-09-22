# Databricks notebook source
# MAGIC %md
# MAGIC # 39 — Validate generic relationship-review contract
# MAGIC
# MAGIC Read-only validation of human relationship reviews.
# MAGIC
# MAGIC Confirms that each review:
# MAGIC - belongs to an AnalysisGroup;
# MAGIC - preserves model-run provenance;
# MAGIC - points to source/target KG nodes from that same analysis/model run;
# MAGIC - refers to an existing graph relationship with the recorded edge ID;
# MAGIC - preserves the original relationship type;
# MAGIC - is stored as a separate append-only review record rather than mutating
# MAGIC   the graph relationship.

# COMMAND ----------

dbutils.widgets.text(
    "analysis_id",
    "",
    "Analysis ID (optional)",
)

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1

# COMMAND ----------

import re

from neo4j import GraphDatabase

analysis_id = dbutils.widgets.get(
    "analysis_id"
).strip()

if analysis_id and not re.fullmatch(
    r"analysis_[0-9a-f]{32}",
    analysis_id,
):
    raise ValueError(
        "analysis_id must be blank or analysis_<32 hex>."
    )

# COMMAND ----------

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

where_clause = (
    "WHERE review.analysis_id = $analysis_id"
    if analysis_id
    else ""
)

query = f"""
MATCH (review:RelationshipReview)
{where_clause}
OPTIONAL MATCH (a:AnalysisGroup {{
    analysis_id: review.analysis_id
}})-[:HAS_RELATIONSHIP_REVIEW]->(review)
OPTIONAL MATCH (review)-[:REVIEWS_SOURCE]->(source:KGNode)
OPTIONAL MATCH (review)-[:REVIEWS_TARGET]->(target:KGNode)
RETURN
    review.review_id AS review_id,
    review.analysis_id AS analysis_id,
    review.model_run_id AS model_run_id,
    review.edge_id AS edge_id,
    review.original_relationship AS original_relationship,
    review.human_review_decision AS decision,
    review.human_review_status AS status,
    a.analysis_id AS linked_analysis_id,
    source.node_id AS source_node_id,
    source.analysis_id AS source_analysis_id,
    source.model_run_id AS source_model_run_id,
    target.node_id AS target_node_id,
    target.analysis_id AS target_analysis_id,
    target.model_run_id AS target_model_run_id,
    toString(review.reviewed_at) AS reviewed_at
ORDER BY review.reviewed_at, review.review_id
"""

with driver.session() as session:
    reviews = [
        record.data()
        for record in session.run(
            query,
            analysis_id=analysis_id or None,
        )
    ]

print("Relationship reviews:", len(reviews))

if not reviews:
    print(
        "No relationship reviews are available for the selected scope."
    )
    driver.close()
    dbutils.notebook.exit(
        "NO_RELATIONSHIP_REVIEWS"
    )

# COMMAND ----------

validation_rows = []
errors = []

with driver.session() as session:
    for review in reviews:
        review_errors = []

        if (
            review["linked_analysis_id"]
            != review["analysis_id"]
        ):
            review_errors.append(
                "review is not linked from its AnalysisGroup"
            )

        if not review.get("model_run_id"):
            review_errors.append(
                "model_run_id is missing"
            )

        for side in ("source", "target"):
            if (
                review.get(
                    f"{side}_analysis_id"
                )
                != review["analysis_id"]
            ):
                review_errors.append(
                    f"{side} node analysis_id mismatch"
                )

            if (
                review.get(
                    f"{side}_model_run_id"
                )
                != review.get("model_run_id")
            ):
                review_errors.append(
                    f"{side} node model_run_id mismatch"
                )

        edge_record = session.run(
            """
            MATCH (source:KGNode {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                node_id: $source_node_id
            })-[r]->(target:KGNode {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                node_id: $target_node_id
            })
            WHERE r.edge_id = $edge_id
            RETURN
                type(r) AS relationship,
                r.evidence_status AS evidence_status
            """,
            analysis_id=review["analysis_id"],
            model_run_id=review["model_run_id"],
            source_node_id=review["source_node_id"],
            target_node_id=review["target_node_id"],
            edge_id=review["edge_id"],
        ).single()

        if edge_record is None:
            review_errors.append(
                "reviewed graph relationship not found"
            )
        elif (
            edge_record["relationship"]
            != review["original_relationship"]
        ):
            review_errors.append(
                "original_relationship does not match graph relationship"
            )

        validation_rows.append(
            {
                "review_id": review["review_id"],
                "analysis_id": review["analysis_id"],
                "model_run_id": review["model_run_id"],
                "edge_id": review["edge_id"],
                "decision": review["decision"],
                "errors": len(review_errors),
                "error_detail": " | ".join(
                    review_errors
                ),
            }
        )

        errors.extend(
            f"{review['review_id']}: {value}"
            for value in review_errors
        )

display(
    spark.createDataFrame(
        validation_rows
    )
)

# COMMAND ----------

if errors:
    print("")
    print("VALIDATION ERRORS")
    for error in errors:
        print(" -", error)

    driver.close()
    raise RuntimeError(
        "Generic relationship-review validation failed."
    )

print("")
print("PASS — GENERIC RELATIONSHIP REVIEWS PRESERVE ANALYSIS AND MODEL PROVENANCE")
print("reviews:", len(reviews))

driver.close()
