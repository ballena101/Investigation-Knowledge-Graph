# Databricks notebook source
# MAGIC %md
# MAGIC # 28 — Compare one frozen MAIRA snapshot with both IKF models
# MAGIC
# MAGIC Controlled, read-only dual-model checkpoint after notebook 27.
# MAGIC
# MAGIC The notebook sends the same frozen evidence and governed question to
# MAGIC GPT-OSS 20B and Llama 3.3 70B in independent requests. It validates
# MAGIC passage references and exposes temporary comparison views only.
# MAGIC
# MAGIC It creates no table and modifies no Neo4j graph.

# COMMAND ----------

dbutils.widgets.text("analysis_id", "", "Analysis ID")
dbutils.widgets.text(
    "retrieval_snapshot_id",
    "",
    "Retrieval snapshot ID",
)
dbutils.widgets.text("query_id", "Q001", "MAIRA query ID")
dbutils.widgets.text(
    "query_spec_id",
    "",
    "MAIRA query specification ID (optional)",
)
dbutils.widgets.text(
    "maira_src_path",
    "",
    "MAIRA src path (optional)",
)
dbutils.widgets.text(
    "model_a",
    "bdw_analysis_prod.kg_poc.ikf-gpt-oss-20b-poc",
    "GPT-OSS 20B model service",
)
dbutils.widgets.text(
    "model_b",
    "bdw_analysis_prod.kg_poc.ikf-llama-3-3-70b-poc",
    "Llama 3.3 70B model service",
)
dbutils.widgets.text(
    "max_output_tokens",
    "2000",
    "Maximum output tokens per model",
)
dbutils.widgets.text(
    "databricks_openai_base_url",
    "",
    "Databricks OpenAI base URL (optional)",
)

# COMMAND ----------

import hashlib
import importlib.util
import json
import os
import re
import sys
import time

from openai import OpenAI
from pyspark.sql import Row
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
)


PROMPT_VERSION = "IKF_MAIRA_DUAL_MODEL_V0.1"
LOCAL_SNAPSHOT_VIEW = "maira_ikf_retrieval_snapshot"
ANALYSIS_DOCUMENT_TABLE = "bdw_analysis_prod.kg_poc.analysis_document"
MAIRA_DOCUMENT_TABLE = "bdw_analysis_prod.maira.documents"
MAIRA_PASSAGE_TABLE = "bdw_analysis_prod.maira.passages"
QUERY_SPEC_TABLE = "bdw_analysis_prod.maira.query_specifications"
QUERY_CONCEPT_TABLE = "bdw_analysis_prod.maira.query_spec_concepts"
RETRIEVAL_CONTRACT_VERSION = "MAIRA_GOVERNED_LEXICAL_V0.1"

RUN_VIEW = "maira_ikf_dual_model_runs"
CANDIDATE_VIEW = "maira_ikf_dual_model_candidates"
COMPARISON_VIEW = "maira_ikf_dual_model_comparison"

ALLOWED_RELATIONSHIPS = {
    "FOLLOWED_BY",
    "CONTRIBUTED_TO",
    "RESULTED_IN",
    "AFFECTED",
    "SUPPORTS",
}
ALLOWED_EVIDENCE_CLASSES = {
    "DIRECT",
    "NORMALISED",
    "INFERRED",
    "SYNTHESISED",
    "INSUFFICIENT_EVIDENCE",
}
CAUSAL_RELATIONSHIPS = {
    "CONTRIBUTED_TO",
    "RESULTED_IN",
}

analysis_id = dbutils.widgets.get("analysis_id").strip()
retrieval_snapshot_id = dbutils.widgets.get(
    "retrieval_snapshot_id"
).strip()
model_a = dbutils.widgets.get("model_a").strip()
model_b = dbutils.widgets.get("model_b").strip()
requested_query_id = dbutils.widgets.get("query_id").strip().upper()
requested_query_spec_id = dbutils.widgets.get("query_spec_id").strip()
configured_base_url = dbutils.widgets.get(
    "databricks_openai_base_url"
).strip()

try:
    max_output_tokens = int(
        dbutils.widgets.get("max_output_tokens").strip()
    )
except ValueError as exc:
    raise ValueError("max_output_tokens must be an integer.") from exc

