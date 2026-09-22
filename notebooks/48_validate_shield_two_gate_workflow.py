# Databricks notebook source
# MAGIC %md
# MAGIC # 48 — Validate two-gate SHIELD workflow
# MAGIC
# MAGIC Read-only validation.
# MAGIC
# MAGIC Gate 1:
# MAGIC latest human relationship review confirms
# MAGIC ContributingFactor — CONTRIBUTED_TO → target.
# MAGIC
# MAGIC Gate 2:
# MAGIC a separate append-only ShieldReview validates/rejects/amends the
# MAGIC assistant proposal.
# MAGIC
# MAGIC The SHIELD proposal itself is never authoritative.

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
from pyspark.sql import functions as F

SHIELD_PASSAGE_TABLE = (
    "bdw_analysis_prod.kg_poc.shield_passage"
)

analysis_id = dbutils.widgets.get(
    "analysis_id"
).strip()

if (
    analysis_id
    and not re.fullmatch(
        r"analysis_[0-9a-f]{32}",
        analysis_id,
    )
):
    raise ValueError(
        "analysis_id must be blank or analysis_<32 hex>."
    )

if not spark.catalog.tableExists(
    SHIELD_PASSAGE_TABLE
):
    raise RuntimeError(
        "SHIELD passage corpus is unavailable. Run notebook 45 first."
    )

