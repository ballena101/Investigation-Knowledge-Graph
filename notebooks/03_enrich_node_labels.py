# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Enrich Neo4j node labels

# COMMAND ----------

from pyspark.sql import functions as F
from neo4j import GraphDatabase

CASE_ID = "commodore_clipper_2010"
INVESTIGATOR_VIEW_TABLE = (
    "bdw_analysis_prod.maira.workshop_kg_cc_v02_investigator_view"
)

iv = spark.table(INVESTIGATOR_VIEW_TABLE)

node_labels_df = (
    iv.select(
        F.col("source_node_id").alias("node_id"),
        F.col("source_label").alias("label"),
    )
    .union(
        iv.select(
            F.col("target_node_id").alias("node_id"),
            F.col("target_label").alias("label"),
        )
    )
    .dropDuplicates(["node_id"])
)

label_rows = [row.asDict() for row in node_labels_df.collect()]
print("Labels to publish:", len(label_rows))

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
        MATCH (n:KGNode {node_id: row.node_id})
        SET n.label = row.label
        """,
        rows=label_rows,
    )

with driver.session() as session:
    result = session.run(
        """
        MATCH (n:KGNode {case_id: $case_id})
        RETURN
            count(n) AS total_nodes,
            count(n.label) AS nodes_with_label,
            collect(n.label)[0..6] AS sample_labels
        """,
        case_id=CASE_ID,
    ).single()

print("Total nodes:", result["total_nodes"])
print("Nodes with readable label:", result["nodes_with_label"])
print("Examples:", result["sample_labels"])

driver.close()
