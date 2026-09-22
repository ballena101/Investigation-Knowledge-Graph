# Databricks notebook source
# MAGIC %md
# MAGIC # 42 — Validate generic EMCIP proposal/review contract
# MAGIC
# MAGIC Read-only validation.
# MAGIC
# MAGIC Confirms:
# MAGIC - proposal belongs to one AnalysisGroup/ModelRun/KGNode;
# MAGIC - proposed code exists in the governed MAIRA EMCIP registry;
# MAGIC - proposed code was present in the deterministic shortlist;
# MAGIC - NO_MAPPING proposals do not carry a selected code;
# MAGIC - human reviews are append-only and linked to the proposal/node;
# MAGIC - AMENDED reviews choose a code from the same governed shortlist.

# COMMAND ----------

dbutils.widgets.text(
    "analysis_id",
    "",
    "Analysis ID",
)

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1

# COMMAND ----------

import json
import re

from neo4j import GraphDatabase
from pyspark.sql import functions as F

analysis_id = dbutils.widgets.get(
    "analysis_id"
).strip()

if not re.fullmatch(
    r"analysis_[0-9a-f]{32}",
    analysis_id,
):
    raise ValueError(
        "Enter analysis_<32 hex>."
    )

REGISTRY_TABLE = (
    "bdw_analysis_prod.maira.emcip_operational_registry"
)

if not spark.catalog.tableExists(
    REGISTRY_TABLE
):
    raise RuntimeError(
        "MAIRA EMCIP operational registry is unavailable."
    )

registry_codes = {
    row["code_idcode"]
    for row in (
        spark.table(REGISTRY_TABLE)
        .select("code_idcode")
        .filter(
            F.col("code_idcode").isNotNull()
        )
        .distinct()
        .collect()
    )
}

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

with driver.session() as session:
    proposals = [
        record.data()
        for record in session.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })-[:HAS_EMCIP_MAPPING_PROPOSAL]->(
                p:EMCIPMappingProposal
            )-[:MAPS_NODE]->(n:KGNode)
            RETURN
                p.proposal_id AS proposal_id,
                p.analysis_id AS analysis_id,
                p.model_run_id AS model_run_id,
                p.node_id AS node_id,
                p.assistant_mapping_status AS assistant_mapping_status,
                p.proposed_code_idcode AS proposed_code_idcode,
                p.candidate_options_json AS candidate_options_json,
                n.analysis_id AS node_analysis_id,
                n.model_run_id AS node_model_run_id,
                n.node_id AS linked_node_id
            ORDER BY p.proposal_id
            """,
            analysis_id=analysis_id,
        )
    ]

print("Proposals:", len(proposals))

if not proposals:
    driver.close()
    dbutils.notebook.exit(
        "NO_EMCIP_MAPPING_PROPOSALS"
    )

# COMMAND ----------

proposal_candidates = {}
validation_rows = []
errors = []

for proposal in proposals:
    proposal_errors = []

    if (
        proposal["analysis_id"]
        != proposal["node_analysis_id"]
    ):
        proposal_errors.append(
            "proposal/node analysis mismatch"
        )

    if (
        proposal["model_run_id"]
        != proposal["node_model_run_id"]
    ):
        proposal_errors.append(
            "proposal/node model-run mismatch"
        )

    if (
        proposal["node_id"]
        != proposal["linked_node_id"]
    ):
        proposal_errors.append(
            "proposal linked to unexpected KGNode"
        )

    try:
        candidates = json.loads(
            proposal.get(
                "candidate_options_json"
            )
            or "[]"
        )
    except Exception:
        candidates = []
        proposal_errors.append(
            "candidate_options_json is invalid"
        )

    candidate_codes = {
        item.get("code_idcode")
        for item in candidates
        if item.get("code_idcode")
    }

    proposal_candidates[
        proposal["proposal_id"]
    ] = candidate_codes

    selected_code = proposal.get(
        "proposed_code_idcode"
    )

    if (
        proposal.get(
            "assistant_mapping_status"
        )
        == "ASSISTANT_PROPOSED"
    ):
        if not selected_code:
            proposal_errors.append(
                "assistant proposal has no selected code"
            )
        else:
            if selected_code not in candidate_codes:
                proposal_errors.append(
                    "selected code was not in deterministic shortlist"
                )
            if selected_code not in registry_codes:
                proposal_errors.append(
                    "selected code does not exist in MAIRA registry"
                )
    else:
        if selected_code:
            proposal_errors.append(
                "NO_MAPPING proposal unexpectedly carries a code"
            )

    validation_rows.append(
        {
            "record_type": "PROPOSAL",
            "record_id": proposal[
                "proposal_id"
            ],
            "errors": len(
                proposal_errors
            ),
            "error_detail": " | ".join(
                proposal_errors
            ),
        }
    )

    errors.extend(
        f"{proposal['proposal_id']}: {value}"
        for value in proposal_errors
    )

# COMMAND ----------

with driver.session() as session:
    reviews = [
        record.data()
        for record in session.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })-[:HAS_EMCIP_MAPPING_REVIEW]->(
                r:EMCIPMappingReview
            )-[:REVIEWS_MAPPING_PROPOSAL]->(
                p:EMCIPMappingProposal
            )
            MATCH (r)-[:REVIEWS_MAPPING_OF]->(
                n:KGNode
            )
            RETURN
                r.review_id AS review_id,
                r.analysis_id AS analysis_id,
                r.model_run_id AS model_run_id,
                r.proposal_id AS proposal_id,
                r.node_id AS node_id,
                r.human_review_decision AS decision,
                r.human_review_status AS status,
                r.amended_code_idcode AS amended_code_idcode,
                p.analysis_id AS proposal_analysis_id,
                p.model_run_id AS proposal_model_run_id,
                p.node_id AS proposal_node_id,
                n.node_id AS linked_node_id
            ORDER BY r.reviewed_at, r.review_id
            """,
            analysis_id=analysis_id,
        )
    ]

