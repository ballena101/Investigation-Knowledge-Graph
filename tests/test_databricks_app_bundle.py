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
        "app_files_api_adoption.py",
        "app_audio_adoption.py",
        "app_audio_fixup.py",
        "app_timeline_adoption.py",
        "app_ui_adoption.py",
        "app_workflow_adoption.py",
        "app_simplification_adoption.py",
        "timeline.py",
        "transcription_governance.py",
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


def test_bundle_materializes_policy_audio_timeline_ui_workflow_and_simplification_before_deployment(tmp_path):
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

    assert "FILES_API_DOWNLOAD_CHUNK_BYTES = 4 * 1024 * 1024" in materialized
    assert '"Range": f"bytes={start}-{end}"' in materialized
    assert 'headers["If-Unmodified-Since"] = last_modified' in materialized
    assert "http.client.IncompleteRead" in materialized
    assert "_source_files_api_range(" in materialized

    assert 'TRANSCRIPTION_JOB_ID = os.getenv(' in materialized
    assert "list_type_d_audio_sources" in materialized
    assert "Transcribe selected audio" in materialized
    assert "Accept validated transcript" in materialized
    assert "CLASS D DOCUMENT AVAILABLE" in materialized
    assert "document_kind = 'TRANSCRIPT'" in materialized
    assert "properties(d)[\"information_class\"] AS information_class" in materialized
    assert "Audio / reviewed transcript — Class D" not in materialized
    assert "Use reviewed audio transcript in this analysis" not in materialized
    assert 'st.session_state["analysis_information_class"] = "D"' not in materialized
    assert "decrypt_direct_text(" not in materialized
    assert "Fernet(" in materialized

    assert "/api/2.0/fs/directories" in materialized
    assert "download_source_file_as_user(str(path))" in materialized
    assert "load_type_d_audio_bytes" in materialized
    assert "TYPE_D_TRANSCRIPT_ROOT.glob" not in materialized
    assert "TYPE_D_TRANSCRIPT_ROOT.is_dir()" not in materialized
    assert "audio_path.open(\"rb\")" not in materialized

    assert "refresh_transcription_" in materialized
    assert "refresh_transcript_publication_" in materialized
    assert "ask_question_col, ask_refresh_col = st.columns([0.92, 0.08])" in materialized
    assert materialized.count('key="refresh_analysis_status"') == 1

    assert "Ask LLMs" in materialized
    assert "Ask / Compare LLMs" not in materialized
    assert materialized.index('st.markdown("### Question history")') < materialized.index(
        "ask_question_col, ask_refresh_col"
    )

    assert 'review_evidence_col, review_decision_col = st.columns(2, gap="large")' in materialized
    assert 'with st.expander("Technical evidence IDs", expanded=False):' in materialized
    assert '"Evidence page"' in materialized
    assert "height=340" in materialized
    assert "with review_decision_col:" in materialized

    assert "### Brief analysis summary" in materialized
    assert "contextual orientation during extraction" in materialized

    assert "### 2. EMCIP mapping review" not in materialized
    assert "Generate / refresh EMCIP proposals" not in materialized
    assert "### SHIELD classification of contributing factors" in materialized
    assert '"Contributing factor"' in materialized
    assert '"SHIELD (LLM)"' in materialized
    assert "No manual SHIELD label selection is required" in materialized

    assert "apply_latest_relationship_reviews_to_graph" in materialized
    assert "rejected relationship(s) hidden" in materialized
    assert 'decision == "REJECTED"' in materialized
    assert 'decision == "AMENDED"' in materialized
    assert 'st.markdown("### Ask about this graph scope")' not in materialized

    # Final simplification pass: one compact routing table plus one short
    # confidentiality notice, with stale user-visible wording removed.
    assert '"AI routing and information classes"' in materialized
    assert '"Confidentiality and Article 9"' in materialized
    assert "AI model routing and Article 9 suitability" not in materialized
    assert "Compliance, confidentiality and AI-use notice" not in materialized
    assert "Article 9-aligned handling rules" in materialized
    assert "Dedicated IKF Databricks services" in materialized
    assert "Dedicated IKG Databricks endpoint" not in materialized
    assert "Controlled Ollama Llama 3.3 70B service is not configured" not in materialized
    assert "Today's Ollama quota has been reset" not in materialized
    assert "Only an IKG administrator" not in materialized
    assert "TYPE_D_TRANSCRIPT_REVIEWERS" not in materialized
    assert "APP_BUILD" not in materialized
    assert "App build:" not in materialized
    assert "### Current validation milestone" not in materialized
    assert "Audio transcription" in materialized
    assert "tab_mapping_review = tab_review" not in materialized

    # Timeline V0.3 is automatically projected from the existing KG/evidence
    # and remains editable/validatable without an additional LLM call.
    assert '"Timeline"' in materialized
    assert "load_default_timeline_projection" in materialized
    assert "project_default_timeline" in materialized
    assert "Default chronology" in materialized
    assert "SOURCE_ORDER" in materialized
    assert "FOLLOWED_BY" in materialized
    assert "Chronology conflicts / reconciliation" in materialized
    assert "Audio time alignment" in materialized
    assert "Evidence-based conclusion" in materialized
    assert "Save investigator timeline decision" in materialized
    assert "HAS_TIMELINE_EVENT" in materialized
    assert "HUMAN_VALIDATED" in materialized
    assert "Add validated timeline event" not in materialized

    assert "import html" in materialized
    assert "Active analysis: {active_analysis_title}" in materialized
    assert "color:#1f77b4" in materialized
    assert "font-size:1.05rem" in materialized

    app_yaml = (output / "app.yaml").read_text(encoding="utf-8")
    assert "EMCIP_MAPPING_JOB_ID" not in app_yaml
    assert "emcip_mapping_job" not in app_yaml

    compile(materialized, str(output / "app.py"), "exec")


