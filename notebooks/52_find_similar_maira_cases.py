# Databricks notebook source
# MAGIC %md
# MAGIC # 52 — Find similar MAIRA investigation cases
# MAGIC
# MAGIC Deterministic, explainable similar-case discovery across the processed MAIRA
# MAGIC `INVESTIGATION / MAIN_REPORT` corpus.
# MAGIC
# MAGIC V0.2 keeps MAIRA lexical retrieval as the first-stage candidate mechanism and
# MAGIC adds deterministic graph-concept weighting at report-package ranking time:
# MAGIC
# MAGIC - ContributingFactor = 5
# MAGIC - SafetyIssue = 4
# MAGIC - Event = 3
# MAGIC - Finding = 2
# MAGIC - System = 1
# MAGIC
# MAGIC Whole multi-word concept matches receive an additional boost. Vessel/Actor/Claim
# MAGIC identity is excluded, the current report package is excluded, and exact matched
# MAGIC passages/pages remain the provenance shown to the investigator.
# MAGIC
# MAGIC No LLM, embedding or vector-similarity call is made.

# COMMAND ----------

dbutils.widgets.text("analysis_id", "", "Analysis ID")

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1

# COMMAND ----------

import hashlib
import json
import os
import re
import sys

from neo4j import GraphDatabase
from pyspark.sql import functions as F

analysis_id = dbutils.widgets.get("analysis_id").strip()
if not re.fullmatch(r"analysis_[0-9a-f]{32}", analysis_id):
    raise ValueError("Enter a valid analysis_id.")

SIMILAR_CASE_VERSION = "IKF_SIMILAR_MAIRA_CASES_V0.2"
RANKING_METHOD = "WEIGHTED_GRAPH_CONCEPTS_V0.2"
MAX_CORPUS_PASSAGES = 5000
MAX_CORPUS_CHARACTERS = 30_000_000
MAX_RETRIEVED_PASSAGES = 120
MAX_RETRIEVED_CHARACTERS = 180_000
MAX_CANDIDATES = 5
MAX_EVIDENCE_PASSAGES_PER_CANDIDATE = 4
MAX_FOCUS_CONCEPTS = 20

KIND_WEIGHT = {
    "ContributingFactor": 5,
    "SafetyIssue": 4,
    "Event": 3,
    "Finding": 2,
    "System": 1,
}

STOP_TERMS = {
    "and", "the", "for", "from", "with", "that", "this", "into", "was",
    "were", "are", "has", "had", "have", "after", "before", "during",
    "vessel", "ship", "event", "finding", "factor", "safety", "system",
}


def normalize_text(value):
    return " ".join(
        re.sub(r"[^\w]+", " ", str(value or "").casefold(), flags=re.UNICODE).split()
    )


def concept_terms(label):
    return tuple(
        token
        for token in normalize_text(label).split()
        if len(token) >= 3 and token not in STOP_TERMS
    )


# COMMAND ----------

NEO4J_URI = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_uri")
NEO4J_USERNAME = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_username")
NEO4J_PASSWORD = dbutils.secrets.get(scope="kg-poc-app", key="neo4j_password")

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
)
driver.verify_connectivity()

# COMMAND ----------

# Import the governed deterministic retrieval implementation owned by MAIRA.
current_notebook_path = (
    dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
)
workspace_notebook_path = (
    "/Workspace" + current_notebook_path
    if current_notebook_path.startswith("/Users/")
    else current_notebook_path
)
ikf_repo_root = workspace_notebook_path.rsplit("/notebooks/", 1)[0]
workspace_user_root = ikf_repo_root.rsplit("/", 1)[0]

maira_imported = False
for candidate_name in ("MAIRA", "MAIRA-main"):
    candidate_src = os.path.join(workspace_user_root, candidate_name, "src")
    if not os.path.isdir(candidate_src):
        continue
    if candidate_src not in sys.path:
        sys.path.insert(0, candidate_src)
    try:
        from maira.retrieval import retrieve_free_text
        maira_imported = True
        break
    except ModuleNotFoundError:
        continue

