"""Deterministic App refinements for weighted MAIRA similar-case retrieval."""

from __future__ import annotations


SIMILARITY_REFINEMENT_VERSION = "IKF_APP_SIMILARITY_REFINEMENT_V0.1"


def _replace_once(source: str, old: str, new: str, name: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Similarity refinement failed at {name}: expected one match, found {count}."
        )
    return source.replace(old, new, 1)


def transform_app_similarity_refinement(source: str) -> tuple[str, tuple[str, ...]]:
    applied = []

    source = _replace_once(
        source,
        '''            run_updated_at:
                toString(
                    run.updated_at
                ),
            candidate_id:
''',
        '''            run_updated_at:
                toString(
                    run.updated_at
                ),
            maira_registered_main_reports:
                run.maira_registered_main_reports,
            maira_query_ready_main_reports:
                run.maira_query_ready_main_reports,
            maira_coverage_gap:
                run.maira_coverage_gap,
            candidate_id:
''',
        "similar-case run coverage fields",
    )

    source = _replace_once(
        source,
        '''            matched_expansion_terms:
                coalesce(
                    c.matched_expansion_terms,
                    []
                ),
            total_score:
''',
        '''            matched_expansion_terms:
                coalesce(
                    c.matched_expansion_terms,
                    []
                ),
            matched_concepts:
                coalesce(
                    c.matched_concepts,
                    []
                ),
            weighted_score:
                c.weighted_score,
            total_score:
''',
        "weighted similar-case candidate fields",
    )
    applied.append("weighted_candidate_provenance")

    source = _replace_once(
        source,
        '''            if similar_candidates:
                global_source_by_id = {
''',
        '''            if similar_candidates:
                _coverage_ready = similar_candidates[0].get(
                    "maira_query_ready_main_reports"
                )
                _coverage_registered = similar_candidates[0].get(
                    "maira_registered_main_reports"
                )
                _coverage_gap = similar_candidates[0].get(
                    "maira_coverage_gap"
                )
                if (
                    _coverage_ready is not None
                    and _coverage_registered is not None
                ):
                    st.caption(
                        "MAIRA search coverage: "
                        + str(_coverage_ready)
                        + "/"
                        + str(_coverage_registered)
                        + " processed MAIN_REPORT document(s) query-ready"
                        + (
                            " · complete"
                            if int(_coverage_gap or 0) == 0
                            else " · " + str(_coverage_gap) + " processing gap(s)"
                        )
                    )

                global_source_by_id = {
''',
        "MAIRA coverage display",
    )
    applied.append("maira_query_ready_coverage_display")

    source = _replace_once(
        source,
        '''                        if matched_terms:
                            st.markdown(
                                "**Why this matched**"
                            )
                            st.write(
                                ", ".join(
                                    matched_terms
                                )
                            )

                        if candidate.get(
''',
        '''                        if matched_terms:
                            st.markdown(
                                "**Why this matched**"
                            )
                            st.write(
                                ", ".join(
                                    matched_terms
                                )
                            )

                        matched_concepts = (
                            candidate.get("matched_concepts")
                            or []
                        )
                        if matched_concepts:
                            st.caption(
                                "Weighted case concepts: "
                                + " · ".join(matched_concepts)
                            )
                        if candidate.get("weighted_score") is not None:
                            st.caption(
                                "Deterministic weighted score: "
                                + str(candidate.get("weighted_score"))
                            )

                        if candidate.get(
''',
        "weighted match explanation",
    )
    applied.append("weighted_match_explanation")

    return source, tuple(applied)
