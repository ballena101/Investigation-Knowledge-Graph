# Databricks notebook source
# MAGIC %md
# MAGIC # 51 — Validate relationship-correction governance
# MAGIC
# MAGIC Read-only validation for one relationship-correction proposal.
# MAGIC
# MAGIC Confirms:
# MAGIC - the proposal is tied to one real graph edge;
# MAGIC - proposal evidence is a subset of the edge's persisted evidence;
# MAGIC - the LLM did not alter the graph relationship;
# MAGIC - proposal staleness follows the latest RelationshipReview;
# MAGIC - any human-approved correction creates a separate append-only
# MAGIC   RelationshipReview;
# MAGIC - the authoritative semantic decision comes from that human review,
# MAGIC   not from the proposal node.

# COMMAND ----------

dbutils.widgets.text(
    "proposal_id",
    "",
    "Relationship correction proposal ID",
)

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1

# COMMAND ----------

from neo4j import GraphDatabase

proposal_id = dbutils.widgets.get(
    "proposal_id"
).strip()

if not proposal_id.startswith(
    "relationship_correction_"
):
    raise ValueError(
        "Enter a relationship_correction_<...> proposal ID."
    )

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

# COMMAND ----------

with driver.session() as session:
    record = session.run(
        """
        MATCH (a:AnalysisGroup)
              -[:HAS_RELATIONSHIP_CORRECTION_PROPOSAL]->
              (p:RelationshipCorrectionProposal {
                  proposal_id: $proposal_id
              })
        MATCH (source:KGNode {
            analysis_id: p.analysis_id,
            model_run_id: p.model_run_id,
            node_id: p.source_node_id
        })-[r]->(target:KGNode {
            analysis_id: p.analysis_id,
            model_run_id: p.model_run_id,
            node_id: p.target_node_id
        })
        WHERE r.edge_id = p.edge_id
        OPTIONAL MATCH (
            latest:RelationshipReview {
                analysis_id: p.analysis_id,
                model_run_id: p.model_run_id,
                edge_id: p.edge_id
            }
        )
        WITH
            a,
            p,
            source,
            r,
            target,
            latest
        ORDER BY latest.reviewed_at DESC
        WITH
            a,
            p,
            source,
            r,
            target,
            head(collect(latest)) AS latest_review
        OPTIONAL MATCH (
            correction_review:RelationshipCorrectionReview {
                proposal_id: p.proposal_id
            }
        )
        WITH
            a,
            p,
            source,
            r,
            target,
            latest_review,
            correction_review
        ORDER BY correction_review.reviewed_at DESC
        WITH
            a,
            p,
            source,
            r,
            target,
            latest_review,
            head(collect(correction_review)) AS correction_review
        RETURN
            p.analysis_id AS analysis_id,
            p.model_run_id AS model_run_id,
            p.edge_id AS edge_id,
            source.node_id AS source_node_id,
            source.label AS source_label,
            type(r) AS graph_relationship,
            target.node_id AS target_node_id,
            target.label AS target_label,
            p.original_relationship AS original_relationship,
            p.base_relationship_review_id AS base_review_id,
            p.assistant_status AS assistant_status,
            p.action AS action,
            p.proposed_relationship AS proposed_relationship,
            coalesce(
                p.evidence_passage_ids,
                []
            ) AS proposal_passage_ids,
            coalesce(
                properties(r)["evidence_passage_ids"],
                []
            ) AS edge_passage_ids,
            latest_review.review_id AS latest_relationship_review_id,
            latest_review.human_review_decision AS latest_relationship_decision,
            latest_review.amended_relationship AS latest_amended_relationship,
            correction_review.review_id AS correction_review_id,
            correction_review.human_decision AS correction_human_decision,
            correction_review.applied_relationship_decision AS applied_relationship_decision,
            correction_review.applied_relationship AS applied_relationship,
            correction_review.authoritative_relationship_review_id AS authoritative_relationship_review_id
        """,
        proposal_id=proposal_id,
    ).single()

if record is None:
    driver.close()
    raise ValueError(
        f"Proposal or graph edge not found: {proposal_id}"
    )

row = record.data()

print("Proposal:", proposal_id)
print("Analysis:", row["analysis_id"])
print(
    "Relationship:",
    row["source_label"],
    "—",
    row["graph_relationship"],
    "→",
    row["target_label"],
)
print("Assistant action:", row["action"])
print(
    "Latest human relationship review:",
    row.get("latest_relationship_review_id"),
)
print(
    "Latest correction review:",
    row.get("correction_review_id"),
)

# COMMAND ----------

errors = []

allowed_actions = {
    "KEEP",
    "CHANGE_RELATIONSHIP",
    "REJECT_RELATIONSHIP",
    "INSUFFICIENT_EVIDENCE",
}

allowed_relationships = {
    "FOLLOWED_BY",
    "CONTRIBUTED_TO",
    "RESULTED_IN",
    "AFFECTED",
    "SUPPORTS",
}

if row["action"] not in allowed_actions:
    errors.append(
        "Proposal contains an unsupported assistant action."
    )

# Critical invariant: proposals/reviews never overwrite the graph edge.
if row["graph_relationship"] != row["original_relationship"]:
    errors.append(
        "The graph relationship no longer matches the proposal's original "
        "relationship. Correction workflow must not overwrite the graph edge."
    )

