# Databricks notebook source
# MAGIC %md
# MAGIC # 49 — Propose a correction for one graph relationship
# MAGIC
# MAGIC Evidence-bounded LLM review of one existing graph relationship.
# MAGIC
# MAGIC Governance:
# MAGIC - the graph relationship is never modified;
# MAGIC - only the relationship's already-cited analysis passages are supplied;
# MAGIC - chronology alone never establishes causality;
# MAGIC - proposal actions are KEEP, CHANGE_RELATIONSHIP,
# MAGIC   REJECT_RELATIONSHIP or INSUFFICIENT_EVIDENCE;
# MAGIC - human approval remains authoritative through append-only review;
# MAGIC - a newer RelationshipReview makes the proposal stale.

# COMMAND ----------

dbutils.widgets.text(
    "analysis_id",
    "",
    "Analysis ID",
)
dbutils.widgets.text(
    "model_run_id",
    "",
    "Model run ID",
)
dbutils.widgets.text(
    "edge_id",
    "",
    "Relationship edge ID",
)

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1 databricks-sdk==0.139.0

# COMMAND ----------

import hashlib
import json
import re
import urllib.error
import urllib.request

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    ChatMessage,
    ChatMessageRole,
)
from neo4j import GraphDatabase
from pyspark.sql import functions as F

analysis_id = dbutils.widgets.get(
    "analysis_id"
).strip()
model_run_id = dbutils.widgets.get(
    "model_run_id"
).strip()
edge_id = dbutils.widgets.get(
    "edge_id"
).strip()

if not re.fullmatch(
    r"analysis_[0-9a-f]{32}",
    analysis_id,
):
    raise ValueError(
        "Enter a valid analysis_id."
    )

if not model_run_id.startswith(
    analysis_id + "__"
):
    raise ValueError(
        "model_run_id must belong to the selected analysis."
    )

if not edge_id:
    raise ValueError(
        "edge_id is required."
    )

ANALYSIS_PASSAGE_TABLE = (
    "bdw_analysis_prod.kg_poc.analysis_passage"
)

PROPOSAL_VERSION = (
    "IKF_RELATIONSHIP_CORRECTION_V0.1"
)

