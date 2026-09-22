# Databricks notebook source
# MAGIC %md
# MAGIC # 40 — Propose EMCIP mappings for one analysis/model graph
# MAGIC
# MAGIC Generates assistant EMCIP mapping proposals for the selected generic
# MAGIC AnalysisGroup/ModelRun.
# MAGIC
# MAGIC Governance:
# MAGIC - MAIRA's persisted EMCIP operational registry is the only taxonomy;
# MAGIC - deterministic lexical/structural ranking creates a bounded shortlist;
# MAGIC - the LLM may select one candidate from that shortlist or NO_MAPPING;
# MAGIC - the LLM cannot invent a taxonomy code;
# MAGIC - proposals are stored separately from KGNode;
# MAGIC - human review remains authoritative and append-only.

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
import re
import time
import unicodedata
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

MAPPING_VERSION = "IKF_EMCIP_MAPPING_PROPOSAL_V0.1"
REGISTRY_TABLE = (
    "bdw_analysis_prod.maira.emcip_operational_registry"
)
MAX_CANDIDATES = 12

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

w = WorkspaceClient()

# COMMAND ----------

if not spark.catalog.tableExists(
    REGISTRY_TABLE
):
    driver.close()
    raise RuntimeError(
        "MAIRA EMCIP operational registry is unavailable."
    )

registry_df = (
    spark.table(REGISTRY_TABLE)
    .filter(
        "code_idcode IS NOT NULL "
        "AND code_value IS NOT NULL"
    )
    .select(
        "source_document_id",
        "registry_rule_version",
        "entity_name",
        "entity_path",
        "attribute_name",
        "attribute_idcode",
        "code_value",
        "code_idcode",
    )
    .dropDuplicates()
)

registry_rows = [
    row.asDict(recursive=True)
    for row in registry_df.collect()
]

if not registry_rows:
    driver.close()
    raise RuntimeError(
        "MAIRA EMCIP operational registry contains no controlled values."
    )

taxonomy_source_ids = sorted(
    {
        str(row["source_document_id"])
        for row in registry_rows
        if row.get("source_document_id")
    }
)
registry_versions = sorted(
    {
        str(row["registry_rule_version"])
        for row in registry_rows
        if row.get("registry_rule_version")
    }
)

print("Registry controlled values:", len(registry_rows))
print("Taxonomy source documents:", taxonomy_source_ids)
print("Registry versions:", registry_versions)

# COMMAND ----------

with driver.session() as session:
    meta = session.run(
        """
        MATCH (a:AnalysisGroup {
            analysis_id: $analysis_id
        })-[:HAS_MODEL_RUN]->(m:ModelRun {
            model_run_id: $model_run_id
        })
        RETURN
            a.analysis_title AS analysis_title,
            properties(a)["information_class"] AS information_class,
            m.model_key AS model_key,
            m.model_label AS model_label,
            m.model_service AS model_service,
            m.status AS model_status
        """,
        analysis_id=analysis_id,
        model_run_id=model_run_id,
    ).single()

    node_rows = [
        record.data()
        for record in session.run(
            """
            MATCH (n:KGNode {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id
            })
            RETURN
                n.node_id AS node_id,
                n.node_kind AS node_kind,
                n.label AS label,
                properties(n)["description"] AS description,
                coalesce(
                    properties(n)["evidence_passage_ids"],
                    []
                ) AS passage_ids,
                coalesce(
                    properties(n)["evidence_references"],
                    []
                ) AS evidence_references,
                coalesce(
                    properties(n)["evidence_locations"],
                    []
                ) AS evidence_locations
            ORDER BY n.node_kind, n.label
            """,
            analysis_id=analysis_id,
            model_run_id=model_run_id,
        )
    ]

if meta is None:
    driver.close()
    raise ValueError(
        "Selected AnalysisGroup/ModelRun was not found."
    )

meta = meta.data()

if meta.get("model_status") != "COMPLETED":
    driver.close()
    raise ValueError(
        "EMCIP mapping proposals require a completed model graph."
    )

model_service = meta.get("model_service")

if not model_service:
    driver.close()
    raise ValueError(
        "The selected ModelRun has no model service."
    )

print("Analysis:", meta["analysis_title"])
print("Model:", meta.get("model_label"))
print("KG nodes:", len(node_rows))

# COMMAND ----------

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "into", "is", "of", "on", "or", "that", "the",
    "this", "to", "was", "were", "with",
}


