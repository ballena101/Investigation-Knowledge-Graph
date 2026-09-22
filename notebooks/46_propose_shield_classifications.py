# Databricks notebook source
# MAGIC %md
# MAGIC # 46 — Propose SHIELD classification for human-validated contributing factors
# MAGIC
# MAGIC Gate 1 is mandatory:
# MAGIC a contributing factor becomes eligible only when the latest human
# MAGIC relationship review confirms:
# MAGIC
# MAGIC ContributingFactor — CONTRIBUTED_TO → target
# MAGIC
# MAGIC The model then proposes a SHIELD classification from deterministically
# MAGIC retrieved SHIELD passages. The proposal is never authoritative until
# MAGIC Gate 2 human SHIELD review.

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

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1 databricks-sdk==0.139.0

# COMMAND ----------

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    ChatMessage,
    ChatMessageRole,
)
from neo4j import GraphDatabase

analysis_id = dbutils.widgets.get(
    "analysis_id"
).strip()
model_run_id = dbutils.widgets.get(
    "model_run_id"
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

PROPOSAL_VERSION = "IKF_SHIELD_PROPOSAL_V0.1"
SHIELD_DOCUMENT_TABLE = (
    "bdw_analysis_prod.kg_poc.shield_document"
)
SHIELD_PASSAGE_TABLE = (
    "bdw_analysis_prod.kg_poc.shield_passage"
)

MAX_SHIELD_PASSAGES = 12
MAX_SHIELD_CHARS = 24000

# COMMAND ----------

# Reuse MAIRA's governed deterministic free-text retrieval implementation.
current_notebook_path = (
    dbutils.notebook.entry_point
    .getDbutils()
    .notebook()
    .getContext()
    .notebookPath()
    .get()
)
workspace_notebook_path = (
    "/Workspace" + current_notebook_path
    if current_notebook_path.startswith(
        "/Users/"
    )
    else current_notebook_path
)
ikf_repo_root = (
    workspace_notebook_path
    .rsplit(
        "/notebooks/",
        1,
    )[0]
)
workspace_user_root = ikf_repo_root.rsplit(
    "/",
    1,
)[0]

for candidate in (
    os.path.join(
        workspace_user_root,
        "MAIRA",
        "src",
    ),
    os.path.join(
        workspace_user_root,
        "MAIRA-main",
        "src",
    ),
):
    if os.path.isdir(candidate):
        sys.path.insert(
            0,
            candidate,
        )

try:
    from maira.retrieval import (
        retrieve_free_text,
    )
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "MAIRA deterministic retrieval is unavailable to the SHIELD Job."
    ) from exc

# COMMAND ----------

for table_name in (
    SHIELD_DOCUMENT_TABLE,
    SHIELD_PASSAGE_TABLE,
):
    if not spark.catalog.tableExists(
        table_name
    ):
        raise RuntimeError(
            "Persistent SHIELD corpus is not indexed. "
            "Run notebook 45 first."
        )

shield_documents = {
    row["shield_document_id"]:
        row.asDict(recursive=True)
    for row in (
        spark.table(
            SHIELD_DOCUMENT_TABLE
        )
        .select(
            "shield_document_id",
            "filename",
            "file_sha256",
            "corpus_snapshot_id",
        )
        .collect()
    )
}

shield_passages = [
    {
        "document_id":
            row["shield_document_id"],
        "passage_id":
            row["shield_passage_id"],
        "report_package_id": None,
        "passage_number":
            row["passage_number"],
        "start_page":
            row["page_start"],
        "end_page":
            row["page_end"],
        "passage_text":
            row["passage_text"],
    }
    for row in (
        spark.table(
            SHIELD_PASSAGE_TABLE
        )
        .select(
            "shield_document_id",
            "shield_passage_id",
            "passage_number",
            "page_start",
            "page_end",
            "passage_text",
        )
        .orderBy(
            "shield_document_id",
            "passage_number",
        )
        .collect()
    )
]

if not shield_passages:
    raise RuntimeError(
        "Persistent SHIELD corpus has no passages."
    )