if not maira_imported:
    driver.close()
    raise RuntimeError(
        "The MAIRA deterministic retrieval package is not importable from the current "
        "workspace Git folders."
    )

# COMMAND ----------

with driver.session() as session:
    meta_record = session.run(
        """
        MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
        OPTIONAL MATCH (a)-[:HAS_SOURCE]->(d:SourceDocument)
        WITH a, collect(DISTINCT properties(d)["maira_report_package_id"]) AS package_ids
        RETURN
            a.analysis_title AS analysis_title,
            a.status AS status,
            properties(a)["information_class"] AS information_class,
            [x IN package_ids WHERE x IS NOT NULL] AS current_package_ids
        """,
        analysis_id=analysis_id,
    ).single()

if meta_record is None:
    driver.close()
    raise ValueError(f"AnalysisGroup not found: {analysis_id}")

meta = meta_record.data()
if meta.get("status") != "COMPLETED":
    driver.close()
    raise ValueError("Similar-case discovery requires a completed analysis.")

# Similarity is concept-based, never vessel/actor identity based.
with driver.session() as session:
    concept_rows = [
        record.data()
        for record in session.run(
            """
            MATCH (n:KGNode {analysis_id: $analysis_id})
            WHERE n.node_kind IN [
                'Event', 'ContributingFactor', 'Finding', 'SafetyIssue', 'System'
            ]
            RETURN n.node_id AS node_id, n.node_kind AS node_kind, n.label AS label
            ORDER BY
                CASE n.node_kind
                    WHEN 'ContributingFactor' THEN 1
                    WHEN 'SafetyIssue' THEN 2
                    WHEN 'Event' THEN 3
                    WHEN 'Finding' THEN 4
                    WHEN 'System' THEN 5
                    ELSE 9
                END,
                n.label
            """,
            analysis_id=analysis_id,
        )
    ]

focus_concepts = []
seen_focus = set()
for row in concept_rows:
    label = str(row.get("label") or "").strip()
    normalized = normalize_text(label)
    if not normalized or normalized == "subject vessel" or normalized in seen_focus:
        continue
    seen_focus.add(normalized)
    focus_concepts.append(
        {
            "label": label,
            "normalized_label": normalized,
            "node_kind": row.get("node_kind") or "Other",
            "weight": KIND_WEIGHT.get(row.get("node_kind"), 1),
        }
    )

focus_concepts = focus_concepts[:MAX_FOCUS_CONCEPTS]
if not focus_concepts:
    driver.close()
    raise ValueError(
        "No suitable event/factor/finding/system concepts are available for "
        "deterministic similar-case retrieval."
    )

focus_labels = [item["label"] for item in focus_concepts]
focus_query = " ; ".join(focus_labels)

term_weights = {}
for concept in focus_concepts:
    for term in concept_terms(concept["label"]):
        term_weights[term] = max(term_weights.get(term, 0), concept["weight"])

print("Analysis:", analysis_id)
print("Weighted focus concepts:", len(focus_concepts))
for concept in focus_concepts:
    print(" -", concept["node_kind"], "x", concept["weight"], "|", concept["label"])

# COMMAND ----------

docs = (
    spark.table("bdw_analysis_prod.maira.documents")
    .filter(F.col("corpus_type") == "INVESTIGATION")
    .filter(F.col("document_role") == "MAIN_REPORT")
    .select(
        "document_id",
        "report_package_id",
        "report_title",
        "vessel_name",
        "source_filename",
        "publication_date",
        "investigation_body",
    )
)

all_passages = (
    spark.table("bdw_analysis_prod.maira.passages")
    .join(
        docs.select("document_id", "report_package_id"),
        on=["document_id", "report_package_id"],
        how="inner",
    )
    .select(
        "report_package_id",
        "document_id",
        "passage_id",
        "passage_number",
        "start_page",
        "end_page",
        "passage_text",
    )
)

