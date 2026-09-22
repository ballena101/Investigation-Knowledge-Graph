# Databricks notebook source
# MAGIC %md
# MAGIC # 43 — Validate information-class pre-screen routing
# MAGIC
# MAGIC Read-only validation of the deterministic Class-D escalation control.
# MAGIC
# MAGIC Checks:
# MAGIC - published MAIRA Class-B analyses may be explicitly exempt;
# MAGIC - a non-D analysis flagged REQUIRES_CLASS_D is failed closed before
# MAGIC   model analysis;
# MAGIC - blocked analyses have no persisted analysis passages;
# MAGIC - blocked direct-text payloads have been purged;
# MAGIC - Class D is never downgraded because the detector found no indicator;
# MAGIC - no ModelRun exists for a blocked non-D analysis.

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

ANALYSIS_PASSAGE_TABLE = (
    "bdw_analysis_prod.kg_poc.analysis_passage"
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

where_clause = (
    "WHERE a.analysis_id = $analysis_id"
    if analysis_id
    else (
        "WHERE properties(a)['classification_prescreen_status'] "
        "IS NOT NULL"
    )
)

query = f"""
MATCH (a:AnalysisGroup)
{where_clause}
OPTIONAL MATCH (a)-[:HAS_SOURCE]->(d:SourceDocument)
OPTIONAL MATCH (a)-[:HAS_SOURCE_TEXT]->(t:DirectTextSource)
OPTIONAL MATCH (a)-[:HAS_MODEL_RUN]->(m:ModelRun)
WITH
    a,
    collect(DISTINCT {{
        document_id: d.document_id,
        source_managed_by: coalesce(
            properties(d)["source_managed_by"],
            "IKF"
        )
    }}) AS documents,
    head(collect(DISTINCT t)) AS text_source,
    count(DISTINCT m) AS model_run_count
RETURN
    a.analysis_id AS analysis_id,
    properties(a)["information_class"] AS information_class,
    properties(a)["input_mode"] AS input_mode,
    a.status AS status,
    a.processing_stage AS processing_stage,
    properties(a)["classification_prescreen_version"] AS prescreen_version,
    properties(a)["classification_prescreen_status"] AS prescreen_status,
    coalesce(
        properties(a)["classification_prescreen_rule_ids"],
        []
    ) AS rule_ids,
    properties(a)["classification_prescreen_required_class"] AS required_class,
    documents,
    CASE
        WHEN text_source IS NULL
        THEN NULL
        ELSE text_source.encrypted_text
    END AS encrypted_text,
    CASE
        WHEN text_source IS NULL
        THEN NULL
        ELSE properties(text_source)["retention_status"]
    END AS text_retention_status,
    model_run_count
ORDER BY a.created_at, a.analysis_id
"""

with driver.session() as session:
    analyses = [
        record.data()
        for record in session.run(
            query,
            analysis_id=analysis_id or None,
        )
    ]

print(
    "Analyses with pre-screen metadata:",
    len(analyses),
)

if not analyses:
    driver.close()
    dbutils.notebook.exit(
        "NO_PRESCREENED_ANALYSES"
    )

# COMMAND ----------

validation_rows = []
errors = []

for item in analyses:
    item_errors = []
    current_analysis_id = item[
        "analysis_id"
    ]
    declared_class = (
        item.get("information_class")
        or "B"
    )
    prescreen_status = (
        item.get("prescreen_status")
        or ""
    )

    passage_count = (
        spark.table(
            ANALYSIS_PASSAGE_TABLE
        )
        .filter(
            F.col("analysis_id")
            == current_analysis_id
        )
        .count()
    )

    if (
        prescreen_status
        == "PUBLISHED_MAIRA_CLASS_B_EXEMPT"
    ):
        if declared_class != "B":
            item_errors.append(
                "MAIRA published exemption is attached to a non-B analysis"
            )

        source_owners = {
            document.get(
                "source_managed_by"
            )
            for document in (
                item.get("documents")
                or []
            )
            if document.get(
                "document_id"
            )
        }

        if source_owners != {"MAIRA"}:
            item_errors.append(
                "published MAIRA exemption has non-MAIRA source ownership"
            )

    if prescreen_status == "REQUIRES_CLASS_D":
        if declared_class == "D":
            item_errors.append(
                "REQUIRES_CLASS_D should represent escalation of a non-D route"
            )

        if item.get(
            "required_class"
        ) != "D":
            item_errors.append(
                "REQUIRES_CLASS_D has no required_class D"
            )

        if not (
            item.get("status") == "FAILED"
            and item.get(
                "processing_stage"
            )
            == "CLASSIFICATION_PRESCREEN_BLOCKED"
        ):
            item_errors.append(
                "Class-D escalation did not fail closed at the prescreen stage"
            )

        if passage_count != 0:
            item_errors.append(
                "blocked non-D analysis has persisted analysis passages"
            )

        if int(
            item.get(
                "model_run_count"
            )
            or 0
        ) != 0:
            item_errors.append(
                "blocked non-D analysis has a ModelRun"
            )

        if (
            item.get("input_mode")
            == "DIRECT_TEXT"
        ):
            if item.get(
                "encrypted_text"
            ):
                item_errors.append(
                    "blocked direct-text encrypted payload was not purged"
                )

            if (
                item.get(
                    "text_retention_status"
                )
                != "ENCRYPTED_PAYLOAD_PURGED_AFTER_PRESCREEN"
            ):
                item_errors.append(
                    "blocked direct-text source has unexpected purge status"
                )

    if declared_class == "D":
        if prescreen_status not in {
            "DECLARED_D_WITH_STRONG_INDICATORS",
            "DECLARED_D_NO_STRONG_INDICATORS",
            "NO_SCREENABLE_RAW_CONTENT",
        }:
            item_errors.append(
                "Class D analysis has an unexpected pre-screen status"
            )

        if item.get(
            "required_class"
        ) not in {
            None,
            "D",
        }:
            item_errors.append(
                "Class D analysis was assigned a lower required class"
            )

    if (
        declared_class in {"A", "C"}
        and item.get("status")
        in {
            "EVIDENCE_READY",
            "ANALYSING",
            "COMPLETED",
        }
        and prescreen_status
        not in {
            "PASSED_NO_STRONG_D_INDICATOR",
            "NO_SCREENABLE_RAW_CONTENT",
        }
    ):
        item_errors.append(
            "non-D IKF analysis proceeded without a passing prescreen status"
        )

    validation_rows.append(
        {
            "analysis_id": current_analysis_id,
            "declared_class": declared_class,
            "prescreen_status": prescreen_status,
            "rules": len(
                item.get("rule_ids")
                or []
            ),
            "analysis_status": item.get(
                "status"
            ),
            "processing_stage": item.get(
                "processing_stage"
            ),
            "passages": passage_count,
            "model_runs": int(
                item.get(
                    "model_run_count"
                )
                or 0
            ),
            "errors": len(
                item_errors
            ),
            "error_detail": " | ".join(
                item_errors
            ),
        }
    )

    errors.extend(
        f"{current_analysis_id}: {value}"
        for value in item_errors
    )

display(
    spark.createDataFrame(
        validation_rows
    )
)

# COMMAND ----------

# APP PREFLIGHT AUDIT VALIDATION
#
# Blocked UI submissions do not create an AnalysisGroup, so their compact
# audit trail is validated separately. The audit node must never reproduce
# matched/raw protected text.

with driver.session() as session:
    app_prescreen_attempts = [
        record.data()
        for record in session.run(
            """
            MATCH (e:ClassificationPrescreenAttempt)
            RETURN
                e.event_id AS event_id,
                e.prescreen_version AS prescreen_version,
                e.prescreen_layer AS prescreen_layer,
                e.decision AS decision,
                e.required_class AS required_class,
                e.declared_class AS declared_class,
                e.input_mode AS input_mode,
                coalesce(e.rule_ids, []) AS rule_ids,
                coalesce(e.document_ids, []) AS document_ids,
                e.content_sha256 AS content_sha256,
                keys(e) AS property_keys
            ORDER BY e.created_at, e.event_id
            """
        )
    ]

audit_validation_rows = []

for item in app_prescreen_attempts:
    item_errors = []

    if item.get("prescreen_layer") != "APP_PREFLIGHT":
        item_errors.append(
            "unexpected prescreen_layer"
        )

    if item.get("decision") != "BLOCKED_REQUIRES_CLASS_D":
        item_errors.append(
            "unexpected decision"
        )

    if item.get("required_class") != "D":
        item_errors.append(
            "blocked App preflight does not require Class D"
        )

    if item.get("declared_class") == "D":
        item_errors.append(
            "Class D must not be blocked/escalated by the App preflight"
        )

    if not item.get("rule_ids"):
        item_errors.append(
            "blocked App preflight has no rule IDs"
        )

    forbidden_property_names = {
        "raw_text",
        "matched_text",
        "source_text",
        "direct_text",
        "matched_value",
        "matched_phrase",
    }

    exposed_forbidden = sorted(
        forbidden_property_names
        & set(item.get("property_keys") or [])
    )

    if exposed_forbidden:
        item_errors.append(
            "audit node contains forbidden raw-text properties: "
            + ", ".join(exposed_forbidden)
        )

    if (
        item.get("input_mode") == "DIRECT_TEXT"
        and not item.get("content_sha256")
    ):
        item_errors.append(
            "blocked direct-text App preflight has no content SHA-256"
        )

    if (
        item.get("input_mode") == "DOCUMENTS"
        and item.get("content_sha256")
    ):
        item_errors.append(
            "document metadata preflight unexpectedly stores a content hash"
        )

    audit_validation_rows.append(
        {
            "event_id": item.get("event_id"),
            "declared_class": item.get("declared_class"),
            "input_mode": item.get("input_mode"),
            "rules": len(item.get("rule_ids") or []),
            "documents": len(item.get("document_ids") or []),
            "has_content_sha256": bool(
                item.get("content_sha256")
            ),
            "errors": len(item_errors),
            "error_detail": " | ".join(item_errors),
        }
    )

    errors.extend(
        f"{item.get('event_id')}: {value}"
        for value in item_errors
    )

print(
    "App preflight audit events:",
    len(app_prescreen_attempts),
)

if audit_validation_rows:
    display(
        spark.createDataFrame(
            audit_validation_rows
        )
    )

# COMMAND ----------

if errors:
    print("")
    print("VALIDATION ERRORS")
    for error in errors:
        print(" -", error)

    driver.close()
    raise RuntimeError(
        "Information-class pre-screen routing validation failed."
    )

print("")
print(
    "PASS — INFORMATION-CLASS PRESCREEN FAILS CLOSED WITHOUT DOWNGRADING CLASS D"
)
print("analyses:", len(analyses))
print(
    "app_preflight_audit_events:",
    len(app_prescreen_attempts),
)

driver.close()
