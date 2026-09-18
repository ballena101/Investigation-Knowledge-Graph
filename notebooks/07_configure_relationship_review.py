# Databricks notebook source
# MAGIC %md
# MAGIC # 07 — Enable relationship review in Neo4j
# MAGIC
# MAGIC The Databricks App uses the same Neo4j credentials already configured for
# MAGIC graph exploration. Human relationship reviews are stored as separate,
# MAGIC append-only RelationshipReview nodes.
# MAGIC
# MAGIC This avoids requiring a SQL warehouse or additional Databricks App
# MAGIC resources for the current PoC.

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

print("Neo4j connection established.")

# COMMAND ----------

# Optional but recommended uniqueness constraint for review IDs.

with driver.session() as session:
    session.run("""
        CREATE CONSTRAINT relationship_review_id_unique
        IF NOT EXISTS
        FOR (r:RelationshipReview)
        REQUIRE r.review_id IS UNIQUE
    """)

print("RelationshipReview constraint ready.")

# COMMAND ----------

# Safe write-capability test: create and immediately remove one temporary node.

TEST_ID = "__kg_poc_review_write_test__"

with driver.session() as session:
    session.run(
        """
        MERGE (r:RelationshipReview {review_id: $review_id})
        SET r.test_only = true
        """,
        review_id=TEST_ID,
    )

    count = session.run(
        """
        MATCH (r:RelationshipReview {review_id: $review_id})
        RETURN count(r) AS count
        """,
        review_id=TEST_ID,
    ).single()["count"]

    session.run(
        """
        MATCH (r:RelationshipReview {review_id: $review_id})
        DETACH DELETE r
        """,
        review_id=TEST_ID,
    )

if count != 1:
    raise RuntimeError("Neo4j write test did not create exactly one temporary review node.")

print("Neo4j write capability confirmed.")
print("Temporary test node removed.")

driver.close()