registered_main_reports = docs.select("document_id").distinct().count()
query_ready_main_reports = all_passages.select("document_id").distinct().count()
coverage_gap = max(registered_main_reports - query_ready_main_reports, 0)

current_package_ids = set(meta.get("current_package_ids") or [])
passages = all_passages
if current_package_ids:
    passages = passages.filter(
        ~F.col("report_package_id").isin(sorted(current_package_ids))
    )

passages = passages.orderBy("report_package_id", "document_id", "passage_number")
passage_rows = [row.asDict(recursive=True) for row in passages.collect()]
corpus_characters = sum(len(row.get("passage_text") or "") for row in passage_rows)

if len(passage_rows) > MAX_CORPUS_PASSAGES or corpus_characters > MAX_CORPUS_CHARACTERS:
    driver.close()
    raise RuntimeError(
        "The current MAIRA corpus exceeds the bounded PoC similar-case retrieval limit. "
        "Move this method to distributed retrieval before scaling further. "
        f"passages={len(passage_rows)}; chars={corpus_characters}"
    )

print(
    "MAIRA MAIN_REPORT coverage:",
    f"{query_ready_main_reports}/{registered_main_reports}",
    "query-ready",
)
print("Candidate MAIRA passages after current-case exclusion:", len(passage_rows))

# COMMAND ----------

retrieval = retrieve_free_text(
    passage_rows,
    focus_query,
    max_passages=MAX_RETRIEVED_PASSAGES,
    max_characters=MAX_RETRIEVED_CHARACTERS,
)
retrieval_method = retrieval.method + "+" + RANKING_METHOD

print("Retrieval method:", retrieval_method)
print("Candidate passage matches:", retrieval.candidate_count)
print("Selected passage matches:", retrieval.selected_count)

# COMMAND ----------

package_accumulator = {}
for hit in retrieval.hits:
    package_id = hit.report_package_id
    if not package_id:
        continue

    normalized_passage = normalize_text(hit.passage_text)
    matched_concepts = [
        concept
        for concept in focus_concepts
        if concept["normalized_label"]
        and concept["normalized_label"] in normalized_passage
    ]
    matched_concept_labels = {item["label"] for item in matched_concepts}
    matched_concept_weight = sum(item["weight"] for item in matched_concepts)
    weighted_term_score = sum(
        term_weights.get(term, 1)
        for term in hit.matched_query_terms
    )
    weighted_hit_score = (
        int(hit.lexical_score)
        + (25 * weighted_term_score)
        + (40 * matched_concept_weight)
    )

    package = package_accumulator.setdefault(
        package_id,
        {
            "report_package_id": package_id,
            "total_score": 0,
            "max_passage_score": 0,
            "weighted_score": 0,
            "matched_concept_weight": 0,
            "matched_concepts": set(),
            "matched_query_terms": set(),
            "matched_expansion_terms": set(),
            "hits": [],
        },
    )
    package["total_score"] += int(hit.lexical_score)
    package["max_passage_score"] = max(
        package["max_passage_score"], int(hit.lexical_score)
    )
    package["weighted_score"] += weighted_hit_score
    package["matched_concept_weight"] += matched_concept_weight
    package["matched_concepts"].update(matched_concept_labels)
    package["matched_query_terms"].update(hit.matched_query_terms)
    package["matched_expansion_terms"].update(hit.matched_expansion_terms)
    package["hits"].append(hit)

ranked_packages = sorted(
    package_accumulator.values(),
    key=lambda item: (
        -item["matched_concept_weight"],
        -len(item["matched_concepts"]),
        -item["weighted_score"],
        -len(item["matched_query_terms"]),
        -item["total_score"],
        -item["max_passage_score"],
        item["report_package_id"],
    ),
)[:MAX_CANDIDATES]

# COMMAND ----------

