# Databricks notebook source
# MAGIC %md
# MAGIC # 08 — Configure EMCIP mapping review
# MAGIC
# MAGIC Human EMCIP mapping reviews are stored in Neo4j as append-only
# MAGIC EMCIPMappingReview nodes. This notebook creates the uniqueness
# MAGIC constraint used by the App.
# MAGIC
# MAGIC The original EMCIP mapping on the KG node is not overwritten.

# COMMAND ----------

from neo4j import GraphDatabase

NEO4J_URI = dbutils.secrets.get(
    catalog="bdw_analysis_prod",
    schema="kg_poc",
    key="neo4j_uri",
)
NEO4J_USERNAME = dbutils.secrets.get(
    catalog="bdw_analysis_prod",
    schema="kg_poc",
    key="neo4j_username",
)
NEO4J_PASSWORD = dbutils.secrets.get(
    catalog="bdw_analysis_prod",
    schema="kg_poc",
    key="neo4j_password",
)

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
)
driver.verify_connectivity()

# COMMAND ----------

with driver.session() as session:
    session.run("""
        CREATE CONSTRAINT emcip_mapping_review_id_unique
        IF NOT EXISTS
        FOR (r:EMCIPMappingReview)
        REQUIRE r.review_id IS UNIQUE
    """)

print("EMCIPMappingReview constraint ready.")

# COMMAND ----------

with driver.session() as session:
    count = session.run("""
        MATCH (r:EMCIPMappingReview)
        RETURN count(r) AS count
    """).single()["count"]

print("Existing EMCIP mapping review records:", count)

driver.close()
