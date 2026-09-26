from pathlib import Path

from ikf.app_lazy_navigation import transform_app_lazy_navigation


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = REPO_ROOT / "app" / "app.py"


def test_lazy_navigation_preserves_capabilities_and_compiles():
    source = APP_SOURCE.read_text(encoding="utf-8")
    transformed, applied = transform_app_lazy_navigation(source)

    assert "top_level_tabs_replaced_with_single_capability_selector" in applied
    assert "inactive_capability_bodies_do_not_execute" in applied
    assert 'key="ikf_active_capability"' in transformed
    assert "= st.tabs(" not in transformed.split("# LAZY_CAPABILITY_NAVIGATION", 1)[1].split("@st.fragment", 1)[0]

    guards = {
        "Home": 1,
        "News & Alerts": 1,
        "Transcriptions": 1,
        "Analyse Documents": 1,
        "Findings & Evidence": 1,
        "Knowledge Graph": 1,
        "Ask / Compare LLMs": 1,
        "Review & Validate": 3,
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