snapshot_ids = sorted(
    {
        item.get(
            "corpus_snapshot_id"
        )
        for item in shield_documents.values()
        if item.get(
            "corpus_snapshot_id"
        )
    }
)

if len(snapshot_ids) != 1:
    raise RuntimeError(
        "SHIELD corpus must resolve to exactly one current snapshot."
    )

shield_snapshot_id = snapshot_ids[0]

print(
    "SHIELD corpus snapshot:",
    shield_snapshot_id,
)
print(
    "SHIELD passages:",
    len(shield_passages),
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

w = WorkspaceClient()

# COMMAND ----------

with driver.session() as session:
    meta_record = session.run(
        """
        MATCH (a:AnalysisGroup {
            analysis_id: $analysis_id
        })-[:HAS_MODEL_RUN]->(
            m:ModelRun {
                model_run_id: $model_run_id
            }
        )
        RETURN
            a.analysis_title AS analysis_title,
            properties(a)["information_class"] AS information_class,
            m.model_service AS model_service,
            m.status AS model_status
        """,
        analysis_id=analysis_id,
        model_run_id=model_run_id,
    ).single()

if meta_record is None:
    driver.close()
    raise ValueError(
        "Analysis/model run was not found."
    )

meta = meta_record.data()

if meta.get("model_status") != "COMPLETED":
    driver.close()
    raise ValueError(
        "SHIELD proposals require a completed model graph."
    )

model_service = meta.get(
    "model_service"
)

if not model_service:
    driver.close()
    raise ValueError(
        "Selected ModelRun has no model service."
    )

# COMMAND ----------

# Gate 1: latest human relationship review must confirm a ContributingFactor
# CONTRIBUTED_TO relationship. Rejected or differently-amended relationships
# are ineligible.

with driver.session() as session:
    eligible_factors = [
        record.data()
        for record in session.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })-[:HAS_RELATIONSHIP_REVIEW]->(
                review:RelationshipReview {
                    model_run_id: $model_run_id
                }
            )
            WITH review
            ORDER BY review.reviewed_at DESC
            WITH
                review.edge_id AS edge_id,
                collect(review)[0] AS latest
            MATCH (source:KGNode {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                node_id: latest.source_node_id
            })
            MATCH (target:KGNode {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                node_id: latest.target_node_id
            })
            WHERE
                source.node_kind = 'ContributingFactor'
                AND (
                    (
                        latest.human_review_decision = 'VALIDATED'
                        AND latest.original_relationship = 'CONTRIBUTED_TO'
                    )
                    OR
                    (
                        latest.human_review_decision = 'AMENDED'
                        AND latest.amended_relationship = 'CONTRIBUTED_TO'
                    )
                )
            RETURN
                latest.review_id AS gate_review_id,
                latest.edge_id AS edge_id,
                latest.human_review_decision AS gate_decision,
                source.node_id AS factor_node_id,
                source.label AS factor_label,
                properties(source)["description"] AS factor_description,
                coalesce(
                    properties(source)["evidence_passage_ids"],
                    []
                ) AS factor_evidence_passage_ids,
                target.node_id AS target_node_id,
                target.label AS target_label
            ORDER BY
                source.label,
                target.label
            """,
            analysis_id=analysis_id,
            model_run_id=model_run_id,
        )
    ]

print(
    "Gate-1 eligible contributing factors:",
    len(eligible_factors),
)

if not eligible_factors:
    with driver.session() as session:
        session.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })
            SET
                a.shield_proposal_status = 'NO_ELIGIBLE_VALIDATED_CF',
                a.shield_proposal_model_run_id = $model_run_id,
                a.shield_proposal_updated_at = datetime(),
                a.shield_proposal_error = NULL
            """,
            analysis_id=analysis_id,
            model_run_id=model_run_id,
        ).consume()

    driver.close()
    dbutils.notebook.exit(
        "NO_ELIGIBLE_VALIDATED_CF"
    )

# COMMAND ----------

