# Databricks notebook source
# MAGIC %md
# MAGIC # 52 — Find similar MAIRA investigation cases
# MAGIC
# MAGIC Deterministic first slice for similar-case discovery.
# MAGIC
# MAGIC Method:
# MAGIC - derive focus labels from the selected analysis graph;
# MAGIC - exclude Vessel/Actor/Claim labels from the similarity query;
# MAGIC - use MAIRA deterministic free-text lexical retrieval over
# MAGIC   INVESTIGATION / MAIN_REPORT passages;
# MAGIC - exclude the current MAIRA report package(s);
# MAGIC - aggregate candidate passages by report package;
# MAGIC - persist explainable package-level candidates with matched terms and
# MAGIC   page provenance.
# MAGIC
# MAGIC This notebook does not use an LLM, embeddings or vector similarity and
# MAGIC does not merge graphs across cases.

# COMMAND ----------

dbutils.widgets.text(
    "analysis_id",
    "",
    "Analysis ID",
)

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

analysis_id = dbutils.widgets.get(
    "analysis_id"
).strip()

if not re.fullmatch(
    r"analysis_[0-9a-f]{32}",
    analysis_id,
):
    raise ValueError(
        "Enter a valid analysis_id."
    )

SIMILAR_CASE_VERSION = "IKF_SIMILAR_MAIRA_CASES_V0.1"
MAX_CORPUS_PASSAGES = 5000
MAX_CORPUS_CHARACTERS = 30_000_000
MAX_RETRIEVED_PASSAGES = 120
MAX_RETRIEVED_CHARACTERS = 180_000
MAX_CANDIDATES = 5
MAX_EVIDENCE_PASSAGES_PER_CANDIDATE = 4

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

# Import MAIRA from the sibling Git-backed workspace repo.
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
    if current_notebook_path.startswith("/Users/")
    else current_notebook_path
)

ikf_repo_root = workspace_notebook_path.rsplit(
    "/notebooks/",
    1,
)[0]

workspace_user_root = ikf_repo_root.rsplit(
    "/",
    1,
)[0]

maira_imported = False

for candidate_name in (
    "MAIRA",
    "MAIRA-main",
):
    candidate_src = os.path.join(
        workspace_user_root,
        candidate_name,
        "src",
    )

    if not os.path.isdir(
        candidate_src
    ):
        continue

    if candidate_src not in sys.path:
        sys.path.insert(
            0,
            candidate_src,
        )

    try:
        from maira.retrieval import retrieve_free_text
        maira_imported = True
        break
    except ModuleNotFoundError:
        continue

if not maira_imported:
    driver.close()
    raise RuntimeError(
        "The MAIRA deterministic retrieval package is not importable from "
        "the current workspace Git folders."
    )

# COMMAND ----------

with driver.session() as session:
    meta = session.run(
        """
        MATCH (a:AnalysisGroup {
            analysis_id: $analysis_id
        })
        OPTIONAL MATCH (a)-[:HAS_SOURCE]->(d:SourceDocument)
        WITH
            a,
            collect(
                DISTINCT properties(d)["maira_report_package_id"]
            ) AS package_ids
        RETURN
            a.analysis_title AS analysis_title,
            a.status AS status,
            properties(a)["information_class"] AS information_class,
            [x IN package_ids WHERE x IS NOT NULL] AS current_package_ids
        """,
        analysis_id=analysis_id,
    ).single()

if meta is None:
    driver.close()
    raise ValueError(
        f"AnalysisGroup not found: {analysis_id}"
    )

meta = meta.data()

if meta.get("status") != "COMPLETED":
    driver.close()
    raise ValueError(
        "Similar-case discovery requires a completed analysis."
    )