metadata_by_package = {
    row["report_package_id"]: row.asDict(recursive=True)
    for row in docs.orderBy("report_package_id", "document_id").collect()
}

candidate_rows = []
for rank, package in enumerate(ranked_packages, start=1):
    metadata = metadata_by_package.get(package["report_package_id"], {})
    evidence_hits = sorted(
        package["hits"],
        key=lambda hit: (
            -hit.lexical_score,
            hit.document_id,
            hit.passage_number if hit.passage_number is not None else 10**12,
            hit.passage_id,
        ),
    )[:MAX_EVIDENCE_PASSAGES_PER_CANDIDATE]

    evidence_passage_ids = [hit.passage_id for hit in evidence_hits]
    evidence_references = []
    evidence_locations = []
    filename = (
        metadata.get("source_filename")
        or metadata.get("report_title")
        or package["report_package_id"]
    )

    for hit in evidence_hits:
        if hit.start_page is None:
            page_ref = "page unknown"
        elif hit.end_page is None or hit.end_page == hit.start_page:
            page_ref = f"p. {hit.start_page}"
        else:
            page_ref = f"pp. {hit.start_page}–{hit.end_page}"
        evidence_references.append(f"{filename} · {page_ref}")
        evidence_locations.append(
            hit.document_id
            + "|"
            + ("" if hit.start_page is None else str(hit.start_page))
            + "|"
            + ("" if hit.end_page is None else str(hit.end_page))
        )

    candidate_id = "similar_case_" + hashlib.sha256(
        (analysis_id + "|" + package["report_package_id"] + "|" + SIMILAR_CASE_VERSION).encode(
            "utf-8"
        )
    ).hexdigest()[:24]

    candidate_rows.append(
        {
            "candidate_id": candidate_id,
            "rank": rank,
            "report_package_id": package["report_package_id"],
            "report_title": metadata.get("report_title"),
            "vessel_name": metadata.get("vessel_name"),
            "source_filename": metadata.get("source_filename"),
            "publication_date": (
                str(metadata.get("publication_date"))
                if metadata.get("publication_date") is not None
                else None
            ),
            "investigation_body": metadata.get("investigation_body"),
            "matched_query_terms": sorted(package["matched_query_terms"]),
            "matched_expansion_terms": sorted(package["matched_expansion_terms"]),
            "matched_concepts": sorted(package["matched_concepts"]),
            "weighted_score": int(package["weighted_score"]),
            "total_score": int(package["total_score"]),
            "max_passage_score": int(package["max_passage_score"]),
            "evidence_passage_ids": evidence_passage_ids,
            "evidence_references": evidence_references,
            "evidence_locations": evidence_locations,
        }
    )

snapshot_payload = {
    "analysis_id": analysis_id,
    "version": SIMILAR_CASE_VERSION,
    "retrieval_method": retrieval_method,
    "focus_concepts": focus_concepts,
    "term_weights": term_weights,
    "current_package_ids": sorted(current_package_ids),
    "maira_registered_main_reports": registered_main_reports,
    "maira_query_ready_main_reports": query_ready_main_reports,
    "candidate_package_ids": [row["report_package_id"] for row in candidate_rows],
    "candidate_passage_ids": [
        passage_id
        for row in candidate_rows
        for passage_id in row["evidence_passage_ids"]
    ],
}