def normalize_text(value):
    text = unicodedata.normalize(
        "NFKC",
        str(value or ""),
    ).casefold()
    text = re.sub(
        r"[^\w]+",
        " ",
        text,
        flags=re.UNICODE,
    )
    return " ".join(text.split())


def tokens(value):
    return {
        token
        for token in normalize_text(
            value
        ).split()
        if len(token) >= 3
        and token not in STOPWORDS
    }


def semantic_bonus(
    node_kind,
    entity_path,
    entity_name,
):
    path = (
        normalize_text(entity_path)
        + " "
        + normalize_text(entity_name)
    )

    if (
        node_kind == "ContributingFactor"
        and "contributing factor" in path
    ):
        return 60

    if (
        node_kind == "Recommendation"
        and "safety recommendation" in path
    ):
        return 60

    if (
        node_kind in {
            "Event",
            "System",
        }
        and (
            "accident event" in path
            or "casualty event" in path
        )
    ):
        return 45

    if (
        node_kind == "Vessel"
        and "vessel" in path
    ):
        return 25

    return 0


def candidate_shortlist(node):
    node_text = " ".join(
        [
            str(node.get("label") or ""),
            str(node.get("description") or ""),
        ]
    )
    node_norm = normalize_text(
        node_text
    )
    node_tokens = tokens(
        node_text
    )

    ranked = []

    for row in registry_rows:
        code_value = str(
            row.get("code_value") or ""
        ).strip()
        attribute_name = str(
            row.get("attribute_name") or ""
        ).strip()
        entity_path = str(
            row.get("entity_path") or ""
        ).strip()
        entity_name = str(
            row.get("entity_name") or ""
        ).strip()

        code_norm = normalize_text(
            code_value
        )
        code_tokens = tokens(
            code_value
        )
        attribute_tokens = tokens(
            attribute_name
        )

        overlap = len(
            node_tokens & code_tokens
        )
        attribute_overlap = len(
            node_tokens & attribute_tokens
        )

        score = (
            overlap * 18
            + attribute_overlap * 6
            + semantic_bonus(
                node.get("node_kind"),
                entity_path,
                entity_name,
            )
        )

        if (
            code_norm
            and code_norm in node_norm
        ):
            score += 120

        if (
            code_tokens
            and code_tokens.issubset(
                node_tokens
            )
        ):
            score += 70

        if score <= 0:
            continue

        raw_id = "|".join(
            [
                str(row.get("entity_path") or ""),
                str(row.get("attribute_name") or ""),
                code_value,
                str(row.get("code_idcode") or ""),
            ]
        )

        ranked.append(
            {
                "candidate_id": (
                    "emcip_candidate_"
                    + hashlib.sha256(
                        raw_id.encode("utf-8")
                    ).hexdigest()[:20]
                ),
                "score": score,
                "entity_name": entity_name,
                "entity_path": entity_path,
                "attribute_name": attribute_name,
                "attribute_idcode": row.get(
                    "attribute_idcode"
                ),
                "code_value": code_value,
                "code_idcode": row.get(
                    "code_idcode"
                ),
            }
        )

    ranked.sort(
        key=lambda item: (
            -int(item["score"]),
            item["entity_path"],
            item["attribute_name"],
            item["code_value"],
            item["code_idcode"] or "",
        )
    )

    unique = []
    seen = set()

    for item in ranked:
        key = (
            item["entity_path"],
            item["attribute_name"],
            item["code_idcode"],
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique) >= MAX_CANDIDATES:
            break

    return unique

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
                    item.get("type") or ""
                ).lower()
                in {
                    "text",
                    "output_text",
                }
            ):
                if item.get("text") is not None:
                    parts.append(
                        str(item["text"])
                    )
        return "\n".join(parts)
    return str(content)