is_app_analysis = bool(
    re.fullmatch(r"analysis_[0-9a-f]{32}", analysis_id)
)
is_controlled_bridge_test = bool(
    re.fullmatch(r"ikf_maira_test_[0-9]{3}", analysis_id)
)
if not (is_app_analysis or is_controlled_bridge_test):
    raise ValueError(
        "Enter an IKF App analysis_id or a controlled "
        "ikf_maira_test_<three digits> bridge-test ID."
    )

if not re.fullmatch(r"snapshot_[0-9a-f]{32}", retrieval_snapshot_id):
    raise ValueError("Enter the exact snapshot ID printed by notebook 27.")

if not re.fullmatch(r"Q[0-9]{3}", requested_query_id):
    raise ValueError("Enter a governed MAIRA query ID such as Q001.")

if not model_a or not model_b or model_a == model_b:
    raise ValueError("Enter two different configured model-service identifiers.")

if not 512 <= max_output_tokens <= 8000:
    raise ValueError("max_output_tokens must be between 512 and 8000.")

print("Analysis:", analysis_id)
print("Retrieval snapshot:", retrieval_snapshot_id)
print("Prompt version:", PROMPT_VERSION)
print("Model A:", model_a)
print("Model B:", model_b)

# COMMAND ----------

def resolve_maira_src_path():
    if importlib.util.find_spec("maira") is not None:
        return None

    configured_path = dbutils.widgets.get("maira_src_path").strip()
    current_user = spark.sql(
        "SELECT current_user() AS username"
    ).first()["username"]
    candidates = [
        configured_path,
        f"/Workspace/Users/{current_user}/MAIRA/src",
        f"/Workspace/Users/{current_user}/MAIRA-main/src",
    ]

    checked_paths = []
    for candidate in candidates:
        if not candidate:
            continue
        candidate = candidate.rstrip("/")
        if os.path.isfile(
            os.path.join(candidate, "maira", "__init__.py")
        ):
            src_path = candidate
        elif os.path.isfile(
            os.path.join(candidate, "src", "maira", "__init__.py")
        ):
            src_path = os.path.join(candidate, "src")
        else:
            checked_paths.append(candidate)
            continue

        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        importlib.invalidate_caches()
        if importlib.util.find_spec("maira") is not None:
            return src_path
        checked_paths.append(src_path)

    raise ModuleNotFoundError(
        "The MAIRA package is not installed and no sibling MAIRA/src folder "
        "was found. Checked: " + ", ".join(checked_paths)
    )


