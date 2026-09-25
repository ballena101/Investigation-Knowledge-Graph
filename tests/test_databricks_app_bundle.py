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
    for name in (
        "app.py", "bootstrap.py", "app.yaml", "requirements.txt",
        ".ikf_shared_policy_materialized", "ikf_bundle_manifest.json",
    ):
        assert (output / name).is_file(), name

    shared = output / "src" / "ikf"
    for name in (
        "app_adoption.py", "app_files_api_adoption.py", "app_audio_adoption.py",
        "app_audio_fixup.py", "app_parakeet_adoption.py", "app_timeline_adoption.py",
        "app_ui_adoption.py", "app_workflow_adoption.py", "app_simplification_adoption.py",
        "app_news_adoption.py", "app_branding_adoption.py",
        "timeline.py", "transcription_governance.py", "source_routing.py",
        "evidence_locations.py", "question_scope.py", "review_governance.py",
        "shield_governance.py", "emcip_governance.py", "graph_governance.py", "retention.py",
    ):
        assert (shared / name).is_file(), name


def test_bundle_materializes_governed_investigator_workflow(tmp_path):
    output = build_test_bundle(tmp_path)
    materialized = (output / "app.py").read_text(encoding="utf-8")

    assert 'page_title="Safety Investigation AI Sandbox"' in materialized
    assert 'st.title("Safety Investigation AI Sandbox")' in materialized
    assert "Safety Investigation Knowledge & AI Support" not in materialized

    assert 'CLASS_D_LLAMA70_ENDPOINT = os.getenv(' in materialized
    assert "CLASS_D_OLLAMA_LLAMA70_URL" not in materialized
    assert "shared_content_retention_hours(information_class)" in materialized
    assert "filter_catalogue_rows(" in materialized
    assert "resolve_effective_document_scope(" in materialized
    assert "validate_human_relationship_review(" in materialized
    assert "validate_app_shield_review(" in materialized
    assert "scope_graph_by_documents(" in materialized

    assert "FILES_API_DOWNLOAD_CHUNK_BYTES = 4 * 1024 * 1024" in materialized
    assert '"Range": f"bytes={start}-{end}"' in materialized
    assert "http.client.IncompleteRead" in materialized

    # User-authored live News & Alerts integration remains materialized.
    assert "import pandas as pd" in materialized
    assert 'SQL_WAREHOUSE_ID = os.getenv("SQL_WAREHOUSE_ID")' in materialized
    assert "bdw_analysis_prod.siana.eu_eea_alerts_hierarchy_v" in materialized
    assert "bdw_marinfo_prod.marinfo5.lot2a_ship" in materialized
    assert "fetch_news_alerts_data" in materialized
    assert "Querying news alerts for the last 7 days" in materialized
    assert "Total alerts" in materialized
    assert "Alert locations" in materialized
    assert "Alerts by vessel type" in materialized
    assert "Daily alert count" in materialized

    assert 'TRANSCRIPTION_JOB_ID = os.getenv(' in materialized
    assert "list_type_d_audio_sources" in materialized
    assert "Transcribe selected audio" in materialized
    assert "Accept validated transcript" in materialized
    assert "CLASS D DOCUMENT AVAILABLE" in materialized
    assert "document_kind = 'TRANSCRIPT'" in materialized
    assert "Audio / reviewed transcript — Class D" not in materialized

    assert "PARAKEET_TDT_06B_V3" in materialized
    assert "NVIDIA Parakeet TDT 0.6B v3" in materialized
    assert "Transcription engine / model" in materialized
    assert "Also run the independent Whisper / Parakeet comparison" in materialized
    assert "Independent ASR comparison" in materialized
    assert "Independent machine outputs, not a consensus transcript" in materialized
    assert "Norwegian and Icelandic" in materialized
    assert "faster-whisper 1.2.1" in materialized
    assert "Transformers 5.17.0" in materialized
    assert "engine_version" in materialized
    assert '(?:large-v3|turbo|parakeet-tdt-0\\.6b-v3)\\.json' in materialized
    assert '(?:large-v3|turbo)\\.json' not in materialized

    assert '"Transcription model capabilities"' in materialized
    assert '"Published languages": "99"' in materialized
    assert '"Published languages": "25 European languages"' in materialized
    assert '"Reference weights": "~1.62 GB"' in materialized
    assert '"Reference weights": "~2.51 GB · ~0.6B parameters"' in materialized
    assert "815.7 s audio in 696.1 s · RTF 0.853" in materialized
    assert "Controlled runtime benchmark pending" in materialized
    assert "Weight-file size is not the same as runtime memory" in materialized
    assert "IKF runtime results are shown only after local validation" in materialized

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
    assert '"Evidence passage"' in materialized
    assert 'with st.expander("Technical evidence IDs", expanded=False):' not in materialized
    assert '"Evidence page"' in materialized
    assert "height=340" in materialized

    assert "### Brief analysis summary" in materialized
    assert "### 2. EMCIP mapping review" not in materialized
    assert "### SHIELD classification of contributing factors" in materialized
    assert '"Contributing factor"' in materialized
    assert '"SHIELD (LLM)"' in materialized

    assert "apply_latest_relationship_reviews_to_graph" in materialized
    assert "rejected relationship(s) hidden" in materialized
    assert 'st.markdown("### Ask about this graph scope")' not in materialized

    assert '"AI routing and information classes"' in materialized
    assert '"Confidentiality, Article 9 and external tools"' in materialized
    assert "Article 9-aligned handling rules" in materialized
    assert "NVIDIA Parakeet TDT 0.6B v3" in materialized
    assert "The application developer does not control those independent" in materialized
    assert "the original recording remains authoritative" in materialized
    assert "TYPE_D_TRANSCRIPT_REVIEWERS" not in materialized
    assert "APP_BUILD" not in materialized
    assert "graph-scoped questions" not in materialized

    assert '"Timeline"' in materialized
    assert "load_default_timeline_projection" in materialized
    assert "Default chronology" in materialized
    assert "SOURCE_ORDER" in materialized
    assert "FOLLOWED_BY" in materialized
    assert "Chronology conflicts / reconciliation" in materialized
    assert "Audio time alignment" in materialized
    assert "Evidence-based conclusion" in materialized
    assert "HUMAN_VALIDATED" in materialized

    app_yaml = (output / "app.yaml").read_text(encoding="utf-8")
    assert "EMCIP_MAPPING_JOB_ID" not in app_yaml
    assert "CLASS_D_OLLAMA_LLAMA70_URL" not in app_yaml
    assert "SQL_WAREHOUSE_ID" in app_yaml
    assert 'value: "372b5b52ba082619"' in app_yaml
    compile(materialized, str(output / "app.py"), "exec")