# Similar cases are based on graph concepts, never on vessel/actor identity.
with driver.session() as session:
    concept_rows = [
        record.data()
        for record in session.run(
            """
            MATCH (n:KGNode {
                analysis_id: $analysis_id
            })
            WHERE n.node_kind IN [
                'Event',
                'ContributingFactor',
                'Finding',
                'SafetyIssue',
                'System'
            ]
            RETURN
                n.node_id AS node_id,
                n.node_kind AS node_kind,
                n.label AS label
            ORDER BY
                CASE n.node_kind
                    WHEN 'ContributingFactor' THEN 1
                    WHEN 'Event' THEN 2
                    WHEN 'SafetyIssue' THEN 3
                    WHEN 'Finding' THEN 4
                    WHEN 'System' THEN 5
                    ELSE 9
                END,
                n.label
            """,
            analysis_id=analysis_id,
        )
    ]

focus_labels = []
seen_focus = set()

for row in concept_rows:
    label = str(
        row.get("label") or ""
    ).strip()

    normalized = " ".join(
        label.casefold().split()
    )

    if (
        not normalized
        or normalized in seen_focus
        or normalized == "subject vessel"
    ):
        continue

    seen_focus.add(
        normalized
    )
    focus_labels.append(
        label
    )

if not focus_labels:
    driver.close()
    raise ValueError(
        "No suitable event/factor/finding/system concepts are available "
        "for deterministic similar-case retrieval."
    )

# Keep the first bounded set in deterministic priority order.
focus_labels = focus_labels[:20]
focus_query = " ; ".join(
    focus_labels
)

print("Analysis:", analysis_id)
print("Focus labels:", len(focus_labels))
for label in focus_labels:
    print(" -", label)

# COMMAND ----------