ALLOWED_RELATIONSHIPS = {
    "FOLLOWED_BY",
    "CONTRIBUTED_TO",
    "RESULTED_IN",
    "AFFECTED",
    "SUPPORTS",
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

w = WorkspaceClient()

# COMMAND ----------

with driver.session() as session:
    record = session.run(
        """
        MATCH (a:AnalysisGroup {
            analysis_id: $analysis_id
        })-[:HAS_MODEL_RUN]->(
            m:ModelRun {
                model_run_id: $model_run_id
            }
        )
        MATCH (source:KGNode {
            analysis_id: $analysis_id,
            model_run_id: $model_run_id
        })-[r]->(target:KGNode {
            analysis_id: $analysis_id,
            model_run_id: $model_run_id
        })
        WHERE r.edge_id = $edge_id
        OPTIONAL MATCH (
            latest:RelationshipReview {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                edge_id: $edge_id
            }
        )
        WITH
            a,
            m,
            source,
            r,
            target,
            latest
        ORDER BY latest.reviewed_at DESC
        WITH
            a,
            m,
            source,
            r,
            target,
            head(
                collect(latest)
            ) AS base_review
        RETURN
            a.analysis_title AS analysis_title,
            properties(a)["information_class"] AS information_class,
            m.model_service AS model_service,
            m.status AS model_status,
            source.node_id AS source_node_id,
            source.label AS source_label,
            source.node_kind AS source_kind,
            target.node_id AS target_node_id,
            target.label AS target_label,
            target.node_kind AS target_kind,
            type(r) AS relationship,
            coalesce(
                properties(r)["edge_class"],
                "REPORT_DERIVED"
            ) AS edge_class,
            coalesce(
                properties(r)["evidence_passage_ids"],
                []
            ) AS passage_ids,
            coalesce(
                properties(r)["evidence_references"],
                []
            ) AS evidence_references,
            coalesce(
                properties(r)["evidence_locations"],
                []
            ) AS evidence_locations,
            base_review.review_id AS base_review_id,
            base_review.human_review_decision AS base_review_decision,
            base_review.amended_relationship AS base_amended_relationship
        """,
        analysis_id=analysis_id,
        model_run_id=model_run_id,
        edge_id=edge_id,
    ).single()

if record is None:
    driver.close()
    raise ValueError(
        "Selected relationship was not found."
    )

edge = record.data()

if edge.get("model_status") != "COMPLETED":
    driver.close()
    raise ValueError(
        "Relationship correction requires a completed model run."
    )

if edge.get("edge_class") == "STRUCTURAL":
    driver.close()
    raise ValueError(
        "Structural relationships are not eligible for semantic correction."
    )

model_service = edge.get(
    "model_service"
)

if not model_service:
    driver.close()
    raise ValueError(
        "The selected model run has no model service."
    )

passage_ids = list(
    edge.get(
        "passage_ids"
    )
    or []
)

if not passage_ids:
    driver.close()
    raise ValueError(
        "The selected relationship has no supporting passage IDs. "
        "A correction proposal cannot be grounded."
    )

print(
    "Relationship:",
    edge["source_label"],
    "—",
    edge["relationship"],
    "→",
    edge["target_label"],
)
print(
    "Evidence passages:",
    len(passage_ids),
)
print(
    "Base human review:",
    edge.get("base_review_id"),
)

# COMMAND ----------

rows = (
    spark.table(
        ANALYSIS_PASSAGE_TABLE
    )
    .filter(
        F.col("analysis_id")
        == analysis_id
    )
    .filter(
        F.col("passage_id").isin(
            passage_ids
        )
    )
    .select(
        "document_id",
        "passage_id",
        "page_start",
        "page_end",
        "passage_order",
        "passage_text",
        "detected_language",
    )
    .orderBy(
        "document_id",
        "passage_order",
    )
    .collect()
)

passage_by_id = {
    row["passage_id"]:
        row
    for row in rows
}

missing_passages = sorted(
    set(passage_ids)
    - set(passage_by_id)
)

if missing_passages:
    driver.close()
    raise RuntimeError(
        "The relationship cites passage IDs that are not present in the "
        "analysis evidence table: "
        + ", ".join(
            missing_passages
        )
    )

# COMMAND ----------

def passage_block(row):
    return (
        f"[PASSAGE_ID: {row['passage_id']}]\n"
        f"[DOCUMENT_ID: {row['document_id']}]\n"
        f"[PAGE_START: {row['page_start']}]\n"
        f"[PAGE_END: {row['page_end']}]\n"
        f"[LANGUAGE: {row['detected_language']}]\n"
        f"{row['passage_text']}"
    )


evidence_text = (
    "\n\n---\n\n".join(
        passage_block(row)
        for row in rows
    )
)

# COMMAND ----------

def extract_chat_final_text(content):
    if content is None:
        return ""

    if isinstance(
        content,
        str,
    ):
        return content

    if isinstance(
        content,
        list,
    ):
        parts = []
        for item in content:
            if (
                isinstance(
                    item,
                    dict,
                )
                and str(
                    item.get(
                        "type"
                    )
                    or ""
                ).lower()
                in {
                    "text",
                    "output_text",
                }
                and item.get(
                    "text"
                )
                is not None
            ):
                parts.append(
                    str(
                        item[
                            "text"
                        ]
                    )
                )

        return "\n".join(
            parts
        )

    return str(content)


def strip_code_fences(value):
    text = str(
        value or ""
    ).strip()
    fence = chr(96) * 3

    if text.startswith(
        fence
    ):
        text = re.sub(
            r"^.{3}(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\s*.{3}$",
            "",
            text,
        )

    return text.strip()


def query_model_json(
    system_prompt,
    user_prompt,
):
    last_error = None

    for attempt in range(2):
        active_prompt = (
            user_prompt
        )

        if attempt:
            active_prompt += (
                "\n\nReturn one valid JSON object only. "
                "Do not include Markdown fences."
            )

        if model_service.startswith(
            "system.ai."
        ):
            request = urllib.request.Request(
                (
                    w.config.host.rstrip("/")
                    + "/ai-gateway/mlflow/v1/chat/completions"
                ),
                data=json.dumps(
                    {
                        "model":
                            model_service,
                        "messages": [
                            {
                                "role":
                                    "system",
                                "content":
                                    system_prompt,
                            },
                            {
                                "role":
                                    "user",
                                "content":
                                    active_prompt,
                            },
                        ],
                        "max_tokens":
                            1000,
                        "temperature":
                            0.0,
                    }
                ).encode(
                    "utf-8"
                ),
                headers={
                    **w.config.authenticate(),
                    "Content-Type":
                        "application/json",
                },
                method="POST",
            )

            try:
                with urllib.request.urlopen(
                    request,
                    timeout=600,
                ) as response:
                    payload = json.loads(
                        response.read()
                        .decode(
                            "utf-8"
                        )
                    )
            except urllib.error.HTTPError as exc:
                body = (
                    exc.read()
                    .decode(
                        "utf-8",
                        errors="replace",
                    )
                )
                raise RuntimeError(
                    "Relationship correction model request failed "
                    f"with HTTP {exc.code}: "
                    f"{body[:1000]}"
                ) from exc

            choices = (
                payload.get(
                    "choices"
                )
                or []
            )
            if not choices:
                raise ValueError(
                    "Model returned no answer choice."
                )

            text = (
                extract_chat_final_text(
                    choices[0]
                    .get(
                        "message",
                        {},
                    )
                    .get(
                        "content"
                    )
                )
            )
        else:
            response = (
                w.serving_endpoints
                .query(
                    name=model_service,
                    messages=[
                        ChatMessage(
                            role=ChatMessageRole.SYSTEM,
                            content=system_prompt,
                        ),
                        ChatMessage(
                            role=ChatMessageRole.USER,
                            content=active_prompt,
                        ),
                    ],
                    temperature=0.0,
                    max_tokens=1000,
                )
            )

            text = (
                extract_chat_final_text(
                    response
                    .choices[0]
                    .message
                    .content
                )
            )

        try:
            return json.loads(
                strip_code_fences(
                    text
                )
            )
        except Exception as exc:
            last_error = exc

    raise ValueError(
        "Relationship correction response was not valid JSON: "
        + str(last_error)
    )

# COMMAND ----------

SYSTEM_PROMPT = """
You review ONE existing relationship in a maritime investigation knowledge
graph using ONLY the supplied source-evidence passages.

Rules:
1. Do not use general maritime knowledge.
2. Chronology, proximity or plausibility alone do not establish causality.
3. You may propose only these semantic relationships:
   FOLLOWED_BY, CONTRIBUTED_TO, RESULTED_IN, AFFECTED, SUPPORTS.
4. Do not change the source or target concept.
5. KEEP means the current relationship is supported by the supplied evidence.
6. CHANGE_RELATIONSHIP requires explicit support for the proposed relationship.
7. REJECT_RELATIONSHIP means the supplied evidence does not support asserting
   the current relationship between these concepts.
8. INSUFFICIENT_EVIDENCE means the supplied evidence is not sufficient to
   decide among KEEP / CHANGE / REJECT.
9. Return only passage_ids supplied by the user.
10. This is an assistant proposal only. A human decision remains authoritative.
11. Return JSON only.

Required JSON:
{
  "action": "KEEP or CHANGE_RELATIONSHIP or REJECT_RELATIONSHIP or INSUFFICIENT_EVIDENCE",
  "proposed_relationship": "allowed relationship or empty",
  "passage_ids": ["passage_..."],
  "rationale": "brief evidence-grounded reason"
}
"""

response = query_model_json(
    SYSTEM_PROMPT,
    json.dumps(
        {
            "relationship": {
                "source_kind":
                    edge[
                        "source_kind"
                    ],
                "source_label":
                    edge[
                        "source_label"
                    ],
                "current_relationship":
                    edge[
                        "relationship"
                    ],
                "target_kind":
                    edge[
                        "target_kind"
                    ],
                "target_label":
                    edge[
                        "target_label"
                    ],
                "latest_human_review": {
                    "review_id":
                        edge.get(
                            "base_review_id"
                        ),
                    "decision":
                        edge.get(
                            "base_review_decision"
                        ),
                    "amended_relationship":
                        edge.get(
                            "base_amended_relationship"
                        ),
                },
            },
            "source_evidence":
                evidence_text,
        },
        ensure_ascii=False,
    ),
)

action = str(
    response.get(
        "action"
    )
    or ""
).strip().upper()

proposed_relationship = str(
    response.get(
        "proposed_relationship"
    )
    or ""
).strip().upper()

rationale = str(
    response.get(
        "rationale"
    )
    or ""
).strip()

returned_ids = {
    str(value)
    for value in response.get(
        "passage_ids",
        [],
    )
}

valid_ids = sorted(
    returned_ids
    & set(
        passage_by_id
    )
)

valid_actions = {
    "KEEP",
    "CHANGE_RELATIONSHIP",
    "REJECT_RELATIONSHIP",
    "INSUFFICIENT_EVIDENCE",
}

grounded = True
grounding_issue = None

if action not in valid_actions:
    grounded = False
    grounding_issue = (
        "Assistant returned an unsupported action."
    )

if (
    action
    == "CHANGE_RELATIONSHIP"
):
    if (
        proposed_relationship
        not in ALLOWED_RELATIONSHIPS
        or proposed_relationship
        == edge[
            "relationship"
        ]
    ):
        grounded = False
        grounding_issue = (
            "Assistant returned an invalid or unchanged replacement relationship."
        )
elif proposed_relationship:
    grounded = False
    grounding_issue = (
        "Only CHANGE_RELATIONSHIP may contain proposed_relationship."
    )

if (
    action
    in {
        "KEEP",
        "CHANGE_RELATIONSHIP",
        "REJECT_RELATIONSHIP",
    }
    and not valid_ids
):
    grounded = False
    grounding_issue = (
        "Assistant proposal contains no valid supporting passage IDs."
    )

if not grounded:
    assistant_status = (
        "NO_GROUNDED_PROPOSAL"
    )
    action = (
        "INSUFFICIENT_EVIDENCE"
    )
    proposed_relationship = ""
    valid_ids = []
    rationale = (
        grounding_issue
        or "The assistant proposal was not sufficiently grounded."
    )
else:
    assistant_status = (
        "ASSISTANT_PROPOSED"
        if action
        != "INSUFFICIENT_EVIDENCE"
        else "NO_GROUNDED_PROPOSAL"
    )

# COMMAND ----------

reference_by_id = {}

for reference in (
    edge.get(
        "evidence_references"
    )
    or []
):
    reference_by_id.setdefault(
        reference,
        True,
    )

evidence_references = (
    edge.get(
        "evidence_references"
    )
    or []
)

evidence_locations = (
    edge.get(
        "evidence_locations"
    )
    or []
)

proposal_id = (
    "relationship_correction_"
    + hashlib.sha256(
        (
            analysis_id
            + "|"
            + model_run_id
            + "|"
            + edge_id
            + "|"
            + str(
                edge.get(
                    "base_review_id"
                )
                or "NO_REVIEW"
            )
            + "|"
            + PROPOSAL_VERSION
        ).encode(
            "utf-8"
        )
    ).hexdigest()[:24]
)

with driver.session() as session:
    session.run(
        """
        CREATE CONSTRAINT relationship_correction_proposal_id_unique
        IF NOT EXISTS
        FOR (p:RelationshipCorrectionProposal)
        REQUIRE p.proposal_id IS UNIQUE
        """
    ).consume()

    session.run(
        """
        MATCH (a:AnalysisGroup {
            analysis_id: $analysis_id
        })
        MATCH (source:KGNode {
            analysis_id: $analysis_id,
            model_run_id: $model_run_id,
            node_id: $source_node_id
        })
        MATCH (target:KGNode {
            analysis_id: $analysis_id,
            model_run_id: $model_run_id,
            node_id: $target_node_id
        })
        MERGE (p:RelationshipCorrectionProposal {
            proposal_id: $proposal_id
        })
        ON CREATE SET
            p.created_at = datetime()
        SET
            p.analysis_id = $analysis_id,
            p.model_run_id = $model_run_id,
            p.edge_id = $edge_id,
            p.source_node_id = $source_node_id,
            p.source_label = $source_label,
            p.target_node_id = $target_node_id,
            p.target_label = $target_label,
            p.original_relationship = $original_relationship,
            p.base_relationship_review_id = $base_review_id,
            p.assistant_status = $assistant_status,
            p.action = $action,
            p.proposed_relationship = $proposed_relationship,
            p.rationale = $rationale,
            p.evidence_passage_ids = $evidence_passage_ids,
            p.evidence_references = $evidence_references,
            p.evidence_locations = $evidence_locations,
            p.proposal_version = $proposal_version,
            p.model_service = $model_service,
            p.updated_at = datetime()
        MERGE (a)-[:HAS_RELATIONSHIP_CORRECTION_PROPOSAL]->(p)
        MERGE (p)-[:PROPOSES_CORRECTION_OF]->(source)
        MERGE (p)-[:PROPOSES_CORRECTION_TOWARD]->(target)
        """,
        proposal_id=proposal_id,
        analysis_id=analysis_id,
        model_run_id=model_run_id,
        edge_id=edge_id,
        source_node_id=edge[
            "source_node_id"
        ],
        source_label=edge[
            "source_label"
        ],
        target_node_id=edge[
            "target_node_id"
        ],
        target_label=edge[
            "target_label"
        ],
        original_relationship=edge[
            "relationship"
        ],
        base_review_id=edge.get(
            "base_review_id"
        ),
        assistant_status=
            assistant_status,
        action=action,
        proposed_relationship=(
            proposed_relationship
            or None
        ),
        rationale=rationale,
        evidence_passage_ids=
            valid_ids,
        evidence_references=
            evidence_references,
        evidence_locations=
            evidence_locations,
        proposal_version=
            PROPOSAL_VERSION,
        model_service=
            model_service,
    ).consume()

    session.run(
        """
        MATCH (a:AnalysisGroup {
            analysis_id: $analysis_id
        })
        SET
            a.relationship_correction_status = 'COMPLETED',
            a.relationship_correction_model_run_id = $model_run_id,
            a.relationship_correction_edge_id = $edge_id,
            a.relationship_correction_proposal_id = $proposal_id,
            a.relationship_correction_updated_at = datetime(),
            a.relationship_correction_error = NULL
        """,
        analysis_id=analysis_id,
        model_run_id=model_run_id,
        edge_id=edge_id,
        proposal_id=proposal_id,
    ).consume()

print("")
print(
    "RELATIONSHIP CORRECTION PROPOSAL COMPLETE"
)
print(
    "proposal_id:",
    proposal_id,
)
print(
    "assistant_status:",
    assistant_status,
)
print(
    "action:",
    action,
)
print(
    "proposed_relationship:",
    proposed_relationship or "—",
)
print(
    "supporting passages:",
    len(valid_ids),
)

driver.close()
