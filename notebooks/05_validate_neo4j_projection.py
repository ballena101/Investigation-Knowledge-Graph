# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — Validate Neo4j projection

# COMMAND ----------

from neo4j import GraphDatabase

CASE_ID = "commodore_clipper_2010"

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
    result = session.run(
        """
        MATCH (n:KGNode {case_id: $case_id})
        WITH count(n) AS nodes
        MATCH (:KGNode {case_id: $case_id})-[r]->
              (:KGNode {case_id: $case_id})
        RETURN
            nodes,
            count(r) AS relationships,
            count(
                CASE
                    WHEN r.evidence_status = 'ASSISTANT_VALIDATED'
                    THEN 1
                END
            ) AS validated_relationships
        """,
        case_id=CASE_ID,
    ).single()

print("Nodes:", result["nodes"])
print("Relationships:", result["relationships"])
print("Evidence-validated:", result["validated_relationships"])

assert result["nodes"] == 17
assert result["relationships"] == 12
assert result["validated_relationships"] == 11

print("Projection validation passed.")

driver.close()
