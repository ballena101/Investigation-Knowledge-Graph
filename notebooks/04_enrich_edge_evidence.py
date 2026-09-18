# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Enrich Neo4j relationships with evidence

# COMMAND ----------

from neo4j import GraphDatabase
from pyspark.sql import functions as F

CASE_ID = "commodore_clipper_2010"
INVESTIGATOR_VIEW_TABLE = (
    "bdw_analysis_prod.maira.workshop_kg_cc_v02_investigator_view"
)

iv = spark.table(INVESTIGATOR_VIEW_TABLE)

edge_projection = (
    iv
    .withColumn(
        "evidence_display",
        F.when(
            F.size(F.col("stronger_evidence")) > 0,
            F.concat_ws(" | ", F.col("stronger_evidence")),
        ).otherwise(F.col("passage_text"))
    )
    .select(
        "edge_id",
        "source_label",
        "relationship",
        "target_label",
        "edge_class",
        "evidence_status",
        "evidence_anchor",
        "evidence_display",
    )
)

edge_rows = [
    row.asDict(recursive=True)
    for row in edge_projection.collect()
]

print("Relationships to enrich:", len(edge_rows))

# COMMAND ----------

NEO4J_URI = dbutils.secrets.get(
    catalog="bdw_analysis_prod", schema="kg_poc", key="neo4j_uri"
)
NEO4J_USERNAME = dbutils.secrets.get(
    catalog="bdw_analysis_prod", schema="kg_poc", key="neo4j_username"
)
NEO4J_PASSWORD = dbutils.secrets.get(
    catalog="bdw_analysis_prod", schema="kg_poc", key="neo4j_password"
)

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
)
driver.verify_connectivity()

with driver.session() as session:
    session.run(
        """
        UNWIND $rows AS row
        MATCH ()-[r {edge_id: row.edge_id}]->()
        SET
            r.source_label = row.source_label,
            r.target_label = row.target_label,
            r.relationship_label = row.relationship,
            r.edge_class = row.edge_class,
            r.evidence_status = row.evidence_status,
            r.evidence_anchor = row.evidence_anchor,
            r.evidence = row.evidence_display
        """,
        rows=edge_rows,
    )

with driver.session() as session:
    result = session.run(
        """
        MATCH ()-[r]->()
        WHERE r.case_id = $case_id
        RETURN
            count(r) AS total_relationships,
            count(r.evidence) AS relationships_with_evidence,
            count(
                CASE
                    WHEN r.evidence_status = 'ASSISTANT_VALIDATED'
                    THEN 1
                END
            ) AS validated_relationships
        """,
        case_id=CASE_ID,
    ).single()

print("Total relationships:", result["total_relationships"])
print("Relationships with evidence:", result["relationships_with_evidence"])
print("Validated report relationships:", result["validated_relationships"])

driver.close()
