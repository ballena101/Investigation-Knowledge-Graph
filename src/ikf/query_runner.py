"""App-facing governed query runner for IKF.

MAIRA remains the source of passages, provenance, terminology mappings,
and deterministic relationship assessment. IKF orchestrates those governed
components for downstream model analysis and application use.
"""

from __future__ import annotations

from typing import Any
import hashlib

from pyspark.sql import functions as F

from maira.relationships import detect_contributed_to


def _distinct_values(df, column: str) -> list[str]:
    return [
        row[column]
        for row in df.select(column).distinct().collect()
        if row[column] is not None
    ]


def run_query(
    spark,
    query_id: str,
    *,
    document_id: str | None = None,
) -> list[dict[str, Any]]:
    """Run a governed MAIRA query and return supported relationship evidence.

    Current PoC support:
    - CONTRIBUTED_TO relationship queries such as Q003.

    Parameters
    ----------
    spark:
        Active SparkSession.
    query_id:
        Governed query identifier from MAIRA query_specifications.
    document_id:
        Optional MAIRA document_id. If omitted, all INVESTIGATION MAIN_REPORT
        passages are assessed.

    Returns
    -------
    list[dict]
        Supported passage-level relationship evidence ready for downstream
        model analysis or app presentation.
    """

    spec = (
        spark.table("bdw_analysis_prod.maira.query_specifications")
        .filter(F.col("query_id") == query_id)
        .select("query_spec_id", "relationship")
        .first()
    )

    if spec is None:
        raise ValueError(f"Unknown governed query_id: {query_id}")

    query_spec_id = spec["query_spec_id"]
    relationship = spec["relationship"]

    if relationship != "CONTRIBUTED_TO":
        raise NotImplementedError(
            f"run_query currently supports CONTRIBUTED_TO only; got {relationship}"
        )

    concepts = (
        spark.table("bdw_analysis_prod.maira.query_spec_concepts")
        .filter(F.col("query_spec_id") == query_spec_id)
        .select("component_role", "code_value", "code_idcode")
    )

    subject_concepts = concepts.filter(F.col("component_role") == "SUBJECT_FACTOR")
    object_concepts = concepts.filter(F.col("component_role") == "OBJECT_EVENT")
    context_concepts = concepts.filter(F.col("component_role") == "OBJECT_CONTEXT")

    subject_codes = _distinct_values(subject_concepts, "code_idcode")
    object_codes = _distinct_values(object_concepts, "code_idcode")
    context_codes = _distinct_values(context_concepts, "code_idcode")

    # Preserve taxonomy labels and add only human-validated source-language
    # normalisations. The detector itself remains deterministic.
    subject_terms = set(_distinct_values(subject_concepts, "code_value"))
    object_terms = set(_distinct_values(object_concepts, "code_value"))
    context_terms = set(_distinct_values(context_concepts, "code_value"))

    normalisations = (
        spark.table("bdw_analysis_prod.maira.terminology_normalisations")
        .filter(F.col("review_status") == "HUMAN_VALIDATED")
        .select("source_expression", "target_code_idcode")
    )

    subject_terms.update(
        _distinct_values(
            normalisations.filter(F.col("target_code_idcode").isin(subject_codes)),
            "source_expression",
        )
    )
    object_terms.update(
        _distinct_values(
            normalisations.filter(F.col("target_code_idcode").isin(object_codes)),
            "source_expression",
        )
    )
    context_terms.update(
        _distinct_values(
            normalisations.filter(F.col("target_code_idcode").isin(context_codes)),
            "source_expression",
        )
    )

    p = spark.table("bdw_analysis_prod.maira.passages").alias("p")
    d = (
        spark.table("bdw_analysis_prod.maira.documents")
        .select("document_id", "corpus_type", "document_role")
        .alias("d")
    )

    passages = (
        p.join(
            d,
            F.col("p.document_id") == F.col("d.document_id"),
            "inner",
        )
        .filter(F.col("d.corpus_type") == "INVESTIGATION")
        .filter(F.col("d.document_role") == "MAIN_REPORT")
    )

    if document_id is not None:
        passages = passages.filter(F.col("p.document_id") == document_id)

    passages = passages.select(
        F.col("p.passage_id").alias("passage_id"),
        F.col("p.document_id").alias("document_id"),
        F.col("p.report_package_id").alias("report_package_id"),
        F.col("p.passage_number").alias("passage_number"),
        F.col("p.start_page").alias("start_page"),
        F.col("p.end_page").alias("end_page"),
        F.col("p.passage_text").alias("passage_text"),
        F.col("p.passage_text_sha256").alias("passage_text_sha256"),
    )

    results: list[dict[str, Any]] = []

    for row in passages.collect():
        assessment = detect_contributed_to(
            row["passage_text"],
            subject_terms=sorted(subject_terms),
            object_terms=sorted(object_terms),
            object_context_terms=sorted(context_terms),
            context_text=row["passage_text"],
        )

        if assessment.relationship_assessment != "SUPPORTED_REQUESTED_RELATIONSHIP":
            continue

        for match in assessment.matches:
            evidence_text = match.evidence_sentence
            evidence_text_sha256 = hashlib.sha256(
                evidence_text.encode("utf-8")
            ).hexdigest()

            results.append(
                {
                    "query_id": query_id,
                    "query_spec_id": query_spec_id,
                    "passage_id": row["passage_id"],
                    "document_id": row["document_id"],
                    "report_package_id": row["report_package_id"],
                    "passage_number": row["passage_number"],
                    "start_page": row["start_page"],
                    "end_page": row["end_page"],
                    "subject_term": match.subject_term,
                    "requested_relationship": relationship,
                    "object_term": match.object_term,
                    "relation_cue": match.cue,
                    "relation_direction": match.direction,
                    "evidence_text": evidence_text,
                    "evidence_text_sha256": evidence_text_sha256,
                    "source_passage_text_sha256": row["passage_text_sha256"],
                }
            )

    return results
