from ikf.app_lazy_navigation import transform_app_lazy_navigation


def _final_ui_fixture():
    return '''(
    tab_home,
    tab_news,
    tab_transcriptions,
    tab_new_analysis,
    tab_findings,
    tab_knowledge_graph,
    tab_analyses,
    tab_review,
    tab_about,
) = st.tabs(
    [
        "Home",
        "News & Alerts",
        "Audio transcription",
        "Analyse Documents",
        "Findings & Evidence",
        "Knowledge Graph",
        "Ask LLMs",
        "Review & Validate",
        "Terms of reference",
    ]
)

with tab_home:
    pass
with tab_news:
    pass
with tab_transcriptions:
    pass
with tab_new_analysis:
    pass
with tab_findings:
    pass
with tab_knowledge_graph:
    pass
with tab_analyses:
    case_question_tab, direct_reference_tab = st.tabs(["Case", "Direct"])
    with case_question_tab:
        pass
    with direct_reference_tab:
        pass
with tab_review:
    pass
with tab_review:
    pass
with tab_about:
    pass
'''


def test_lazy_navigation_preserves_capabilities_and_compiles():
    transformed, applied = transform_app_lazy_navigation(_final_ui_fixture())

    assert "top_level_tabs_replaced_with_single_capability_selector" in applied
    assert "inactive_capability_bodies_do_not_execute" in applied
    assert 'key="ikf_active_capability"' in transformed

    guards = {
        "Home": 1,
        "News & Alerts": 1,
        "Audio transcription": 1,
        "Analyse Documents": 1,
        "Findings & Evidence": 1,
        "Knowledge Graph": 1,
        "Ask LLMs": 1,
        "Review & Validate": 2,
        "Terms of reference": 1,
    }
    for capability, expected in guards.items():
        assert transformed.count(
            f'if active_capability == "{capability}":'
        ) == expected

    # Inner Ask-mode tabs are intentionally preserved.
    assert "case_question_tab, direct_reference_tab = st.tabs(" in transformed
    assert "with case_question_tab:" in transformed
    assert "with direct_reference_tab:" in transformed

    # Old eager top-level tab guards must not survive.
    for old_guard in (
        "with tab_home:",
        "with tab_news:",
        "with tab_transcriptions:",
        "with tab_new_analysis:",
        "with tab_findings:",
        "with tab_knowledge_graph:",
        "with tab_analyses:",
        "with tab_review:",
        "with tab_mapping_review:",
        "with tab_about:",
    ):
        assert old_guard not in transformed

    compile(transformed, "<test-lazy-navigation>", "exec")