shield_passage_rows = {
    row["shield_passage_id"]:
        row.asDict(recursive=True)
    for row in (
        spark.table(
            SHIELD_PASSAGE_TABLE
        )
        .select(
            "shield_passage_id",
            "shield_document_id",
            "page_start",
            "page_end",
            "passage_text",
            "corpus_snapshot_id",
        )
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
    auth=(
        NEO4J_USERNAME,
        NEO4J_PASSWORD,
    ),
)
driver.verify_connectivity()

where_clause = (
    "WHERE p.analysis_id = $analysis_id"
    if analysis_id
    else ""
)

with driver.session() as session:
    proposals = [
        record.data()
        for record in session.run(
            f"""
            MATCH (p:ShieldProposal)
            {where_clause}
            OPTIONAL MATCH (
                a:AnalysisGroup {{
                    analysis_id:
                        p.analysis_id
                }}
            )-[:HAS_SHIELD_PROPOSAL]->(p)
            OPTIONAL MATCH (
                p
            )-[:CLASSIFIES_FACTOR]->(
                factor:KGNode
            )
            OPTIONAL MATCH (
                p
            )-[:GATED_BY_REVIEW]->(
                gate:RelationshipReview
            )
            OPTIONAL MATCH (
                newest:RelationshipReview {{
                    analysis_id:
                        p.analysis_id,
                    model_run_id:
                        p.model_run_id,
                    edge_id:
                        p.edge_id
                }}
            )
            WITH
                p,
                a,
                factor,
                gate,
                newest
            ORDER BY newest.reviewed_at DESC
            WITH
                p,
                a,
                factor,
                gate,
                head(
                    collect(newest)
                ) AS latest_gate
            RETURN
                p.proposal_id AS proposal_id,
                p.analysis_id AS analysis_id,
                p.model_run_id AS model_run_id,
                p.edge_id AS edge_id,
                p.factor_node_id AS factor_node_id,
                p.factor_label AS factor_label,
                p.target_node_id AS target_node_id,
                p.target_label AS target_label,
                p.gate_relationship_review_id AS gate_review_id,
                p.assistant_status AS assistant_status,
                p.proposed_shield_label AS proposed_shield_label,
                p.proposed_shield_code AS proposed_shield_code,
                p.proposed_shield_path AS proposed_shield_path,
                coalesce(
                    p.shield_passage_ids,
                    []
                ) AS shield_passage_ids,
                p.shield_corpus_snapshot_id AS shield_corpus_snapshot_id,
                p.proposal_version AS proposal_version,
                a.analysis_id AS linked_analysis_id,
                factor.node_id AS linked_factor_node_id,
                factor.node_kind AS factor_node_kind,
                factor.analysis_id AS factor_analysis_id,
                factor.model_run_id AS factor_model_run_id,
                gate.review_id AS linked_gate_review_id,
                gate.human_review_decision AS gate_decision,
                gate.original_relationship AS gate_original_relationship,
                gate.amended_relationship AS gate_amended_relationship,
                latest_gate.review_id AS latest_gate_review_id
            ORDER BY
                p.analysis_id,
                p.proposal_id
            """,
            analysis_id=(
                analysis_id
                or None
            ),
        )
    ]

print(
    "SHIELD proposals:",
    len(proposals),
)

if not proposals:
    driver.close()
    dbutils.notebook.exit(
        "NO_SHIELD_PROPOSALS"
    )

# COMMAND ----------

errors = []
proposal_validation = []

for proposal in proposals:
    item_errors = []

    if (
        proposal.get(
            "linked_analysis_id"
        )
        != proposal.get(
            "analysis_id"
        )
    ):
        item_errors.append(
            "proposal is not linked from its AnalysisGroup"
        )

    if (
        proposal.get(
            "linked_factor_node_id"
        )
        != proposal.get(
            "factor_node_id"
        )
    ):
        item_errors.append(
            "proposal does not link to its contributing-factor node"
        )

    if (
        proposal.get(
            "factor_node_kind"
        )
        != "ContributingFactor"
    ):
        item_errors.append(
            "SHIELD proposal factor is not a ContributingFactor node"
        )

    if (
        proposal.get(
            "factor_analysis_id"
        )
        != proposal.get(
            "analysis_id"
        )
        or proposal.get(
            "factor_model_run_id"
        )
        != proposal.get(
            "model_run_id"
        )
    ):
        item_errors.append(
            "factor analysis/model provenance mismatch"
        )

    if (
        proposal.get(
            "linked_gate_review_id"
        )
        != proposal.get(
            "gate_review_id"
        )
    ):
        item_errors.append(
            "proposal is not linked to its Gate-1 RelationshipReview"
        )

    gate_confirms_contribution = (
        (
            proposal.get(
                "gate_decision"
            )
            == "VALIDATED"
            and proposal.get(
                "gate_original_relationship"
            )
            == "CONTRIBUTED_TO"
        )
        or
        (
            proposal.get(
                "gate_decision"
            )
            == "AMENDED"
            and proposal.get(
                "gate_amended_relationship"
            )
            == "CONTRIBUTED_TO"
        )
    )

    if not gate_confirms_contribution:
        item_errors.append(
            "Gate-1 review does not confirm CONTRIBUTED_TO"
        )

    if (
        proposal.get(
            "latest_gate_review_id"
        )
        != proposal.get(
            "gate_review_id"
        )
    ):
        item_errors.append(
            "proposal is stale because Gate 1 has a newer human review"
        )

    passage_ids = (
        proposal.get(
            "shield_passage_ids"
        )
        or []
    )

    unknown_passages = sorted(
        {
            passage_id
            for passage_id in passage_ids
            if passage_id
            not in shield_passage_rows
        }
    )

    if unknown_passages:
        item_errors.append(
            "proposal cites unknown SHIELD passage IDs"
        )

    if (
        proposal.get(
            "assistant_status"
        )
        == "ASSISTANT_PROPOSED"
    ):
        if not proposal.get(
            "proposed_shield_label"
        ):
            item_errors.append(
                "assistant proposal has no SHIELD label"
            )

        if not passage_ids:
            item_errors.append(
                "assistant proposal has no SHIELD source passages"
            )

        cited_text = "\n".join(
            shield_passage_rows[
                passage_id
            ][
                "passage_text"
            ]
            for passage_id
            in passage_ids
            if passage_id
            in shield_passage_rows
        ).casefold()

        label = str(
            proposal.get(
                "proposed_shield_label"
            )
            or ""
        ).casefold()

        code = str(
            proposal.get(
                "proposed_shield_code"
            )
            or ""
        ).casefold()

        if (
            label
            and label
            not in cited_text
        ):
            item_errors.append(
                "assistant SHIELD label is not present in cited SHIELD text"
            )

        if (
            code
            and code
            not in cited_text
        ):
            item_errors.append(
                "assistant SHIELD code is not present in cited SHIELD text"
            )

        cited_snapshots = {
            shield_passage_rows[
                passage_id
            ][
                "corpus_snapshot_id"
            ]
            for passage_id
            in passage_ids
            if passage_id
            in shield_passage_rows
        }

        if cited_snapshots != {
            proposal.get(
                "shield_corpus_snapshot_id"
            )
        }:
            item_errors.append(
                "proposal SHIELD snapshot does not match cited passages"
            )

    elif (
        proposal.get(
            "assistant_status"
        )
        == "NO_GROUNDED_PROPOSAL"
    ):
        if any(
            [
                proposal.get(
                    "proposed_shield_label"
                ),
                proposal.get(
                    "proposed_shield_code"
                ),
                proposal.get(
                    "proposed_shield_path"
                ),
            ]
        ):
            item_errors.append(
                "NO_GROUNDED_PROPOSAL contains classification values"
            )
    else:
        item_errors.append(
            "unexpected assistant SHIELD proposal status"
        )

    proposal_validation.append(
        {
            "proposal_id":
                proposal[
                    "proposal_id"
                ],
            "analysis_id":
                proposal[
                    "analysis_id"
                ],
            "factor":
                proposal.get(
                    "factor_label"
                ),
            "assistant_status":
                proposal.get(
                    "assistant_status"
                ),
            "gate_current":
                (
                    proposal.get(
                        "latest_gate_review_id"
                    )
                    == proposal.get(
                        "gate_review_id"
                    )
                ),
            "shield_passages":
                len(
                    passage_ids
                ),
            "errors":
                len(
                    item_errors
                ),
            "error_detail":
                " | ".join(
                    item_errors
                ),
        }
    )

    errors.extend(
        f"{proposal['proposal_id']}: {value}"
        for value in item_errors
    )

display(
    spark.createDataFrame(
        proposal_validation
    )
)

# COMMAND ----------

review_where = (
    "WHERE review.analysis_id = $analysis_id"
    if analysis_id
    else ""
)

with driver.session() as session:
    reviews = [
        record.data()
        for record in session.run(
            f"""
            MATCH (review:ShieldReview)
            {review_where}
            OPTIONAL MATCH (
                a:AnalysisGroup {{
                    analysis_id:
                        review.analysis_id
                }}
            )-[:HAS_SHIELD_REVIEW]->(
                review
            )
            OPTIONAL MATCH (
                review
            )-[:REVIEWS_SHIELD_PROPOSAL]->(
                p:ShieldProposal
            )
            OPTIONAL MATCH (
                review
            )-[:REVIEWS_SHIELD_OF]->(
                n:KGNode
            )
            OPTIONAL MATCH (
                review
            )-[:REVIEW_GATE]->(
                gate:RelationshipReview
            )
            RETURN
                review.review_id AS review_id,
                review.analysis_id AS analysis_id,
                review.model_run_id AS model_run_id,
                review.proposal_id AS proposal_id,
                review.factor_node_id AS factor_node_id,
                review.gate_relationship_review_id AS gate_review_id,
                review.assistant_status AS assistant_status,
                review.original_shield_label AS original_shield_label,
                review.original_shield_code AS original_shield_code,
                review.original_shield_path AS original_shield_path,
                review.human_review_decision AS decision,
                review.human_review_status AS status,
                review.amended_shield_label AS amended_shield_label,
                review.amended_shield_code AS amended_shield_code,
                review.amended_shield_path AS amended_shield_path,
                a.analysis_id AS linked_analysis_id,
                p.proposal_id AS linked_proposal_id,
                p.gate_relationship_review_id AS proposal_gate_review_id,
                p.assistant_status AS proposal_assistant_status,
                n.node_id AS linked_factor_node_id,
                gate.review_id AS linked_gate_review_id
            ORDER BY
                review.reviewed_at,
                review.review_id
            """,
            analysis_id=(
                analysis_id
                or None
            ),
        )
    ]

print(
    "Gate-2 SHIELD reviews:",
    len(reviews),
)

review_validation = []

for review in reviews:
    item_errors = []

    if (
        review.get(
            "linked_analysis_id"
        )
        != review.get(
            "analysis_id"
        )
    ):
        item_errors.append(
            "SHIELD review is not linked from its AnalysisGroup"
        )

    if (
        review.get(
            "linked_proposal_id"
        )
        != review.get(
            "proposal_id"
        )
    ):
        item_errors.append(
            "SHIELD review is not linked to its proposal"
        )

    if (
        review.get(
            "linked_factor_node_id"
        )
        != review.get(
            "factor_node_id"
        )
    ):
        item_errors.append(
            "SHIELD review is not linked to its contributing factor"
        )

    if (
        review.get(
            "linked_gate_review_id"
        )
        != review.get(
            "gate_review_id"
        )
        or review.get(
            "proposal_gate_review_id"
        )
        != review.get(
            "gate_review_id"
        )
    ):
        item_errors.append(
            "Gate-1 review provenance mismatch"
        )

    if (
        review.get(
            "proposal_assistant_status"
        )
        != "ASSISTANT_PROPOSED"
        or review.get(
            "assistant_status"
        )
        != "ASSISTANT_PROPOSED"
    ):
        item_errors.append(
            "Gate-2 review exists for a non-grounded assistant proposal"
        )

    decision = review.get(
        "decision"
    )

    expected_status = {
        "VALIDATED":
            "HUMAN_VALIDATED",
        "REJECTED":
            "HUMAN_REJECTED",
        "AMENDED":
            "HUMAN_AMENDED",
    }.get(
        decision
    )

    if (
        expected_status is None
        or review.get(
            "status"
        )
        != expected_status
    ):
        item_errors.append(
            "invalid Gate-2 decision/status pair"
        )

    if (
        decision == "AMENDED"
        and not review.get(
            "amended_shield_label"
        )
    ):
        item_errors.append(
            "amended SHIELD review has no amended label"
        )

    if (
        decision != "AMENDED"
        and any(
            [
                review.get(
                    "amended_shield_label"
                ),
                review.get(
                    "amended_shield_code"
                ),
                review.get(
                    "amended_shield_path"
                ),
            ]
        )
    ):
        item_errors.append(
            "non-amended SHIELD review contains amended values"
        )

    review_validation.append(
        {
            "review_id":
                review[
                    "review_id"
                ],
            "proposal_id":
                review[
                    "proposal_id"
                ],
            "decision":
                decision,
            "status":
                review.get(
                    "status"
                ),
            "errors":
                len(
                    item_errors
                ),
            "error_detail":
                " | ".join(
                    item_errors
                ),
        }
    )

    errors.extend(
        f"{review['review_id']}: {value}"
        for value in item_errors
    )

if review_validation:
    display(
        spark.createDataFrame(
            review_validation
        )
    )

# COMMAND ----------

if errors:
    print("")
    print(
        "VALIDATION ERRORS"
    )
    for error in errors:
        print(
            " -",
            error,
        )

    driver.close()
    raise RuntimeError(
        "Two-gate SHIELD workflow validation failed."
    )

print("")
print(
    "PASS — SHIELD PROPOSALS REQUIRE GATE 1 AND AUTHORITATIVE CLASSIFICATION REQUIRES GATE 2"
)
print(
    "proposals:",
    len(proposals),
)
print(
    "human SHIELD reviews:",
    len(reviews),
)

driver.close()