def rebuild_verified_snapshot():
    resolved_path = resolve_maira_src_path()

    from maira.integration.ikf_passage_contract import (
        PASSAGE_CONTRACT_VERSION,
    )
    from maira.query.terms import derive_evidence_terms
    from maira.retrieval.lexical import retrieve_candidates

    analysis_documents = (
        spark.table(ANALYSIS_DOCUMENT_TABLE)
        .filter(F.col("analysis_id") == analysis_id)
        .select(
            "analysis_id",
            F.col("document_id").alias("ikf_document_id"),
            F.lower(F.col("sha256")).alias("source_document_sha256"),
        )
    )
    if analysis_documents.count() == 0:
        raise ValueError(
            f"No IKF analysis documents found for {analysis_id}."
        )

    duplicate_inputs = (
        analysis_documents.groupBy("source_document_sha256")
        .count()
        .filter(F.col("count") > 1)
    )
    if duplicate_inputs.count():
        raise ValueError("The IKF analysis contains duplicate document content.")

    maira_documents = spark.table(MAIRA_DOCUMENT_TABLE).select(
        F.col("document_id").alias("maira_document_id"),
        "report_package_id",
        F.lower(F.col("sha256")).alias("source_document_sha256"),
    )
    document_matches = analysis_documents.join(
        maira_documents,
        on="source_document_sha256",
        how="left",
    )
    match_counts = document_matches.groupBy(
        "analysis_id",
        "ikf_document_id",
        "source_document_sha256",
    ).agg(F.countDistinct("maira_document_id").alias("maira_document_matches"))
    if match_counts.filter(F.col("maira_document_matches") != 1).count():
        raise ValueError(
            "Every IKF document must match exactly one MAIRA document by "
            "full SHA-256 before governed retrieval can run."
        )

    maira_passages = spark.table(MAIRA_PASSAGE_TABLE).select(
        F.col("document_id").alias("maira_document_id"),
        "passage_id",
        "passage_number",
        "start_page",
        "end_page",
        "passage_text",
        F.lower(F.col("passage_text_sha256")).alias("text_sha256"),
    )
    bridge = (
        document_matches.filter(F.col("maira_document_id").isNotNull())
        .join(maira_passages, on="maira_document_id", how="inner")
        .select(
            "analysis_id",
            "ikf_document_id",
            "maira_document_id",
            "report_package_id",
            "passage_id",
            "passage_number",
            "start_page",
            "end_page",
            "passage_text",
            "text_sha256",
            "source_document_sha256",
        )
    )
    if bridge.count() == 0:
        raise ValueError("The matched MAIRA documents contain no passages.")
    if bridge.filter(
        F.col("passage_id").isNull()
        | F.col("passage_text").isNull()
        | (F.length(F.trim(F.col("passage_text"))) == 0)
        | (F.sha2(F.col("passage_text"), 256) != F.col("text_sha256"))
    ).count():
        raise ValueError("MAIRA passage integrity validation failed.")

    query_specs = spark.table(QUERY_SPEC_TABLE).filter(
        F.upper(F.col("query_id")) == requested_query_id
    )
    if requested_query_spec_id:
        query_specs = query_specs.filter(
            F.col("query_spec_id") == requested_query_spec_id
        )
    query_spec_rows = query_specs.select(
        "query_spec_id",
        "query_id",
        "query_spec_version",
        "user_query",
        "relationship",
    ).dropDuplicates().collect()
    if len(query_spec_rows) != 1:
        raise ValueError(
            f"Expected one governed specification for {requested_query_id}; "
            f"found {len(query_spec_rows)}. Enter query_spec_id if needed."
        )
    active_query_spec = query_spec_rows[0].asDict()
    active_query_spec_id = active_query_spec["query_spec_id"]

    concept_rows = (
        spark.table(QUERY_CONCEPT_TABLE)
        .filter(F.col("query_spec_id") == active_query_spec_id)
        .select(
            "query_spec_id",
            "component_role",
            "query_token",
            "code_value",
        )
        .collect()
    )
    terms = derive_evidence_terms(
        [row.asDict() for row in concept_rows],
        active_query_spec_id,
    )

    bridge_rows = bridge.orderBy(
        "report_package_id",
        "maira_document_id",
        "passage_number",
    ).collect()
    retrieval_input = [
        {
            "report_package_id": row["report_package_id"],
            "document_id": row["maira_document_id"],
            "passage_id": row["passage_id"],
            "passage_number": row["passage_number"],
            "start_page": row["start_page"],
            "end_page": row["end_page"],
            "passage_text": row["passage_text"],
        }
        for row in bridge_rows
    ]
    retrieval = retrieve_candidates(retrieval_input, terms)
    candidate_package_ids = {
        item["report_package_id"]
        for item in retrieval.package_candidates
    }
    selected_matches = sorted(
        (
            item
            for item in retrieval.passage_matches
            if item["report_package_id"] in candidate_package_ids
        ),
        key=lambda item: (
            item["report_package_id"],
            item["document_id"],
            item["passage_number"],
            item["passage_id"],
        ),
    )
    if not selected_matches:
        raise ValueError(
            "The governed retrieval produced no complete candidate package."
        )

    bridge_by_passage_id = {
        row["passage_id"]: row.asDict()
        for row in bridge_rows
    }
    snapshot_material = "\n".join(
        "|".join(
            (
                item["passage_id"],
                bridge_by_passage_id[item["passage_id"]]["text_sha256"],
            )
        )
        for item in selected_matches
    )
    computed_snapshot_id = "snapshot_" + hashlib.sha256(
        "|".join(
            (
                analysis_id,
                active_query_spec_id,
                PASSAGE_CONTRACT_VERSION,
                RETRIEVAL_CONTRACT_VERSION,
                snapshot_material,
            )
        ).encode("utf-8")
    ).hexdigest()[:32]
    if computed_snapshot_id != retrieval_snapshot_id:
        raise ValueError(
            "The governed data no longer reproduces the requested frozen "
            f"snapshot. Expected {retrieval_snapshot_id}; computed "
            f"{computed_snapshot_id}."
        )

    rebuilt_rows = []
    for item in selected_matches:
        source = bridge_by_passage_id[item["passage_id"]]
        rebuilt_rows.append(
            Row(
                retrieval_snapshot_id=computed_snapshot_id,
                retrieval_contract_version=RETRIEVAL_CONTRACT_VERSION,
                passage_contract_version=PASSAGE_CONTRACT_VERSION,
                analysis_id=analysis_id,
                query_spec_id=active_query_spec_id,
                query_id=requested_query_id,
                report_package_id=source["report_package_id"],
                ikf_document_id=source["ikf_document_id"],
                maira_document_id=source["maira_document_id"],
                passage_id=source["passage_id"],
                passage_order=source["passage_number"],
                page_start=source["start_page"],
                page_end=source["end_page"],
                passage_text=source["passage_text"],
                text_sha256=source["text_sha256"],
                matched_roles=sorted(item["matched_terms"]),
                matched_terms_json=json.dumps(
                    {
                        role: list(values)
                        for role, values in item["matched_terms"].items()
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
        )

    rebuilt_df = spark.createDataFrame(rebuilt_rows)
    print(
        "Snapshot source: deterministically rebuilt and verified from "
        "governed tables"
    )
    print("MAIRA source:", resolved_path or "installed package")
    return rebuilt_df


snapshot_df = None
snapshot_view = None
if spark.catalog.tableExists(LOCAL_SNAPSHOT_VIEW):
    local_candidate = (
        spark.table(LOCAL_SNAPSHOT_VIEW)
        .filter(F.col("analysis_id") == analysis_id)
        .filter(F.col("retrieval_snapshot_id") == retrieval_snapshot_id)
    )
    if local_candidate.limit(1).count():
        snapshot_df = local_candidate
        snapshot_view = LOCAL_SNAPSHOT_VIEW
        print("Snapshot source: notebook-local temporary view")

if snapshot_df is None:
    snapshot_df = rebuild_verified_snapshot()
    snapshot_df.createOrReplaceTempView(LOCAL_SNAPSHOT_VIEW)
    snapshot_view = LOCAL_SNAPSHOT_VIEW

snapshot_rows = snapshot_df.orderBy(
    "report_package_id",
    "maira_document_id",
    "passage_order",
    "passage_id",
).collect()

if not snapshot_rows:
    raise ValueError(
        "The selected temporary view does not contain the requested analysis "
        "and retrieval snapshot. Rerun notebook 27 with the same inputs."
    )

passage_ids = [row["passage_id"] for row in snapshot_rows]
if len(passage_ids) != len(set(passage_ids)):
    raise ValueError("The frozen snapshot contains duplicate passage IDs.")

invalid_hashes = snapshot_df.filter(
    F.sha2(F.col("passage_text"), 256) != F.lower(F.col("text_sha256"))
)
if invalid_hashes.count():
    display(invalid_hashes)
    raise ValueError("Frozen snapshot passage-text integrity validation failed.")

query_spec_ids = {
    row["query_spec_id"]
    for row in snapshot_rows
}
query_ids = {
    row["query_id"]
    for row in snapshot_rows
}
if len(query_spec_ids) != 1 or len(query_ids) != 1:
    raise ValueError("The snapshot must contain exactly one governed query.")

query_spec_id = next(iter(query_spec_ids))
query_id = next(iter(query_ids))

query_spec_rows = (
    spark.table(QUERY_SPEC_TABLE)
    .filter(F.col("query_spec_id") == query_spec_id)
    .select(
        "query_spec_id",
        "query_id",
        "query_spec_version",
        "user_query",
        "relationship",
    )
    .dropDuplicates()
    .collect()
)
if len(query_spec_rows) != 1:
    raise ValueError(
        "The frozen snapshot query specification could not be resolved "
        "uniquely from the governed MAIRA table."
    )

query_spec = query_spec_rows[0].asDict()
if str(query_spec["query_id"]).upper() != str(query_id).upper():
    raise ValueError("Snapshot/query-spec query ID mismatch.")

print("Snapshot view:", snapshot_view)
print("Frozen passages:", len(snapshot_rows))
print("Query:", query_id)
print("Question:", query_spec["user_query"])
print("Requested relationship:", query_spec["relationship"])

# COMMAND ----------

evidence_passages = [
    {
        "passage_id": row["passage_id"],
        "document_id": row["maira_document_id"],
        "report_package_id": row["report_package_id"],
        "passage_order": int(row["passage_order"]),
        "page_start": row["page_start"],
        "page_end": row["page_end"],
        "text_sha256": row["text_sha256"],
        "passage_text": row["passage_text"],
    }
    for row in snapshot_rows
]

frozen_payload = {
    "analysis_id": analysis_id,
    "retrieval_snapshot_id": retrieval_snapshot_id,
    "query_spec_id": query_spec_id,
    "query_spec_version": query_spec["query_spec_version"],
    "query_id": query_id,
    "question": query_spec["user_query"],
    "requested_relationship": query_spec["relationship"],
    "evidence_passages": evidence_passages,
}
frozen_payload_json = json.dumps(
    frozen_payload,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
)

instructions = """
You are an evidence-bounded extraction component for a maritime investigation
knowledge graph. Produce candidate relationships for human review.

Rules:
1. Use only the supplied frozen evidence passages. Do not use outside knowledge.
2. Do not convert chronology, proximity, correlation or sequence into causality.
3. Use only these relationship labels: FOLLOWED_BY, CONTRIBUTED_TO, RESULTED_IN,
   AFFECTED, SUPPORTS.
4. Every candidate must cite one or more supplied passage_id values.
5. evidence_quote must be copied verbatim from one cited passage.
6. If the requested relationship is not supported, return an empty
   candidate_relationships array and explain the uncertainty in answer_summary.
7. Return exactly one JSON object with this schema and no Markdown:
{
  "answer_summary": "concise evidence-bounded answer",
  "candidate_relationships": [
    {
      "source_label": "source entity or factor",
      "relationship": "one allowed label",
      "target_label": "target entity, event or outcome",
      "evidence_passage_ids": ["passage id"],
      "evidence_quote": "exact quotation from a cited passage",
      "evidence_class": "DIRECT|NORMALISED|INFERRED|SYNTHESISED|INSUFFICIENT_EVIDENCE",
      "explanation": "why the cited evidence supports this direction and label"
    }
  ],
  "uncertainties": ["material uncertainty"]
}
""".strip()

prompt = (
    instructions
    + "\n\nPROMPT_VERSION: "
    + PROMPT_VERSION
    + "\nFROZEN_INPUT_JSON:\n"
    + frozen_payload_json
)
prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

print("Identical prompt SHA-256:", prompt_sha256)

# COMMAND ----------

def strip_code_fences(value):
    text = (value or "").strip()
    fence = chr(96) * 3
    if text.startswith(fence):
        text = re.sub(
            r"^.{3}(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\s*.{3}$", "", text)
    return text.strip()


def integer_value(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def usage_value(usage, field):
    if usage is None:
        return 0
    if isinstance(usage, dict):
        return integer_value(usage.get(field))
    return integer_value(getattr(usage, field, 0))


def invoke_model(model_key, configured_model):
    started = time.perf_counter()

    if model_key == "MODEL_A":
        response = client.responses.create(
            model=configured_model,
            max_output_tokens=max_output_tokens,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt,
                        }
                    ],
                }
            ],
        )
        execution_status = str(
            getattr(response, "status", "") or ""
        )
        if execution_status.lower() != "completed":
            detail = getattr(response, "incomplete_details", None)
            raise RuntimeError(
                f"{model_key} did not complete: status={execution_status}; "
                f"details={detail}"
            )
        response_text = response.output_text
        underlying_model = str(
            getattr(response, "model", "") or ""
        )
        usage = getattr(response, "usage", None)
        input_tokens = usage_value(usage, "input_tokens")
        output_tokens = usage_value(usage, "output_tokens")
        total_tokens = usage_value(usage, "total_tokens")
        api_method = "responses.create"
    else:
        response = client.chat.completions.create(
            model=configured_model,
            max_tokens=max_output_tokens,
            temperature=0.0,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )
        choice = response.choices[0]
        execution_status = str(
            getattr(choice, "finish_reason", "") or ""
        )
        if execution_status.lower() not in {"stop", "completed"}:
            raise RuntimeError(
                f"{model_key} did not complete: finish_reason="
                f"{execution_status}"
            )
        response_text = choice.message.content
        underlying_model = str(
            getattr(response, "model", "") or ""
        )
        usage = getattr(response, "usage", None)
        input_tokens = usage_value(usage, "prompt_tokens")
        output_tokens = usage_value(usage, "completion_tokens")
        total_tokens = usage_value(usage, "total_tokens")
        api_method = "chat.completions.create"

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    parsed = json.loads(strip_code_fences(response_text))
    if not isinstance(parsed, dict):
        raise ValueError(f"{model_key} response must be one JSON object.")

    return {
        "model_key": model_key,
        "configured_model": configured_model,
        "underlying_model": underlying_model,
        "api_method": api_method,
        "execution_status": execution_status,
        "latency_ms": elapsed_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "response": parsed,
    }