def extract_chat_final_text(content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if (
                isinstance(item, dict)
                and str(
                    item.get("type")
                    or ""
                ).lower()
                in {
                    "text",
                    "output_text",
                }
                and item.get("text")
                is not None
            ):
                parts.append(
                    str(
                        item["text"]
                    )
                )
        return "\n".join(parts)
    return str(content)


def strip_code_fences(value):
    text = str(
        value or ""
    ).strip()
    fence = chr(96) * 3

    if text.startswith(fence):
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
        active_prompt = user_prompt
        if attempt:
            active_prompt += (
                "\n\nReturn one valid JSON object only. "
                "Do not use Markdown fences."
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
                            1200,
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
                    "SHIELD proposal model request failed "
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

            text = extract_chat_final_text(
                choices[0]
                .get(
                    "message",
                    {},
                )
                .get(
                    "content"
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
                    max_tokens=1200,
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
        "SHIELD proposal response was not valid JSON: "
        + str(last_error)
    )


SYSTEM_PROMPT = """
You propose a SHIELD classification for one HUMAN-VALIDATED contributing
factor.

The SHIELD passages supplied by the user are the only classification source.

Rules:
1. The contributing factor has already passed Gate 1 human validation.
2. You may propose only a SHIELD label/code/path explicitly present in the
   supplied SHIELD passages.
3. Do not invent, expand or reinterpret the SHIELD taxonomy.
4. If the retrieved passages do not support one clear classification, return
   NO_GROUNDED_PROPOSAL.
5. The proposal is a candidate only. Gate 2 human SHIELD review remains
   authoritative.
6. Return supporting shield_passage_ids.
7. Return JSON only.

Required JSON:
{
  "status": "PROPOSED or NO_GROUNDED_PROPOSAL",
  "shield_label": "exact source label or empty",
  "shield_code": "exact source code or empty",
  "shield_path": "exact/faithful source hierarchy or empty",
  "shield_passage_ids": ["shield_passage_..."],
  "rationale": "brief source-grounded reason"
}
"""


def reference_for_hit(
    hit,
):
    document = shield_documents.get(
        hit.document_id,
        {},
    )
    filename = (
        document.get("filename")
        or hit.document_id
    )

    if hit.start_page is None:
        page = "page unknown"
    elif (
        hit.end_page is None
        or hit.end_page
        == hit.start_page
    ):
        page = (
            f"p. {hit.start_page}"
        )
    else:
        page = (
            f"pp. {hit.start_page}–"
            f"{hit.end_page}"
        )

    return (
        f"{filename} · {page}"
    )


def location_for_hit(
    hit,
):
    start = (
        ""
        if hit.start_page is None
        else str(hit.start_page)
    )
    end = (
        ""
        if hit.end_page is None
        else str(hit.end_page)
    )
    return (
        f"{hit.document_id}|"
        f"{start}|{end}"
    )


proposal_rows = []

for factor in eligible_factors:
    query_text = " ".join(
        [
            str(
                factor.get(
                    "factor_label"
                )
                or ""
            ),
            str(
                factor.get(
                    "factor_description"
                )
                or ""
            ),
            str(
                factor.get(
                    "target_label"
                )
                or ""
            ),
        ]
    ).strip()

    retrieval = retrieve_free_text(
        shield_passages,
        query_text,
        max_passages=
            MAX_SHIELD_PASSAGES,
        max_characters=
            MAX_SHIELD_CHARS,
    )

    hit_by_id = {
        hit.passage_id:
            hit
        for hit in retrieval.hits
    }

    selected_source_text = (
        "\n\n---\n\n".join(
            (
                f"[SHIELD_PASSAGE_ID: "
                f"{hit.passage_id}]\n"
                f"[DOCUMENT: "
                f"{shield_documents.get(hit.document_id, {}).get('filename', hit.document_id)}]\n"
                f"[PAGE_START: "
                f"{hit.start_page}]\n"
                f"[PAGE_END: "
                f"{hit.end_page}]\n"
                f"{hit.passage_text}"
            )
            for hit in retrieval.hits
        )
    )

    proposal_id = (
        "shield_proposal_"
        + hashlib.sha256(
            (
                analysis_id
                + "|"
                + model_run_id
                + "|"
                + factor[
                    "edge_id"
                ]
                + "|"
                + factor[
                    "gate_review_id"
                ]
                + "|"
                + shield_snapshot_id
                + "|"
                + PROPOSAL_VERSION
            ).encode(
                "utf-8"
            )
        ).hexdigest()[:24]
    )

    if not retrieval.hits:
        proposal_rows.append(
            {
                "proposal_id":
                    proposal_id,
                "factor": factor,
                "status":
                    "NO_GROUNDED_PROPOSAL",
                "label": None,
                "code": None,
                "path": None,
                "rationale":
                    "No deterministic SHIELD passage matched the validated contributing factor.",
                "retrieval": retrieval,
                "passage_ids": [],
                "references": [],
                "locations": [],
            }
        )
        continue

    response = query_model_json(
        SYSTEM_PROMPT,
        json.dumps(
            {
                "validated_contributing_factor": {
                    "label":
                        factor[
                            "factor_label"
                        ],
                    "description":
                        factor.get(
                            "factor_description"
                        )
                        or "",
                    "contributes_to":
                        factor[
                            "target_label"
                        ],
                    "gate_review_id":
                        factor[
                            "gate_review_id"
                        ],
                },
                "shield_passages":
                    selected_source_text,
            },
            ensure_ascii=False,
        ),
    )

    requested_status = str(
        response.get(
            "status"
        )
        or ""
    ).strip().upper()

    label = str(
        response.get(
            "shield_label"
        )
        or ""
    ).strip()
    code = str(
        response.get(
            "shield_code"
        )
        or ""
    ).strip()
    path = str(
        response.get(
            "shield_path"
        )
        or ""
    ).strip()
    rationale = str(
        response.get(
            "rationale"
        )
        or ""
    ).strip()

    returned_ids = {
        str(value)
        for value in response.get(
            "shield_passage_ids",
            [],
        )
    }

    valid_ids = sorted(
        returned_ids
        & set(
            hit_by_id
        )
    )

    grounding_text = (
        "\n".join(
            hit.passage_text
            for hit in retrieval.hits
        )
        .casefold()
    )

    grounded_label = bool(
        label
        and label.casefold()
        in grounding_text
    )
    grounded_code = (
        True
        if not code
        else code.casefold()
        in grounding_text
    )

    if (
        requested_status
        != "PROPOSED"
        or not valid_ids
        or not grounded_label
        or not grounded_code
    ):
        status = (
            "NO_GROUNDED_PROPOSAL"
        )
        label = None
        code = None
        path = None
        if not rationale:
            rationale = (
                "The model did not return a proposal grounded in the "
                "retrieved SHIELD source passages."
            )
        valid_ids = []
    else:
        status = (
            "ASSISTANT_PROPOSED"
        )

    proposal_rows.append(
        {
            "proposal_id":
                proposal_id,
            "factor": factor,
            "status": status,
            "label": label,
            "code": code,
            "path": path,
            "rationale":
                rationale,
            "retrieval":
                retrieval,
            "passage_ids":
                valid_ids,
            "references": [
                reference_for_hit(
                    hit_by_id[
                        passage_id
                    ]
                )
                for passage_id
                in valid_ids
            ],
            "locations": [
                location_for_hit(
                    hit_by_id[
                        passage_id
                    ]
                )
                for passage_id
                in valid_ids
            ],
        }
    )

print(
    "SHIELD proposals prepared:",
    len(proposal_rows),
)

# COMMAND ----------

with driver.session() as session:
    session.run(
        """
        CREATE CONSTRAINT shield_proposal_id_unique
        IF NOT EXISTS
        FOR (p:ShieldProposal)
        REQUIRE p.proposal_id IS UNIQUE
        """
    ).consume()

    for item in proposal_rows:
        factor = item[
            "factor"
        ]
        retrieval = item[
            "retrieval"
        ]

        session.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })
            MATCH (n:KGNode {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                node_id: $factor_node_id
            })
            MATCH (gate:RelationshipReview {
                review_id: $gate_review_id
            })
            MERGE (p:ShieldProposal {
                proposal_id: $proposal_id
            })
            ON CREATE SET
                p.created_at =
                    datetime()
            SET
                p.analysis_id =
                    $analysis_id,
                p.model_run_id =
                    $model_run_id,
                p.factor_node_id =
                    $factor_node_id,
                p.factor_label =
                    $factor_label,
                p.target_node_id =
                    $target_node_id,
                p.target_label =
                    $target_label,
                p.edge_id =
                    $edge_id,
                p.gate_relationship_review_id =
                    $gate_review_id,
                p.gate_human_decision =
                    $gate_human_decision,
                p.assistant_status =
                    $assistant_status,
                p.proposed_shield_label =
                    $proposed_shield_label,
                p.proposed_shield_code =
                    $proposed_shield_code,
                p.proposed_shield_path =
                    $proposed_shield_path,
                p.rationale =
                    $rationale,
                p.shield_passage_ids =
                    $shield_passage_ids,
                p.shield_references =
                    $shield_references,
                p.shield_locations =
                    $shield_locations,
                p.shield_corpus_snapshot_id =
                    $shield_corpus_snapshot_id,
                p.retrieval_method =
                    $retrieval_method,
                p.retrieval_candidate_count =
                    $retrieval_candidate_count,
                p.retrieval_selected_count =
                    $retrieval_selected_count,
                p.proposal_version =
                    $proposal_version,
                p.model_service =
                    $model_service,
                p.updated_at =
                    datetime()
            MERGE (a)-[:HAS_SHIELD_PROPOSAL]->(p)
            MERGE (p)-[:CLASSIFIES_FACTOR]->(n)
            MERGE (p)-[:GATED_BY_REVIEW]->(gate)
            """,
            analysis_id=analysis_id,
            model_run_id=model_run_id,
            factor_node_id=
                factor[
                    "factor_node_id"
                ],
            factor_label=
                factor[
                    "factor_label"
                ],
            target_node_id=
                factor[
                    "target_node_id"
                ],
            target_label=
                factor[
                    "target_label"
                ],
            edge_id=
                factor[
                    "edge_id"
                ],
            gate_review_id=
                factor[
                    "gate_review_id"
                ],
            gate_human_decision=
                factor[
                    "gate_decision"
                ],
            proposal_id=
                item[
                    "proposal_id"
                ],
            assistant_status=
                item[
                    "status"
                ],
            proposed_shield_label=
                item[
                    "label"
                ],
            proposed_shield_code=
                item[
                    "code"
                ],
            proposed_shield_path=
                item[
                    "path"
                ],
            rationale=
                item[
                    "rationale"
                ],
            shield_passage_ids=
                item[
                    "passage_ids"
                ],
            shield_references=
                item[
                    "references"
                ],
            shield_locations=
                item[
                    "locations"
                ],
            shield_corpus_snapshot_id=
                shield_snapshot_id,
            retrieval_method=
                retrieval.method,
            retrieval_candidate_count=
                retrieval.candidate_count,
            retrieval_selected_count=
                retrieval.selected_count,
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
            a.shield_proposal_status =
                'COMPLETED',
            a.shield_proposal_model_run_id =
                $model_run_id,
            a.shield_proposal_count =
                $proposal_count,
            a.shield_proposal_snapshot_id =
                $shield_snapshot_id,
            a.shield_proposal_updated_at =
                datetime(),
            a.shield_proposal_error =
                NULL
        """,
        analysis_id=analysis_id,
        model_run_id=model_run_id,
        proposal_count=len(
            proposal_rows
        ),
        shield_snapshot_id=
            shield_snapshot_id,
    ).consume()

print("")
print(
    "SHIELD PROPOSAL GENERATION COMPLETE"
)
print(
    "analysis_id:",
    analysis_id,
)
print(
    "model_run_id:",
    model_run_id,
)
print(
    "eligible factors:",
    len(
        eligible_factors
    ),
)
print(
    "assistant proposals:",
    sum(
        1
        for item in proposal_rows
        if item["status"]
        == "ASSISTANT_PROPOSED"
    ),
)
print(
    "no grounded proposal:",
    sum(
        1
        for item in proposal_rows
        if item["status"]
        == "NO_GROUNDED_PROPOSAL"
    ),
)

driver.close()
