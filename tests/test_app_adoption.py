"""Regression tests for the transitional Streamlit shared-policy adoption."""

from pathlib import Path

from ikf.app_adoption import transform_app_source


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_FILE = REPO_ROOT / "app" / "app.py"


def test_real_app_source_adopts_shared_policy_and_compiles():
    source = APP_FILE.read_text(encoding="utf-8")
    transformed, applied = transform_app_source(source)

    assert set(applied) == {
        "shared_imports",
        "class_d_llama_alias",
        "retention_policy",
        "evidence_location_parser",
        "source_catalogue_routing",
        "question_scope",
        "relationship_review",
        "shield_gate2",
        "emcip_review",
        "graph_document_scope",
    }

    assert 'CLASS_D_OLLAMA_LLAMA70_URL = os.getenv("CLASS_D_OLLAMA_LLAMA70_URL")' in transformed
    assert "shared_content_retention_hours(information_class)" in transformed
    assert "legacy_parse_evidence_location(value)" in transformed
    assert "filter_catalogue_rows(" in transformed
    assert "resolve_effective_document_scope(" in transformed
    assert "validate_human_relationship_review(" in transformed
    assert "validate_app_shield_review(" in transformed
    assert "validate_app_emcip_review(" in transformed
    assert "scope_graph_by_documents(" in transformed

    compile(transformed, str(APP_FILE), "exec")


def test_transform_fails_closed_when_policy_anchor_drifts():
    source = APP_FILE.read_text(encoding="utf-8")
    broken = source.replace(
        "def content_retention_hours(information_class):",
        "def changed_retention_function(information_class):",
        1,
    )

    try:
        transform_app_source(broken)
    except RuntimeError as exc:
        assert "retention_policy" in str(exc)
    else:
        raise AssertionError("App adoption must fail closed when a governed anchor drifts")