snapshot_id = "similar_snapshot_" + hashlib.sha256(
    json.dumps(snapshot_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()[:32]

# COMMAND ----------

with driver.session() as session:
    session.run(
        """
        CREATE CONSTRAINT similar_case_run_id_unique IF NOT EXISTS
        FOR (r:SimilarCaseRun) REQUIRE r.similar_case_run_id IS UNIQUE
        """
    ).consume()
    session.run(
        """
        CREATE CONSTRAINT similar_case_candidate_id_unique IF NOT EXISTS
        FOR (c:SimilarCaseCandidate) REQUIRE c.candidate_id IS UNIQUE
        """
    ).consume()

    run_id = "similar_run_" + hashlib.sha256(
        (analysis_id + "|" + snapshot_id).encode("utf-8")
    ).hexdigest()[:24]

    session.run(
        """
        MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
        MERGE (run:SimilarCaseRun {similar_case_run_id: $run_id})
        ON CREATE SET run.created_at = datetime()
        SET
            run.analysis_id = $analysis_id,
            run.version = $version,
            run.retrieval_method = $retrieval_method,
            run.retrieval_snapshot_id = $snapshot_id,
            run.focus_labels = $focus_labels,
            run.focus_concepts_json = $focus_concepts_json,
            run.current_package_ids = $current_package_ids,
            run.maira_registered_main_reports = $registered_main_reports,
            run.maira_query_ready_main_reports = $query_ready_main_reports,
            run.maira_coverage_gap = $coverage_gap,
            run.candidate_count = $candidate_count,
            run.status = 'COMPLETED',
            run.updated_at = datetime()
        MERGE (a)-[:HAS_SIMILAR_CASE_RUN]->(run)
        """,
        analysis_id=analysis_id,
        run_id=run_id,
        version=SIMILAR_CASE_VERSION,
        retrieval_method=retrieval_method,
        snapshot_id=snapshot_id,
        focus_labels=focus_labels,
        focus_concepts_json=json.dumps(focus_concepts, ensure_ascii=False),
        current_package_ids=sorted(current_package_ids),
        registered_main_reports=registered_main_reports,
        query_ready_main_reports=query_ready_main_reports,
        coverage_gap=coverage_gap,
        candidate_count=len(candidate_rows),
    ).consume()

    for candidate in candidate_rows:
        session.run(
            """
            MATCH (run:SimilarCaseRun {similar_case_run_id: $run_id})
            MERGE (c:SimilarCaseCandidate {candidate_id: $candidate_id})
            ON CREATE SET c.created_at = datetime()
            SET
                c.analysis_id = $analysis_id,
                c.rank = $rank,
                c.report_package_id = $report_package_id,
                c.report_title = $report_title,
                c.vessel_name = $vessel_name,
                c.source_filename = $source_filename,
                c.publication_date = $publication_date,
                c.investigation_body = $investigation_body,
                c.matched_query_terms = $matched_query_terms,
                c.matched_expansion_terms = $matched_expansion_terms,
                c.matched_concepts = $matched_concepts,
                c.weighted_score = $weighted_score,
                c.total_score = $total_score,
                c.max_passage_score = $max_passage_score,
                c.evidence_passage_ids = $evidence_passage_ids,
                c.evidence_references = $evidence_references,
                c.evidence_locations = $evidence_locations,
                c.retrieval_method = $retrieval_method,
                c.retrieval_snapshot_id = $snapshot_id,
                c.updated_at = datetime()
            MERGE (run)-[:HAS_SIMILAR_CASE_CANDIDATE]->(c)
            """,
            run_id=run_id,
            analysis_id=analysis_id,
            retrieval_method=retrieval_method,
            snapshot_id=snapshot_id,
            **candidate,
        ).consume()

print("")
print("SIMILAR MAIRA CASE RETRIEVAL COMPLETE")
print("run_id:", run_id)
print("snapshot_id:", snapshot_id)
print(
    "MAIRA coverage:",
    f"{query_ready_main_reports}/{registered_main_reports}",
    "query-ready MAIN_REPORT documents",
)
print("candidates:", len(candidate_rows))
for candidate in candidate_rows:
    print(
        candidate["rank"],
        "|",
        candidate.get("report_title")
        or candidate.get("vessel_name")
        or candidate["report_package_id"],
        "| weighted score:",
        candidate["weighted_score"],
        "| concepts:",
        candidate["matched_concepts"],
        "| evidence:",
        candidate["evidence_references"],
    )

driver.close()