def test_bundle_manifest_records_materialized_contract(tmp_path):
    output = build_test_bundle(tmp_path)
    manifest = json.loads((output / "ikf_bundle_manifest.json").read_text(encoding="utf-8"))

    assert manifest["bundle_contract"] == "IKF_DATABRICKS_APP_BUNDLE_V0.10"
    assert manifest["parakeet_adoption_version"] == "IKF_APP_PARAKEET_ADOPTION_V0.3"
    assert set(manifest["applied_parakeet_adoptions"]) >= {
        "parakeet_governance_imports",
        "parakeet_transcript_discovery",
        "parakeet_model_selector",
        "independent_dual_engine_queue",
        "independent_asr_comparison",
        "asr_engine_provenance_display",
        "parakeet_confidentiality_disclosure",
    }
    assert manifest["timeline_adoption_version"] == "IKF_APP_TIMELINE_ADOPTION_V0.3"
    assert manifest["ui_adoption_version"] == "IKF_APP_UI_ADOPTION_V0.3"
    assert manifest["workflow_adoption_version"] == "IKF_APP_WORKFLOW_ADOPTION_V0.1"
    assert manifest["simplification_adoption_version"] == "IKF_APP_SIMPLIFICATION_ADOPTION_V0.5"
    assert manifest["news_adoption_version"] == "IKF_APP_NEWS_ADOPTION_V0.1"
    assert manifest["branding_adoption_version"] == "IKF_APP_BRANDING_ADOPTION_V0.1"
    assert set(manifest["applied_news_adoptions"]) == {
        "pandas_news_dependency",
        "sql_warehouse_binding",
        "live_news_query",
        "live_news_tab",
    }
    assert manifest["applied_branding_adoptions"] == ["safety_investigation_ai_sandbox"]
    assert manifest["source_app_sha256"] != manifest["materialized_app_sha256"]
    assert manifest["shared_package_path"] == "src/ikf"


def test_bundled_bootstrap_prefers_materialized_source(tmp_path):
    output = build_test_bundle(tmp_path)
    bootstrap = (output / "bootstrap.py").read_text(encoding="utf-8")

    assert "MATERIALIZED_MARKER" in bootstrap
    assert "transform_app_files_api_source" in bootstrap
    assert "transform_app_audio_source" in bootstrap
    assert "transform_app_audio_fixup_source" in bootstrap
    assert "transform_app_parakeet_source" in bootstrap
    assert "transform_app_timeline_source" in bootstrap
    assert "transform_app_workflow_source" in bootstrap
    assert "transform_app_simplification_source" in bootstrap
    assert "transform_app_news_source" in bootstrap
    assert "transform_app_branding_source" in bootstrap
    assert (output / "src" / "ikf").is_dir()