proposal_passages = set(
    row.get("proposal_passage_ids")
    or []
)
edge_passages = set(
    row.get("edge_passage_ids")
    or []
)

if not proposal_passages.issubset(
    edge_passages
):
    errors.append(
        "Proposal cites evidence passages that were not part of the original "
        "relationship evidence."
    )

if (
    row["assistant_status"]
    == "ASSISTANT_PROPOSED"
    and row["action"]
    in {
        "KEEP",
        "CHANGE_RELATIONSHIP",
        "REJECT_RELATIONSHIP",
    }
    and not proposal_passages
):
    errors.append(
        "A grounded actionable proposal has no supporting passage IDs."
    )

if row["action"] == "CHANGE_RELATIONSHIP":
    if (
        row.get("proposed_relationship")
        not in allowed_relationships
    ):
        errors.append(
            "CHANGE_RELATIONSHIP does not contain an allowed replacement."
        )
    elif (
        row.get("proposed_relationship")
        == row["original_relationship"]
    ):
        errors.append(
            "CHANGE_RELATIONSHIP proposes the unchanged relationship."
        )
elif row.get("proposed_relationship"):
    errors.append(
        "Only CHANGE_RELATIONSHIP may contain proposed_relationship."
    )

# COMMAND ----------

base_review_id = row.get(
    "base_review_id"
)
latest_review_id = row.get(
    "latest_relationship_review_id"
)

proposal_is_current = (
    (
        base_review_id is None
        and latest_review_id is None
    )
    or (
        base_review_id is not None
        and base_review_id == latest_review_id
    )
)

print(
    "Proposal base review is current:",
    proposal_is_current,
)

# A correction review can legitimately make the proposal stale, because an
# approved correction creates a newer RelationshipReview. That is expected.
correction_review_id = row.get(
    "correction_review_id"
)

if (
    correction_review_id is None
    and not proposal_is_current
):
    errors.append(
        "Unreviewed proposal is stale because a newer RelationshipReview exists."
    )

# COMMAND ----------

if correction_review_id is not None:
    decision = row.get(
        "correction_human_decision"
    )
    authoritative_review_id = row.get(
        "authoritative_relationship_review_id"
    )

    if decision == "DISMISSED":
        if authoritative_review_id is not None:
            errors.append(
                "Dismissed proposal unexpectedly created an authoritative "
                "RelationshipReview."
            )
    elif decision in {
        "APPROVED",
        "APPLIED_WITH_AMENDMENT",
    }:
        if not authoritative_review_id:
            errors.append(
                "Applied correction decision has no authoritative "
                "RelationshipReview ID."
            )
        else:
            with driver.session() as session:
                authoritative = session.run(
                    """
                    MATCH (r:RelationshipReview {
                        review_id: $review_id
                    })
                    RETURN
                        r.analysis_id AS analysis_id,
                        r.model_run_id AS model_run_id,
                        r.edge_id AS edge_id,
                        r.human_review_decision AS decision,
                        r.human_review_status AS status,
                        r.amended_relationship AS amended_relationship,
                        r.correction_proposal_id AS correction_proposal_id,
                        r.correction_review_id AS correction_review_id
                    """,
                    review_id=authoritative_review_id,
                ).single()

            if authoritative is None:
                errors.append(
                    "Authoritative RelationshipReview ID does not resolve."
                )
            else:
                authoritative = authoritative.data()

                for field in (
                    "analysis_id",
                    "model_run_id",
                    "edge_id",
                ):
                    if (
                        authoritative[field]
                        != row[field]
                    ):
                        errors.append(
                            "Authoritative RelationshipReview provenance "
                            f"mismatch for {field}."
                        )

                if (
                    authoritative.get(
                        "correction_proposal_id"
                    )
                    != proposal_id
                ):
                    errors.append(
                        "Authoritative RelationshipReview is not linked to "
                        "this correction proposal."
                    )

                if (
                    authoritative.get(
                        "correction_review_id"
                    )
                    != correction_review_id
                ):
                    errors.append(
                        "Authoritative RelationshipReview is not linked to "
                        "the latest correction review."
                    )

                if (
                    authoritative.get(
                        "decision"
                    )
                    != row.get(
                        "applied_relationship_decision"
                    )
                ):
                    errors.append(
                        "Applied human relationship decision differs from the "
                        "authoritative RelationshipReview."
                    )

                if (
                    authoritative.get(
                        "amended_relationship"
                    )
                    != row.get(
                        "applied_relationship"
                    )
                ):
                    errors.append(
                        "Applied amended relationship differs from the "
                        "authoritative RelationshipReview."
                    )
    else:
        errors.append(
            "RelationshipCorrectionReview contains an unsupported human decision."
        )

# COMMAND ----------

if errors:
    print("")
    print("VALIDATION ERRORS")
    for error in errors:
        print(" -", error)

    driver.close()
    raise RuntimeError(
        "Relationship-correction governance validation failed."
    )

print("")
print(
    "PASS — RELATIONSHIP CORRECTION REMAINS HUMAN-GOVERNED"
)
print(
    "Graph relationship remains:",
    row["graph_relationship"],
)
print(
    "Correction review:",
    correction_review_id or "not yet reviewed",
)
print(
    "Authoritative relationship review:",
    row.get("authoritative_relationship_review_id")
    or "none",
)

driver.close()