def test_bundle_manifest_records_materialized_contract(tmp_path):
    output = build_test_bundle(tmp_path)
    manifest = json.loads(
        (output / "ikf_bundle_manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["bundle_contract"] == "IKF_DATABRICKS_APP_BUNDLE_V0.8"
    assert manifest["adoption_version"].startswith("IKF_APP_SHARED_POLICY_ADOPTION_")
    assert manifest["files_api_download_adoption_version"].startswith(
        "IKF_APP_FILES_API_DOWNLOAD_"
    )
    assert manifest["audio_adoption_version"].startswith("IKF_APP_AUDIO_ADOPTION_")
    assert manifest["audio_fixup_version"].startswith("IKF_APP_AUDIO_FIXUP_")
    assert manifest["timeline_adoption_version"] == "IKF_APP_TIMELINE_ADOPTION_V0.3"
    assert manifest["ui_adoption_version"].startswith("IKF_APP_UI_ADOPTION_")
    assert manifest["workflow_adoption_version"] == "IKF_APP_WORKFLOW_ADOPTION_V0.1"
    assert manifest["simplification_adoption_version"] == (
        "IKF_APP_SIMPLIFICATION_ADOPTION_V0.1"
    )
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
    assert set(manifest["applied_files_api_adoptions"]) == {
        "files_api_transport_imports",
        "ranged_files_api_download",
    }
    assert set(manifest["applied_audio_adoptions"]) == {
        "transcription_job_environment",
        "transcription_governance_import",
        "app_access_is_type_d_audio_boundary",
        "user_scoped_audio_and_transcript_files_api",
        "transcription_job_orchestration",
        "transcript_review_publication",
        "class_d_transcript_catalogue_scope",
        "single_transcription_workspace",
        "reviewed_transcript_decryption",
    }
    assert set(manifest["applied_timeline_adoptions"]) == {
        "timeline_imports",
        "timeline_store_helpers",
        "default_graph_chronology_projection",
        "chronology_conflict_detection",
        "audio_absolute_alignment",
        "evidence_based_timeline_conclusion",
        "timeline_tab",
        "timeline_home_card",
        "timeline_workspace",
    }
    assert set(manifest["applied_ui_adoptions"]) == {
        "html_escape_import",
        "active_analysis_header",
        "ask_llms_title",
        "ask_refresh_beside_question",
        "compact_relationship_review",
    }
    assert set(manifest["applied_workflow_adoptions"]) == {
        "analysis_description_explanation",
        "ask_history_before_question",
        "findings_brief_summary",
        "remove_emcip_ui",
        "shield_factor_mapping_view",
        "reviewed_graph_projection",
        "remove_graph_questions",
        "workflow_wording_cleanup",
    }
    assert set(manifest["applied_simplification_adoptions"]) == {
        "remove_stale_app_build_label",
        "remove_legacy_transcript_reviewer_allowlist",
        "compact_governance_notices",
        "remove_ikg_ollama_user_wording",
        "remove_static_validation_milestone",
        "remove_legacy_emcip_tab_alias",
        "clarify_audio_workspace_label",
    }
    assert manifest["shared_package_path"] == "src/ikf"


def test_bundled_bootstrap_prefers_materialized_source(tmp_path):
    output = build_test_bundle(tmp_path)
    bootstrap = (output / "bootstrap.py").read_text(encoding="utf-8")

    assert 'APP_DIR / "src"' in bootstrap
    assert "MATERIALIZED_MARKER" in bootstrap
    assert "transform_app_files_api_source" in bootstrap
    assert "transform_app_audio_source" in bootstrap
    assert "transform_app_audio_fixup_source" in bootstrap
    assert "transform_app_timeline_source" in bootstrap
    assert "transform_app_workflow_source" in bootstrap
    assert "transform_app_simplification_source" in bootstrap
    assert (output / "src" / "ikf").is_dir()