docs = (
    spark.table(
        "bdw_analysis_prod.maira.documents"
    )
    .filter(
        F.col("corpus_type")
        == "INVESTIGATION"
    )
    .filter(
        F.col("document_role")
        == "MAIN_REPORT"
    )
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

passages = (
    spark.table(
        "bdw_analysis_prod.maira.passages"
    )
    .join(
        docs.select(
            "document_id",
            "report_package_id",
        ),
        on=[
            "document_id",
            "report_package_id",
        ],
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
    .orderBy(
        "report_package_id",
        "document_id",
        "passage_number",
    )
)

current_package_ids = set(
    meta.get(
        "current_package_ids"
    )
    or []
)

if current_package_ids:
    passages = passages.filter(
        ~F.col(
            "report_package_id"
        ).isin(
            sorted(
                current_package_ids
            )
        )
    )

passage_rows = [
    row.asDict(
        recursive=True
    )
    for row in passages.collect()
]

corpus_characters = sum(
    len(
        row.get(
            "passage_text"
        )
        or ""
    )
    for row in passage_rows
)

if (
    len(passage_rows)
    > MAX_CORPUS_PASSAGES
    or corpus_characters
    > MAX_CORPUS_CHARACTERS
):
    driver.close()
    raise RuntimeError(
        "The current MAIRA corpus exceeds the bounded PoC similar-case "
        "retrieval limit. Move this method to a distributed retrieval "
        "implementation before scaling further. "
        f"passages={len(passage_rows)}; chars={corpus_characters}"
    )

print("Candidate MAIRA passages:", len(passage_rows))

# COMMAND ----------

retrieval = retrieve_free_text(
    passage_rows,
    focus_query,
    max_passages=MAX_RETRIEVED_PASSAGES,
    max_characters=MAX_RETRIEVED_CHARACTERS,
)

print("Retrieval method:", retrieval.method)
print("Candidate passage matches:", retrieval.candidate_count)
print("Selected passage matches:", retrieval.selected_count)

# COMMAND ----------

package_accumulator = {}

for hit in retrieval.hits:
    package_id = hit.report_package_id

    if not package_id:
        continue

    package = package_accumulator.setdefault(
        package_id,
        {
            "report_package_id": package_id,
            "total_score": 0,
            "max_passage_score": 0,
            "matched_query_terms": set(),
            "matched_expansion_terms": set(),
            "hits": [],
        },
    )

    package["total_score"] += int(
        hit.lexical_score
    )
    package["max_passage_score"] = max(
        package["max_passage_score"],
        int(hit.lexical_score),
    )
    package[
        "matched_query_terms"
    ].update(
        hit.matched_query_terms
    )
    package[
        "matched_expansion_terms"
    ].update(
        hit.matched_expansion_terms
    )
    package["hits"].append(
        hit
    )

ranked_packages = sorted(
    package_accumulator.values(),
    key=lambda item: (
        -len(
            item[
                "matched_query_terms"
            ]
        ),
        -item[
            "total_score"
        ],
        -item[
            "max_passage_score"
        ],
        item[
            "report_package_id"
        ],
    ),
)[:MAX_CANDIDATES]

# COMMAND ----------

metadata_by_package = {
    row["report_package_id"]:
        row.asDict(
            recursive=True
        )
    for row in (
        docs
        .orderBy(
            "report_package_id",
            "document_id",
        )
        .collect()
    )
}

candidate_rows = []

for rank, package in enumerate(
    ranked_packages,
    start=1,
):
    metadata = metadata_by_package.get(
        package[
            "report_package_id"
        ],
        {},
    )

    evidence_hits = sorted(
        package[
            "hits"
        ],
        key=lambda hit: (
            -hit.lexical_score,
            hit.document_id,
            (
                hit.passage_number
                if hit.passage_number
                is not None
                else 10**12
            ),
            hit.passage_id,
        ),
    )[
        :MAX_EVIDENCE_PASSAGES_PER_CANDIDATE
    ]

    evidence_passage_ids = [
        hit.passage_id
        for hit in evidence_hits
    ]

    evidence_references = []
    evidence_locations = []

    filename = (
        metadata.get(
            "source_filename"
        )
        or metadata.get(
            "report_title"
        )
        or package[
            "report_package_id"
        ]
    )

    for hit in evidence_hits:
        if hit.start_page is None:
            page_ref = "page unknown"
        elif (
            hit.end_page is None
            or hit.end_page
            == hit.start_page
        ):
            page_ref = (
                f"p. {hit.start_page}"
            )
        else:
            page_ref = (
                f"pp. {hit.start_page}–{hit.end_page}"
            )

        evidence_references.append(
            f"{filename} · {page_ref}"
        )
        evidence_locations.append(
            (
                hit.document_id
                + "|"
                + (
                    ""
                    if hit.start_page
                    is None
                    else str(
                        hit.start_page
                    )
                )
                + "|"
                + (
                    ""
                    if hit.end_page
                    is None
                    else str(
                        hit.end_page
                    )
                )
            )
        )

    candidate_id = (
        "similar_case_"
        + hashlib.sha256(
            (
                analysis_id
                + "|"
                + package[
                    "report_package_id"
                ]
                + "|"
                + SIMILAR_CASE_VERSION
            ).encode(
                "utf-8"
            )
        ).hexdigest()[:24]
    )

    candidate_rows.append(
        {
            "candidate_id":
                candidate_id,
            "rank":
                rank,
            "report_package_id":
                package[
                    "report_package_id"
                ],
            "report_title":
                metadata.get(
                    "report_title"
                ),
            "vessel_name":
                metadata.get(
                    "vessel_name"
                ),
            "source_filename":
                metadata.get(
                    "source_filename"
                ),
            "publication_date":
                (
                    str(
                        metadata.get(
                            "publication_date"
                        )
                    )
                    if metadata.get(
                        "publication_date"
                    )
                    is not None
                    else None
                ),
            "investigation_body":
                metadata.get(
                    "investigation_body"
                ),
            "matched_query_terms":
                sorted(
                    package[
                        "matched_query_terms"
                    ]
                ),
            "matched_expansion_terms":
                sorted(
                    package[
                        "matched_expansion_terms"
                    ]
                ),
            "total_score":
                int(
                    package[
                        "total_score"
                    ]
                ),
            "max_passage_score":
                int(
                    package[
                        "max_passage_score"
                    ]
                ),
            "evidence_passage_ids":
                evidence_passage_ids,
            "evidence_references":
                evidence_references,
            "evidence_locations":
                evidence_locations,
        }
    )

snapshot_payload = {
    "analysis_id":
        analysis_id,
    "version":
        SIMILAR_CASE_VERSION,
    "retrieval_method":
        retrieval.method,
    "focus_labels":
        focus_labels,
    "current_package_ids":
        sorted(
            current_package_ids
        ),
    "candidate_package_ids":
        [
            row[
                "report_package_id"
            ]
            for row in candidate_rows
        ],
    "candidate_passage_ids":
        [
            passage_id
            for row in candidate_rows
            for passage_id in row[
                "evidence_passage_ids"
            ]
        ],
}

snapshot_id = (
    "similar_snapshot_"
    + hashlib.sha256(
        json.dumps(
            snapshot_payload,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        ).encode(
            "utf-8"
        )
    ).hexdigest()[:32]
)

# COMMAND ----------

with driver.session() as session:
    session.run(
        """
        CREATE CONSTRAINT similar_case_run_id_unique
        IF NOT EXISTS
        FOR (r:SimilarCaseRun)
        REQUIRE r.similar_case_run_id IS UNIQUE
        """
    ).consume()

    session.run(
        """
        CREATE CONSTRAINT similar_case_candidate_id_unique
        IF NOT EXISTS
        FOR (c:SimilarCaseCandidate)
        REQUIRE c.candidate_id IS UNIQUE
        """
    ).consume()

    run_id = (
        "similar_run_"
        + hashlib.sha256(
            (
                analysis_id
                + "|"
                + snapshot_id
            ).encode(
                "utf-8"
            )
        ).hexdigest()[:24]
    )

    session.run(
        """
        MATCH (a:AnalysisGroup {
            analysis_id: $analysis_id
        })
        MERGE (run:SimilarCaseRun {
            similar_case_run_id: $run_id
        })
        ON CREATE SET
            run.created_at = datetime()
        SET
            run.analysis_id = $analysis_id,
            run.version = $version,
            run.retrieval_method = $retrieval_method,
            run.retrieval_snapshot_id = $snapshot_id,
            run.focus_labels = $focus_labels,
            run.current_package_ids = $current_package_ids,
            run.candidate_count = $candidate_count,
            run.status = 'COMPLETED',
            run.updated_at = datetime()
        MERGE (a)-[:HAS_SIMILAR_CASE_RUN]->(run)
        """,
        analysis_id=analysis_id,
        run_id=run_id,
        version=SIMILAR_CASE_VERSION,
        retrieval_method=retrieval.method,
        snapshot_id=snapshot_id,
        focus_labels=focus_labels,
        current_package_ids=sorted(
            current_package_ids
        ),
        candidate_count=len(
            candidate_rows
        ),
    ).consume()

    for candidate in candidate_rows:
        session.run(
            """
            MATCH (run:SimilarCaseRun {
                similar_case_run_id: $run_id
            })
            MERGE (c:SimilarCaseCandidate {
                candidate_id: $candidate_id
            })
            ON CREATE SET
                c.created_at = datetime()
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
            retrieval_method=retrieval.method,
            snapshot_id=snapshot_id,
            **candidate,
        ).consume()

print("")
print(
    "SIMILAR MAIRA CASE RETRIEVAL COMPLETE"
)
print("run_id:", run_id)
print("snapshot_id:", snapshot_id)
print("candidates:", len(candidate_rows))

for candidate in candidate_rows:
    print(
        candidate["rank"],
        "|",
        candidate.get("report_title")
        or candidate.get("vessel_name")
        or candidate["report_package_id"],
        "| matched terms:",
        candidate["matched_query_terms"],
        "| evidence:",
        candidate["evidence_references"],
    )

driver.close()
