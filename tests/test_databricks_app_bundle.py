"""Tests for the derived Databricks App deployment bundle."""

import json
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDER = REPO_ROOT / "scripts" / "build_databricks_app_bundle.py"


def build_test_bundle(tmp_path):
    output = tmp_path / "ikf_app"
    subprocess.run(
        [sys.executable, str(BUILDER), "--output", str(output)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return output


def test_bundle_contains_app_and_canonical_ikf_package(tmp_path):
    output = build_test_bundle(tmp_path)

    assert (output / "app.py").is_file()
    assert (output / "bootstrap.py").is_file()
    assert (output / "app.yaml").is_file()
    assert (output / "requirements.txt").is_file()
    assert (output / ".ikf_shared_policy_materialized").is_file()
    assert (output / "ikf_bundle_manifest.json").is_file()

    shared = output / "src" / "ikf"
    for name in (
        "app_adoption.py",
        "app_audio_adoption.py",
        "app_ui_adoption.py",
        "source_routing.py",
        "evidence_locations.py",
        "question_scope.py",
        "review_governance.py",
        "shield_governance.py",
        "emcip_governance.py",
        "graph_governance.py",
        "retention.py",
    ):
        assert (shared / name).is_file(), name


def test_bundle_materializes_policy_audio_and_ui_before_deployment(tmp_path):
    output = build_test_bundle(tmp_path)
    materialized = (output / "app.py").read_text(encoding="utf-8")

    assert 'CLASS_D_OLLAMA_LLAMA70_URL = os.getenv("CLASS_D_OLLAMA_LLAMA70_URL")' in materialized
    assert "shared_content_retention_hours(information_class)" in materialized
    assert "legacy_parse_evidence_location(value)" in materialized
    assert "filter_catalogue_rows(" in materialized
    assert "resolve_effective_document_scope(" in materialized
    assert "validate_human_relationship_review(" in materialized
    assert "validate_app_shield_review(" in materialized
    assert "validate_app_emcip_review(" in materialized
    assert "scope_graph_by_documents(" in materialized

    assert 'return get_current_user_key() != "unknown"' in materialized
    assert "Audio / reviewed transcript — Class D" in materialized
    assert "Use reviewed audio transcript in this analysis" in materialized
    assert "Machine-generated transcript — not validated evidence" in materialized
    assert 'st.session_state["analysis_information_class"] = "D"' in materialized

    assert "import html" in materialized
    assert "Active analysis: {active_analysis_title}" in materialized
    assert "color:#1f77b4" in materialized
    assert "font-size:1.05rem" in materialized

    compile(materialized, str(output / "app.py"), "exec")


def test_bundle_manifest_records_materialized_contract(tmp_path):
    output = build_test_bundle(tmp_path)
    manifest = json.loads(
        (output / "ikf_bundle_manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["bundle_contract"] == "IKF_DATABRICKS_APP_BUNDLE_V0.3"
    assert manifest["adoption_version"].startswith("IKF_APP_SHARED_POLICY_ADOPTION_")
    assert manifest["audio_adoption_version"].startswith("IKF_APP_AUDIO_ADOPTION_")
    assert manifest["ui_adoption_version"].startswith("IKF_APP_UI_ADOPTION_")
    assert manifest["source_app_sha256"] != manifest["materialized_app_sha256"]
    assert set(manifest["applied_policy_adoptions"]) == {
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
    assert set(manifest["applied_audio_adoptions"]) == {
        "app_access_is_type_d_audio_boundary",
        "analyse_documents_audio_review",
        "transcription_access_message",
    }
    assert set(manifest["applied_ui_adoptions"]) == {
        "html_escape_import",
        "active_analysis_header",
    }
    assert manifest["shared_package_path"] == "src/ikf"


def test_bundled_bootstrap_prefers_materialized_source(tmp_path):
    output = build_test_bundle(tmp_path)
    bootstrap = (output / "bootstrap.py").read_text(encoding="utf-8")

    assert 'APP_DIR / "src"' in bootstrap
    assert "MATERIALIZED_MARKER" in bootstrap
    assert "transform_app_audio_source" in bootstrap
    assert (output / "src" / "ikf").is_dir()
