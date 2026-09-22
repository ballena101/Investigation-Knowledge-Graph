# Databricks notebook source
# MAGIC %md
# MAGIC # 54 — Validate deterministic similar MAIRA cases
# MAGIC
# MAGIC Read-only validation for the latest SimilarCaseRun of one analysis.
# MAGIC
# MAGIC Confirms:
# MAGIC - current report package(s) are excluded;
# MAGIC - candidates are ranked uniquely;
# MAGIC - candidate evidence passage IDs exist in MAIRA;
# MAGIC - each evidence passage belongs to the candidate report package;
# MAGIC - page-location keys agree with the MAIRA passage provenance;
# MAGIC - retrieval method/version provenance is present.

# COMMAND ----------

dbutils.widgets.text(
    "analysis_id",
    "",
    "Analysis ID",
)

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1

# COMMAND ----------

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
        "Enter a valid analysis_id."
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
    run_record = session.run(
        """
        MATCH (a:AnalysisGroup {
            analysis_id: $analysis_id
        })-[:HAS_SIMILAR_CASE_RUN]->(
            run:SimilarCaseRun
        )
        WITH run
        ORDER BY run.updated_at DESC
        LIMIT 1
        OPTIONAL MATCH (run)-[:HAS_SIMILAR_CASE_CANDIDATE]->(
            c:SimilarCaseCandidate
        )
        RETURN
            run.similar_case_run_id AS run_id,
            run.version AS version,
            run.retrieval_method AS retrieval_method,
            run.retrieval_snapshot_id AS retrieval_snapshot_id,
            coalesce(
                run.current_package_ids,
                []
            ) AS current_package_ids,
            collect({
                candidate_id:
                    c.candidate_id,
                rank:
                    c.rank,
                report_package_id:
                    c.report_package_id,
                evidence_passage_ids:
                    coalesce(
                        c.evidence_passage_ids,
                        []
                    ),
                evidence_locations:
                    coalesce(
                        c.evidence_locations,
                        []
                    ),
                matched_query_terms:
                    coalesce(
                        c.matched_query_terms,
                        []
                    )
            }) AS candidates
        """,
        analysis_id=analysis_id,
    ).single()

if run_record is None:
    driver.close()
    raise ValueError(
        "No SimilarCaseRun exists for this analysis."
    )

run = run_record.data()
candidates = [
    candidate
    for candidate in (
        run.get(
            "candidates"
        )
        or []
    )
    if candidate.get(
        "candidate_id"
    )
]

print("Run:", run["run_id"])
print("Version:", run["version"])
print(
    "Retrieval method:",
    run["retrieval_method"],
)
print(
    "Snapshot:",
    run["retrieval_snapshot_id"],
)
print(
    "Candidates:",
    len(candidates),
)

# COMMAND ----------

errors = []

if not run.get(
    "version"
):
    errors.append(
        "SimilarCaseRun has no version."
    )

if not run.get(
    "retrieval_method"
):
    errors.append(
        "SimilarCaseRun has no retrieval_method."
    )

if not run.get(
    "retrieval_snapshot_id"
):
    errors.append(
        "SimilarCaseRun has no retrieval_snapshot_id."
    )

current_packages = set(
    run.get(
        "current_package_ids"
    )
    or []
)

ranks = [
    int(
        candidate["rank"]
    )
    for candidate in candidates
]

if len(
    ranks
) != len(
    set(
        ranks
    )
):
    errors.append(
        "Candidate ranks are not unique."
    )

if ranks and sorted(
    ranks
) != list(
    range(
        1,
        len(
            ranks
        )
        + 1,
    )
):
    errors.append(
        "Candidate ranks are not contiguous from 1."
    )

for candidate in candidates:
    package_id = candidate[
        "report_package_id"
    ]

    if package_id in current_packages:
        errors.append(
            "Current report package was returned as a similar-case candidate: "
            + str(
                package_id
            )
        )

# COMMAND ----------

all_passage_ids = sorted(
    {
        passage_id
        for candidate in candidates
        for passage_id in (
            candidate.get(
                "evidence_passage_ids"
            )
            or []
        )
    }
)

if all_passage_ids:
    passage_rows = (
        spark.table(
            "bdw_analysis_prod.maira.passages"
        )
        .filter(
            F.col(
                "passage_id"
            ).isin(
                all_passage_ids
            )
        )
        .select(
            "passage_id",
            "document_id",
            "report_package_id",
            "start_page",
            "end_page",
        )
        .collect()
    )
else:
    passage_rows = []

passage_by_id = {
    row["passage_id"]:
        row.asDict(
            recursive=True
        )
    for row in passage_rows
}

missing_passages = sorted(
    set(
        all_passage_ids
    )
    - set(
        passage_by_id
    )
)

if missing_passages:
    errors.append(
        "Candidate evidence passages are missing from MAIRA: "
        + ", ".join(
            missing_passages
        )
    )

# COMMAND ----------

for candidate in candidates:
    package_id = candidate[
        "report_package_id"
    ]

    candidate_passages = (
        candidate.get(
            "evidence_passage_ids"
        )
        or []
    )

    if not candidate_passages:
        errors.append(
            f"Candidate {candidate['candidate_id']} has no evidence passages."
        )

    for passage_id in candidate_passages:
        passage = passage_by_id.get(
            passage_id
        )

        if passage is None:
            continue

        if (
            passage[
                "report_package_id"
            ]
            != package_id
        ):
            errors.append(
                f"Passage {passage_id} belongs to package "
                f"{passage['report_package_id']} instead of candidate "
                f"{package_id}."
            )

    for raw_location in (
        candidate.get(
            "evidence_locations"
        )
        or []
    ):
        parts = str(
            raw_location
        ).split(
            "|"
        )

        if len(
            parts
        ) != 3:
            errors.append(
                "Invalid evidence location format: "
                + str(
                    raw_location
                )
            )
            continue

        document_id = parts[
            0
        ]
        page_start = (
            int(
                parts[
                    1
                ]
            )
            if parts[
                1
            ].isdigit()
            else None
        )
        page_end = (
            int(
                parts[
                    2
                ]
            )
            if parts[
                2
            ].isdigit()
            else None
        )

        location_match = any(
            passage[
                "document_id"
            ]
            == document_id
            and passage[
                "start_page"
            ]
            == page_start
            and passage[
                "end_page"
            ]
            == page_end
            for passage_id in candidate_passages
            for passage in [
                passage_by_id.get(
                    passage_id
                )
            ]
            if passage is not None
        )

        if not location_match:
            errors.append(
                "Evidence location is not backed by a candidate MAIRA "
                "passage: "
                + str(
                    raw_location
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
        "Similar MAIRA case validation failed."
    )

print("")
print(
    "PASS — SIMILAR MAIRA CASES ARE DETERMINISTIC AND TRACEABLE"
)
print(
    "Current package(s) excluded:",
    sorted(
        current_packages
    ),
)
print(
    "Candidate package count:",
    len(
        candidates
    ),
)

driver.close()