context = (
    dbutils.notebook.entry_point
    .getDbutils()
    .notebook()
    .getContext()
)
workspace_url = context.apiUrl().get().rstrip("/")
base_url = configured_base_url or (
    workspace_url + "/ai-gateway/openai/v1"
)

databricks_token = os.environ.get("DATABRICKS_TOKEN", "").strip()
if not databricks_token:
    try:
        databricks_token = dbutils.secrets.get(
            scope="kg-poc-app",
            key="databricks_model_token",
        )
    except Exception:
        try:
            databricks_token = context.apiToken().get()
        except Exception as exc:
            raise RuntimeError(
                "No Databricks model token is available. Configure the "
                "DATABRICKS_TOKEN environment variable or the "
                "kg-poc-app/databricks_model_token secret."
            ) from exc

client = OpenAI(
    api_key=databricks_token,
    base_url=base_url,
)
print("Databricks OpenAI base URL:", base_url)

model_definitions = [
    ("MODEL_A", model_a),
    ("MODEL_B", model_b),
]

model_results = []
model_failures = []

for model_key, configured_model in model_definitions:
    print("")
    print("Invoking", model_key, "independently...")
    try:
        result = invoke_model(model_key, configured_model)
        model_results.append(result)
        print(
            model_key,
            "completed in",
            result["latency_ms"],
            "ms",
        )
    except Exception as exc:
        model_failures.append(
            {
                "model_key": model_key,
                "configured_model": configured_model,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        print(model_key, "FAILED:", model_failures[-1]["error"])

if model_failures:
    display(spark.createDataFrame([Row(**item) for item in model_failures]))
    raise RuntimeError(
        "Dual-model execution did not complete. No comparison PASS was issued."
    )

# COMMAND ----------

passage_text_by_id = {
    row["passage_id"]: row["passage_text"]
    for row in snapshot_rows
}


def normalise_whitespace(value):
    return " ".join(str(value or "").split())


run_rows = []
candidate_rows = []

for result in model_results:
    response = result["response"]
    raw_candidates = response.get("candidate_relationships", [])
    root_errors = []

    if not isinstance(response.get("answer_summary"), str):
        root_errors.append("answer_summary must be a string")
    if not isinstance(raw_candidates, list):
        root_errors.append("candidate_relationships must be an array")
        raw_candidates = []
    if not isinstance(response.get("uncertainties", []), list):
        root_errors.append("uncertainties must be an array")

    candidate_error_count = 0
    for position, item in enumerate(raw_candidates, start=1):
        errors = []
        if not isinstance(item, dict):
            errors.append("candidate must be an object")
            item = {}

        relationship = str(item.get("relationship") or "").upper()
        evidence_class = str(item.get("evidence_class") or "").upper()
        cited_ids = item.get("evidence_passage_ids") or []
        if not isinstance(cited_ids, list):
            cited_ids = []
            errors.append("evidence_passage_ids must be an array")
        cited_ids = [str(value) for value in cited_ids]

        if relationship not in ALLOWED_RELATIONSHIPS:
            errors.append("relationship label is not allowed")
        if evidence_class not in ALLOWED_EVIDENCE_CLASSES:
            errors.append("evidence_class is not allowed")
        if not cited_ids:
            errors.append("at least one evidence passage is required")

        unknown_ids = sorted(set(cited_ids) - set(passage_text_by_id))
        reference_valid = not unknown_ids and bool(cited_ids)
        if unknown_ids:
            errors.append("unknown evidence passage IDs: " + ", ".join(unknown_ids))

        quote = str(item.get("evidence_quote") or "")
        normalised_quote = normalise_whitespace(quote)
        quote_exact = bool(normalised_quote) and any(
            normalised_quote in normalise_whitespace(
                passage_text_by_id[passage_id]
            )
            for passage_id in cited_ids
            if passage_id in passage_text_by_id
        )
        if not quote_exact:
            errors.append("evidence_quote is not verbatim in a cited passage")

        source_label = str(item.get("source_label") or "").strip()
        target_label = str(item.get("target_label") or "").strip()
        if not source_label:
            errors.append("source_label is required")
        if not target_label:
            errors.append("target_label is required")

        schema_valid = not errors
        if not schema_valid:
            candidate_error_count += 1

        signature_material = "|".join(
            (
                normalise_whitespace(source_label).casefold(),
                relationship,
                normalise_whitespace(target_label).casefold(),
            )
        )
        candidate_signature = hashlib.sha256(
            signature_material.encode("utf-8")
        ).hexdigest()[:24]

        candidate_rows.append(
            {
                "retrieval_snapshot_id": retrieval_snapshot_id,
                "analysis_id": analysis_id,
                "prompt_version": PROMPT_VERSION,
                "prompt_sha256": prompt_sha256,
                "model_key": result["model_key"],
                "configured_model": result["configured_model"],
                "candidate_position": position,
                "candidate_signature": candidate_signature,
                "source_label": source_label,
                "relationship": relationship,
                "target_label": target_label,
                "evidence_passage_ids": cited_ids,
                "evidence_quote": quote,
                "evidence_class": evidence_class,
                "explanation": str(item.get("explanation") or ""),
                "evidence_reference_valid": reference_valid,
                "evidence_quote_exact": quote_exact,
                "requires_causal_review": relationship in CAUSAL_RELATIONSHIPS,
                "schema_valid": schema_valid,
                "validation_errors": errors,
            }
        )

    run_schema_valid = not root_errors and candidate_error_count == 0
    run_rows.append(
        {
            "retrieval_snapshot_id": retrieval_snapshot_id,
            "analysis_id": analysis_id,
            "query_spec_id": query_spec_id,
            "query_id": query_id,
            "prompt_version": PROMPT_VERSION,
            "prompt_sha256": prompt_sha256,
            "frozen_passage_count": len(snapshot_rows),
            "model_key": result["model_key"],
            "configured_model": result["configured_model"],
            "underlying_model": result["underlying_model"],
            "api_method": result["api_method"],
            "execution_status": result["execution_status"],
            "latency_ms": result["latency_ms"],
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "total_tokens": result["total_tokens"],
            "candidate_count": len(raw_candidates),
            "candidate_validation_error_count": candidate_error_count,
            "schema_valid": run_schema_valid,
            "validation_errors": root_errors,
            "answer_summary": str(response.get("answer_summary") or ""),
            "uncertainties_json": json.dumps(
                response.get("uncertainties", []),
                ensure_ascii=False,
                sort_keys=True,
            ),
            "response_json": json.dumps(
                response,
                ensure_ascii=False,
                sort_keys=True,
            ),
        }
    )

# COMMAND ----------

run_schema = StructType(
    [
        StructField("retrieval_snapshot_id", StringType(), False),
        StructField("analysis_id", StringType(), False),
        StructField("query_spec_id", StringType(), False),
        StructField("query_id", StringType(), False),
        StructField("prompt_version", StringType(), False),
        StructField("prompt_sha256", StringType(), False),
        StructField("frozen_passage_count", IntegerType(), False),
        StructField("model_key", StringType(), False),
        StructField("configured_model", StringType(), False),
        StructField("underlying_model", StringType(), True),
        StructField("api_method", StringType(), False),
        StructField("execution_status", StringType(), False),
        StructField("latency_ms", LongType(), False),
        StructField("input_tokens", IntegerType(), False),
        StructField("output_tokens", IntegerType(), False),
        StructField("total_tokens", IntegerType(), False),
        StructField("candidate_count", IntegerType(), False),
        StructField("candidate_validation_error_count", IntegerType(), False),
        StructField("schema_valid", BooleanType(), False),
        StructField("validation_errors", ArrayType(StringType()), False),
        StructField("answer_summary", StringType(), False),
        StructField("uncertainties_json", StringType(), False),
        StructField("response_json", StringType(), False),
    ]
)

candidate_schema = StructType(
    [
        StructField("retrieval_snapshot_id", StringType(), False),
        StructField("analysis_id", StringType(), False),
        StructField("prompt_version", StringType(), False),
        StructField("prompt_sha256", StringType(), False),
        StructField("model_key", StringType(), False),
        StructField("configured_model", StringType(), False),
        StructField("candidate_position", IntegerType(), False),
        StructField("candidate_signature", StringType(), False),
        StructField("source_label", StringType(), False),
        StructField("relationship", StringType(), False),
        StructField("target_label", StringType(), False),
        StructField("evidence_passage_ids", ArrayType(StringType()), False),
        StructField("evidence_quote", StringType(), False),
        StructField("evidence_class", StringType(), False),
        StructField("explanation", StringType(), False),
        StructField("evidence_reference_valid", BooleanType(), False),
        StructField("evidence_quote_exact", BooleanType(), False),
        StructField("requires_causal_review", BooleanType(), False),
        StructField("schema_valid", BooleanType(), False),
        StructField("validation_errors", ArrayType(StringType()), False),
    ]
)

run_df = spark.createDataFrame(
    [Row(**item) for item in run_rows],
    schema=run_schema,
)
candidate_df = spark.createDataFrame(
    [Row(**item) for item in candidate_rows],
    schema=candidate_schema,
)

run_df.createOrReplaceTempView(RUN_VIEW)
candidate_df.createOrReplaceTempView(CANDIDATE_VIEW)

model_a_signatures = {
    item["candidate_signature"]
    for item in candidate_rows
    if item["model_key"] == "MODEL_A"
}
model_b_signatures = {
    item["candidate_signature"]
    for item in candidate_rows
    if item["model_key"] == "MODEL_B"
}

comparison_rows = [
    Row(
        retrieval_snapshot_id=retrieval_snapshot_id,
        analysis_id=analysis_id,
        candidate_signature=signature,
        in_model_a=signature in model_a_signatures,
        in_model_b=signature in model_b_signatures,
        exact_label_agreement=(
            signature in model_a_signatures
            and signature in model_b_signatures
        ),
    )
    for signature in sorted(model_a_signatures | model_b_signatures)
]

comparison_schema = StructType(
    [
        StructField("retrieval_snapshot_id", StringType(), False),
        StructField("analysis_id", StringType(), False),
        StructField("candidate_signature", StringType(), False),
        StructField("in_model_a", BooleanType(), False),
        StructField("in_model_b", BooleanType(), False),
        StructField("exact_label_agreement", BooleanType(), False),
    ]
)
comparison_df = spark.createDataFrame(
    comparison_rows,
    schema=comparison_schema,
)
comparison_df.createOrReplaceTempView(COMPARISON_VIEW)

# COMMAND ----------

display(
    run_df.select(
        "model_key",
        "configured_model",
        "underlying_model",
        "api_method",
        "execution_status",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "candidate_count",
        "candidate_validation_error_count",
        "schema_valid",
        "answer_summary",
    ).orderBy("model_key")
)

display(
    candidate_df.select(
        "model_key",
        "candidate_position",
        "source_label",
        "relationship",
        "target_label",
        "evidence_passage_ids",
        "evidence_reference_valid",
        "evidence_quote_exact",
        "requires_causal_review",
        "schema_valid",
        "validation_errors",
    ).orderBy("model_key", "candidate_position")
)

display(comparison_df.orderBy("candidate_signature"))

print("")
print("Frozen passages sent to each model:", len(snapshot_rows))
print("Identical prompt SHA-256:", prompt_sha256)
print("Exact candidate-label agreements:", len(model_a_signatures & model_b_signatures))
print("Candidates only from MODEL_A:", len(model_a_signatures - model_b_signatures))
print("Candidates only from MODEL_B:", len(model_b_signatures - model_a_signatures))
print("Temporary run view:", RUN_VIEW)
print("Temporary candidate view:", CANDIDATE_VIEW)
print("Temporary comparison view:", COMPARISON_VIEW)
print("PASS — MAIRA DUAL-MODEL EXECUTION CHECKPOINT")
print(
    "Human review is still required; PASS confirms controlled execution and "
    "provenance checks, not model accuracy."
)
