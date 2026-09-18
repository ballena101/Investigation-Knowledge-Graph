# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Publish Commodore Clipper graph to Neo4j
# MAGIC
# MAGIC Publishes the reviewed Commodore Clipper CASE_GRAPH_V0.2 from persisted Delta tables.
# MAGIC Delta remains authoritative; Neo4j is a rebuildable graph projection.

# COMMAND ----------

from collections import defaultdict
from neo4j import GraphDatabase
from pyspark.sql import functions as F

CASE_ID = "commodore_clipper_2010"

NODES_TABLE = "bdw_analysis_prod.maira.workshop_kg_cc_v02_nodes"
INVESTIGATOR_VIEW_TABLE = (
    "bdw_analysis_prod.maira.workshop_kg_cc_v02_investigator_view"
)
MAPPING_DISPOSITION_TABLE = (
    "bdw_analysis_prod.maira.workshop_kg_cc_v02_mapping_disposition"
)
MAPPING_REVIEWED_TABLE = (
    "bdw_analysis_prod.maira.workshop_kg_cc_v02_emcip_mapping_reviewed"
)

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

# COMMAND ----------

mapping_df = (
    spark.table(MAPPING_REVIEWED_TABLE)
    .filter(F.col("review_status") == "ASSISTANT_VALIDATED")
    .groupBy("node_id")
    .agg(
        F.collect_list(
            F.concat_ws(
                " → ",
                F.col("emcip_entity"),
                F.concat(
                    F.col("attribute_name"),
                    F.lit(" = "),
                    F.col("code_value"),
                ),
            )
        ).alias("emcip_mappings")
    )
)

disp_raw = spark.table(MAPPING_DISPOSITION_TABLE)

possible_cols = [
    "mapping_disposition",
    "disposition",
    "mapping_status",
    "status",
]

disp_col = next(c for c in possible_cols if c in disp_raw.columns)

disp_df = disp_raw.select(
    "node_id",
    F.col(disp_col).alias("mapping_disposition"),
)

nodes_df = (
    spark.table(NODES_TABLE)
    .join(disp_df, on="node_id", how="left")
    .join(mapping_df, on="node_id", how="left")
)

# COMMAND ----------

node_rows = []

for row in nodes_df.collect():
    d = row.asDict(recursive=True)
    node_id = d["node_id"]

    if node_id.startswith("occ_"):
        node_kind = "Occurrence"
    elif node_id.startswith("ves_"):
        node_kind = "Vessel"
    elif node_id.startswith("cf_"):
        node_kind = "ContributingFactor"
    elif node_id.startswith("evt_"):
        node_kind = "Event"
    else:
        node_kind = "Concept"

    node_rows.append({
        "node_id": node_id,
        "case_id": d.get("case_id", CASE_ID),
        "graph_version": d.get("graph_version"),
        "label": d.get("node_label"),
        "node_kind": node_kind,
        "proposed_emcip_entity": d.get("proposed_emcip_entity"),
        "mapping_disposition": d.get("mapping_disposition"),
        "emcip_mappings": d.get("emcip_mappings") or [],
    })

edge_rows = []

for row in spark.table(INVESTIGATOR_VIEW_TABLE).collect():
    d = row.asDict(recursive=True)
    edge_rows.append({
        "edge_id": d["edge_id"],
        "case_id": d.get("case_id", CASE_ID),
        "graph_version": d.get("graph_version"),
        "source_node_id": d["source_node_id"],
        "target_node_id": d["target_node_id"],
        "relationship": d["relationship"],
        "edge_class": d.get("edge_class"),
        "evidence_status": d.get("evidence_status"),
        "evidence_anchor": d.get("evidence_anchor"),
        "passage_text": d.get("passage_text"),
    })

# COMMAND ----------

with driver.session() as session:
    session.run("""
        CREATE CONSTRAINT kg_node_id_unique
        IF NOT EXISTS
        FOR (n:KGNode)
        REQUIRE n.node_id IS UNIQUE
    """)

    session.run(
        """
        MATCH (n:KGNode {case_id: $case_id})
        DETACH DELETE n
        """,
        case_id=CASE_ID,
    )

# COMMAND ----------

nodes_by_kind = defaultdict(list)
for node in node_rows:
    nodes_by_kind[node["node_kind"]].append(node)

allowed_node_labels = {
    "Occurrence",
    "Vessel",
    "Event",
    "ContributingFactor",
    "Concept",
}

with driver.session() as session:
    for node_kind, rows in nodes_by_kind.items():
        if node_kind not in allowed_node_labels:
            raise ValueError(f"Unexpected node kind: {node_kind}")

        query = f"""
        UNWIND $rows AS row
        MERGE (n:KGNode:`{node_kind}` {{node_id: row.node_id}})
        SET
            n.case_id = row.case_id,
            n.graph_version = row.graph_version,
            n.label = row.label,
            n.node_kind = row.node_kind,
            n.proposed_emcip_entity = row.proposed_emcip_entity,
            n.mapping_disposition = row.mapping_disposition,
            n.emcip_mappings = row.emcip_mappings
        """
        session.run(query, rows=rows)

# COMMAND ----------

edges_by_type = defaultdict(list)
for edge in edge_rows:
    edges_by_type[edge["relationship"]].append(edge)

allowed_relationships = {
    "HAS_VESSEL",
    "RESULTED_IN",
    "AFFECTED",
    "CONTRIBUTED_TO",
}

with driver.session() as session:
    for rel_type, rows in edges_by_type.items():
        if rel_type not in allowed_relationships:
            raise ValueError(f"Unexpected relationship: {rel_type}")

        query = f"""
        UNWIND $rows AS row
        MATCH (source:KGNode {{node_id: row.source_node_id}})
        MATCH (target:KGNode {{node_id: row.target_node_id}})
        MERGE (source)-[r:`{rel_type}` {{edge_id: row.edge_id}}]->(target)
        SET
            r.case_id = row.case_id,
            r.graph_version = row.graph_version,
            r.edge_class = row.edge_class,
            r.evidence_status = row.evidence_status,
            r.evidence_anchor = row.evidence_anchor,
            r.passage_text = row.passage_text
        """
        session.run(query, rows=rows)

# COMMAND ----------

with driver.session() as session:
    node_count = session.run(
        """
        MATCH (n:KGNode {case_id: $case_id})
        RETURN count(n) AS count
        """,
        case_id=CASE_ID,
    ).single()["count"]

    relationship_count = session.run(
        """
        MATCH (:KGNode {case_id: $case_id})-[r]->
              (:KGNode {case_id: $case_id})
        RETURN count(r) AS count
        """,
        case_id=CASE_ID,
    ).single()["count"]

print("Neo4j nodes:", node_count)
print("Neo4j relationships:", relationship_count)

driver.close()