print("Human mapping reviews:", len(reviews))

for review in reviews:
    review_errors = []

    if (
        review["analysis_id"]
        != review["proposal_analysis_id"]
    ):
        review_errors.append(
            "review/proposal analysis mismatch"
        )

    if (
        review["model_run_id"]
        != review["proposal_model_run_id"]
    ):
        review_errors.append(
            "review/proposal model-run mismatch"
        )

    if (
        review["node_id"]
        != review["proposal_node_id"]
        or review["node_id"]
        != review["linked_node_id"]
    ):
        review_errors.append(
            "review/proposal/node mismatch"
        )

    amended_code = review.get(
        "amended_code_idcode"
    )

    if review["decision"] == "AMENDED":
        if not amended_code:
            review_errors.append(
                "AMENDED review has no governed replacement code"
            )
        else:
            allowed = proposal_candidates.get(
                review["proposal_id"],
                set(),
            )
            if amended_code not in allowed:
                review_errors.append(
                    "amended code was not in proposal shortlist"
                )
            if amended_code not in registry_codes:
                review_errors.append(
                    "amended code does not exist in MAIRA registry"
                )
    elif amended_code:
        review_errors.append(
            "non-AMENDED review unexpectedly carries amended code"
        )

    validation_rows.append(
        {
            "record_type": "REVIEW",
            "record_id": review[
                "review_id"
            ],
            "errors": len(
                review_errors
            ),
            "error_detail": " | ".join(
                review_errors
            ),
        }
    )

    errors.extend(
        f"{review['review_id']}: {value}"
        for value in review_errors
    )

# COMMAND ----------

display(
    spark.createDataFrame(
        validation_rows
    )
)

if errors:
    print("")
    print("VALIDATION ERRORS")
    for error in errors:
        print(" -", error)

    driver.close()
    raise RuntimeError(
        "Generic EMCIP proposal/review validation failed."
    )

print("")
print("PASS — GENERIC EMCIP PROPOSALS AND REVIEWS REMAIN GOVERNED")
print("proposals:", len(proposals))
print("reviews:", len(reviews))

driver.close()