def strip_code_fences(text):
    value = str(text or "").strip()
    fence = chr(96) * 3
    if value.startswith(fence):
        value = re.sub(
            r"^.{3}(?:json)?\s*",
            "",
            value,
            flags=re.IGNORECASE,
        )
        value = re.sub(
            r"\s*.{3}$",
            "",
            value,
        )
    return value.strip()


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
                        "model": model_service,
                        "messages": [
                            {
                                "role": "system",
                                "content": system_prompt,
                            },
                            {
                                "role": "user",
                                "content": active_prompt,
                            },
                        ],
                        "max_tokens": 1200,
                        "temperature": 0.0,
                    }
                ).encode("utf-8"),
                headers={
                    **w.config.authenticate(),
                    "Content-Type": (
                        "application/json"
                    ),
                },
                method="POST",
            )

            try:
                with urllib.request.urlopen(
                    request,
                    timeout=600,
                ) as response:
                    payload = json.loads(
                        response.read().decode(
                            "utf-8"
                        )
                    )
            except urllib.error.HTTPError as exc:
                body = exc.read().decode(
                    "utf-8",
                    errors="replace",
                )
                raise RuntimeError(
                    "EMCIP mapping model request failed "
                    f"with HTTP {exc.code}: "
                    f"{body[:1000]}"
                ) from exc

            choices = payload.get(
                "choices"
            ) or []
            if not choices:
                raise ValueError(
                    "Model returned no choice."
                )

            text = extract_chat_final_text(
                choices[0]
                .get("message", {})
                .get("content")
            )

        else:
            response = w.serving_endpoints.query(
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
            text = extract_chat_final_text(
                response.choices[0]
                .message.content
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
        "EMCIP mapping model response was not valid JSON: "
        + str(last_error)
    )

# COMMAND ----------

SYSTEM_PROMPT = """
You propose an EMCIP analytical mapping for one investigation-graph concept.

Rules:
1. You may select ONLY one candidate_id from the supplied candidate list, or
   return NO_MAPPING.
2. Never invent an EMCIP entity, attribute, code value or code identifier.
3. A lexical candidate is not automatically correct. Use the concept label,
   description and node kind to decide whether the candidate represents the
   same analytical concept.
4. If the candidates are ambiguous or none represent the concept, return
   NO_MAPPING.
5. This is only an assistant proposal. Human validation remains authoritative.
6. Return JSON only.

Required JSON:
{
  "selection": "candidate_id or NO_MAPPING",
  "rationale": "brief reason"
}
"""

proposal_rows = []

for node in node_rows:
    shortlist = candidate_shortlist(
        node
    )

    proposal_id = (
        "emcip_proposal_"
        + hashlib.sha256(
            (
                analysis_id
                + "|"
                + model_run_id
                + "|"
                + node["node_id"]
                + "|"
                + MAPPING_VERSION
            ).encode("utf-8")
        ).hexdigest()[:24]
    )

    if not shortlist:
        selected = None
        rationale = (
            "No deterministic EMCIP shortlist candidate was available."
        )
        assistant_status = "NO_MAPPING"
        proposal_method = (
            "NO_LEXICAL_CANDIDATE"
        )
    else:
        response = query_model_json(
            SYSTEM_PROMPT,
            json.dumps(
                {
                    "node": {
                        "node_kind": (
                            node["node_kind"]
                        ),
                        "label": node["label"],
                        "description": (
                            node.get(
                                "description"
                            )
                            or ""
                        ),
                    },
                    "candidates": shortlist,
                },
                ensure_ascii=False,
            ),
        )

        selection = str(
            response.get(
                "selection"
            )
            or ""
        ).strip()
        rationale = str(
            response.get(
                "rationale"
            )
            or ""
        ).strip()

        candidate_by_id = {
            item["candidate_id"]: item
            for item in shortlist
        }

        selected = candidate_by_id.get(
            selection
        )

        if selection == "NO_MAPPING":
            assistant_status = "NO_MAPPING"
            proposal_method = (
                "LLM_NO_MAPPING"
            )
        elif selected is None:
            assistant_status = (
                "NO_MAPPING"
            )
            proposal_method = (
                "INVALID_LLM_SELECTION"
            )
            rationale = (
                "The model returned a candidate outside the governed "
                "shortlist. No mapping proposal was accepted."
            )
        else:
            assistant_status = (
                "ASSISTANT_PROPOSED"
            )
            proposal_method = (
                "DETERMINISTIC_SHORTLIST_LLM_SELECTION"
            )

    proposal_rows.append(
        {
            "proposal_id": proposal_id,
            "node": node,
            "shortlist": shortlist,
            "selected": selected,
            "assistant_status": assistant_status,
            "proposal_method": proposal_method,
            "rationale": rationale,
        }
    )

print("Mapping proposals prepared:", len(proposal_rows))

# COMMAND ----------

with driver.session() as session:
    session.run(
        """
        CREATE CONSTRAINT emcip_mapping_proposal_id_unique
        IF NOT EXISTS
        FOR (p:EMCIPMappingProposal)
        REQUIRE p.proposal_id IS UNIQUE
        """
    ).consume()

    for item in proposal_rows:
        node = item["node"]
        selected = item["selected"]

        session.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })
            MATCH (n:KGNode {
                analysis_id: $analysis_id,
                model_run_id: $model_run_id,
                node_id: $node_id
            })
            MERGE (p:EMCIPMappingProposal {
                proposal_id: $proposal_id
            })
            ON CREATE SET
                p.created_at = datetime()
            SET
                p.analysis_id = $analysis_id,
                p.model_run_id = $model_run_id,
                p.node_id = $node_id,
                p.node_label = $node_label,
                p.node_kind = $node_kind,
                p.assistant_mapping_status = $assistant_mapping_status,
                p.proposal_method = $proposal_method,
                p.proposed_entity = $proposed_entity,
                p.proposed_entity_path = $proposed_entity_path,
                p.proposed_attribute_name = $proposed_attribute_name,
                p.proposed_attribute_idcode = $proposed_attribute_idcode,
                p.proposed_code_value = $proposed_code_value,
                p.proposed_code_idcode = $proposed_code_idcode,
                p.candidate_options_json = $candidate_options_json,
                p.rationale = $rationale,
                p.evidence_passage_ids = $evidence_passage_ids,
                p.evidence_references = $evidence_references,
                p.evidence_locations = $evidence_locations,
                p.taxonomy_source_document_ids = $taxonomy_source_document_ids,
                p.taxonomy_registry_versions = $taxonomy_registry_versions,
                p.mapping_version = $mapping_version,
                p.model_service = $model_service,
                p.updated_at = datetime()
            MERGE (a)-[:HAS_EMCIP_MAPPING_PROPOSAL]->(p)
            MERGE (p)-[:MAPS_NODE]->(n)
            """,
            analysis_id=analysis_id,
            model_run_id=model_run_id,
            proposal_id=item["proposal_id"],
            node_id=node["node_id"],
            node_label=node["label"],
            node_kind=node["node_kind"],
            assistant_mapping_status=item[
                "assistant_status"
            ],
            proposal_method=item[
                "proposal_method"
            ],
            proposed_entity=(
                selected.get(
                    "entity_name"
                )
                if selected
                else None
            ),
            proposed_entity_path=(
                selected.get(
                    "entity_path"
                )
                if selected
                else None
            ),
            proposed_attribute_name=(
                selected.get(
                    "attribute_name"
                )
                if selected
                else None
            ),
            proposed_attribute_idcode=(
                selected.get(
                    "attribute_idcode"
                )
                if selected
                else None
            ),
            proposed_code_value=(
                selected.get(
                    "code_value"
                )
                if selected
                else None
            ),
            proposed_code_idcode=(
                selected.get(
                    "code_idcode"
                )
                if selected
                else None
            ),
            candidate_options_json=json.dumps(
                item["shortlist"],
                ensure_ascii=False,
                sort_keys=True,
            ),
            rationale=item[
                "rationale"
            ],
            evidence_passage_ids=node.get(
                "passage_ids"
            )
            or [],
            evidence_references=node.get(
                "evidence_references"
            )
            or [],
            evidence_locations=node.get(
                "evidence_locations"
            )
            or [],
            taxonomy_source_document_ids=taxonomy_source_ids,
            taxonomy_registry_versions=registry_versions,
            mapping_version=MAPPING_VERSION,
            model_service=model_service,
        ).consume()

    session.run(
        """
        MATCH (a:AnalysisGroup {
            analysis_id: $analysis_id
        })
        SET
            a.emcip_mapping_proposal_status = 'COMPLETED',
            a.emcip_mapping_proposal_model_run_id = $model_run_id,
            a.emcip_mapping_proposal_count = $proposal_count,
            a.emcip_mapping_proposal_version = $mapping_version,
            a.emcip_mapping_proposal_updated_at = datetime()
        """,
        analysis_id=analysis_id,
        model_run_id=model_run_id,
        proposal_count=len(proposal_rows),
        mapping_version=MAPPING_VERSION,
    ).consume()

print("")
print("PASS — GENERIC EMCIP MAPPING PROPOSALS PERSISTED")
print("analysis_id:", analysis_id)
print("model_run_id:", model_run_id)
print("proposals:", len(proposal_rows))

driver.close()
