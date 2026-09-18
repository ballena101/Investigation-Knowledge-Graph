# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Neo4j connection test
# MAGIC Standalone Investigation Knowledge Graph PoC.

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

import neo4j
from neo4j import GraphDatabase

print("Neo4j driver version:", neo4j.__version__)

# COMMAND ----------

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

driver.close()
