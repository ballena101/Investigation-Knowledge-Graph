# Databricks notebook source
# MAGIC %md
# MAGIC # 23 — Purge expired analytical artefacts
# MAGIC
# MAGIC Retention policy:
# MAGIC - raw Class D source ingress: separate maximum 24-hour rule;
# MAGIC - direct-text raw buffer: purge immediately after successful extraction;
# MAGIC - derived/digested analytical artefacts: 72 hours by default;
# MAGIC - analyses explicitly retained for validation are excluded from purge.
# MAGIC
# MAGIC This notebook removes expired analytical content while preserving
# MAGIC minimal audit metadata on the AnalysisGroup.

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

from datetime import datetime, timezone

from neo4j import GraphDatabase

DERIVED_TABLES = [
    "bdw_analysis_prod.kg_poc.analysis_passage",
    "bdw_analysis_prod.kg_poc.analysis_candidate",
    "bdw_analysis_prod.kg_poc.analysis_candidate_relationship",
    "bdw_analysis_prod.kg_poc.analysis_summary",
]

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

print("Neo4j connection: OK")

# COMMAND ----------

with driver.session() as session:
    expired = [
        record.data()
        for record in session.run(
            """
            MATCH (a:AnalysisGroup)
            WHERE
                coalesce(a.retention_policy, '') = 'TRANSIENT_72H'
                AND coalesce(a.retain_for_validation, false) = false
                AND a.derived_expires_at IS NOT NULL
                AND a.derived_expires_at <= datetime()
                AND a.status IN ['COMPLETED', 'FAILED']
                AND coalesce(a.retention_purge_status, 'ACTIVE') <> 'PURGED'
            RETURN
                a.analysis_id AS analysis_id,
                a.status AS status,
                toString(a.derived_expires_at) AS derived_expires_at
            ORDER BY a.derived_expires_at
            """
        )
    ]

print("Expired analyses:", len(expired))
for item in expired:
    print(
        item["analysis_id"],
        item["status"],
        item["derived_expires_at"],
    )

# COMMAND ----------

for item in expired:
    analysis_id = item["analysis_id"]

    print("")
    print("Purging:", analysis_id)

    # Remove governed derived rows from Delta.
    for table_name in DERIVED_TABLES:
        if spark.catalog.tableExists(table_name):
            spark.sql(
                f"""
                DELETE FROM {table_name}
                WHERE analysis_id = '{analysis_id}'
                """
            )
            print("  Delta purged:", table_name)

    # Remove generated graph content and transient direct-text source nodes.
    # Preserve AnalysisGroup and compact ModelRun audit metadata.
    with driver.session() as session:
        session.run(
            """
            MATCH (n:KGNode {analysis_id: $analysis_id})
            DETACH DELETE n
            """,
            analysis_id=analysis_id,
        ).consume()

        session.run(
            """
            MATCH (s:DirectTextSource {analysis_id: $analysis_id})
            DETACH DELETE s
            """,
            analysis_id=analysis_id,
        ).consume()

        session.run(
            """
            MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
            OPTIONAL MATCH (a)-[:HAS_MODEL_RUN]->(m:ModelRun)
            REMOVE
                m.analysis_summary,
                m.key_findings,
                m.uncertainties,
                m.source_conflicts,
                m.raw_response,
                m.prompt_text,
                m.response_text
            SET
                m.derived_content_purged_at = datetime()
            """,
            analysis_id=analysis_id,
        ).consume()

        session.run(
            """
            MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
            REMOVE
                a.analysis_summary,
                a.key_findings,
                a.uncertainties,
                a.source_conflicts,
                a.processing_error
            SET
                a.retention_purge_status = 'PURGED',
                a.derived_content_purged = true,
                a.derived_purged_at = datetime(),
                a.processing_updated_at = datetime()
            """,
            analysis_id=analysis_id,
        ).consume()

    print("  Neo4j analytical content purged")

print("")
print("RETENTION CLEANUP COMPLETE")
print("Purged analyses:", len(expired))
print(
    "Minimal metadata/hashes/review governance remain. "
    "Analyses retained for validation were not touched."
)

driver.close()
