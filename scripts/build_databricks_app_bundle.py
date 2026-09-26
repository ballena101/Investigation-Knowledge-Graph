"""Build the deployable Databricks App source bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = REPO_ROOT / "app"
SRC_ROOT = REPO_ROOT / "src"
IKF_SOURCE = SRC_ROOT / "ikf"
DEFAULT_OUTPUT = REPO_ROOT / "build" / "databricks_app"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ikf.app_adoption import ADOPTION_VERSION, transform_app_source
from ikf.app_files_api_adoption import FILES_API_DOWNLOAD_ADOPTION_VERSION, transform_app_files_api_source
from ikf.app_audio_adoption import AUDIO_ADOPTION_VERSION, transform_app_audio_source
from ikf.app_audio_fixup import AUDIO_FIXUP_VERSION, transform_app_audio_fixup_source
from ikf.app_parakeet_adoption import PARAKEET_ADOPTION_VERSION, transform_app_parakeet_source
from ikf.app_timeline_adoption import TIMELINE_ADOPTION_VERSION, transform_app_timeline_source
from ikf.app_ui_adoption import UI_ADOPTION_VERSION, transform_app_ui_source
from ikf.app_workflow_adoption import WORKFLOW_ADOPTION_VERSION, transform_app_workflow_source
from ikf.app_simplification_adoption import SIMPLIFICATION_ADOPTION_VERSION, transform_app_simplification_source
from ikf.app_news_adoption import NEWS_ADOPTION_VERSION, transform_app_news_source
from ikf.app_branding_adoption import BRANDING_ADOPTION_VERSION, transform_app_branding_source
from ikf.app_operational_refinement import (
    OPERATIONAL_REFINEMENT_VERSION,
    transform_app_operational_refinement,
    _remove_analysis_summary,
    _apply_news_refinement,
)
from ikf.app_similarity_refinement import (
    SIMILARITY_REFINEMENT_VERSION,
    transform_app_similarity_refinement,
)
from ikf.app_visual_refinement import (
    VISUAL_REFINEMENT_VERSION,
    transform_app_visual_refinement,
)
from ikf.app_direct_text_classification_guard import (
    DIRECT_TEXT_CLASSIFICATION_GUARD_VERSION,
    transform_app_direct_text_classification_guard,
)
from ikf.app_pseudonymisation_adoption import (
    PSEUDONYMISATION_ADOPTION_VERSION,
    transform_app_pseudonymisation_source,
)
from ikf.app_pseudonymisation_persistence import (
    PSEUDONYMISATION_PERSISTENCE_VERSION,
    transform_app_pseudonymisation_persistence,
)
from ikf.app_lazy_navigation import (
    LAZY_NAVIGATION_VERSION,
    transform_app_lazy_navigation,
)

COPIED_APP_FILES = ("bootstrap.py", "app.yaml", "requirements.txt")
MATERIALIZED_MARKER = ".ikf_shared_policy_materialized"
MANIFEST_NAME = "ikf_bundle_manifest.json"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _apply_similar_cases_wording_compatibly(source: str) -> str:
    old_scope = (
        '            "Deterministic lexical retrieval from processed case concepts. "\n'
        '            "No embedding or LLM similarity score is used."'
    )
    new_scope = (
        '            "Search scope: all processed MAIRA INVESTIGATION / MAIN_REPORT passages "\n'
        '            "with canonical passages; the current report package is excluded. "\n'
        '            "Matching is deterministic and lexical over existing case concepts. "\n'
        '            "No embedding or LLM similarity score is used at this stage."'
    )
    if old_scope in source:
        source = source.replace(old_scope, new_scope, 1)

    old_news = (
        '            "External/news similarity remains separate from validated "\n'
        '            "investigation knowledge and is handled in the News/dashboard "\n'
        '            "workstream."'
    )
    new_news = (
        '            "Recent alerts remain external, unverified intelligence. In News & Alerts, "\n'
        '            "use ‘Related to active analysis only’ for deterministic lexical screening "\n'
        '            "against active-analysis concepts; this does not turn an alert into evidence."'
    )
    if old_news in source:
        source = source.replace(old_news, new_news, 1)
    return source


def _apply_operational_refinement_compatibly(source: str) -> tuple[str, tuple[str, ...]]:
    """Apply operational refinements without replaying an already-materialized quota migration."""

    quota_already_current = (
        "MODEL_DAILY_LIMITS" in source
        or "def get_gpt20_daily_usage" in source
        or "GPT20_DAILY_QUESTION_LIMIT" in source
    )

    if not quota_already_current:
        return transform_app_operational_refinement(source)

    applied = [
        "class_d_ask_quotas_already_present_in_source",
        "analysis_runs_do_not_consume_ask_quota_already_present_in_source",
    ]

    if 'st.markdown("### Analysis summary")' in source:
        source = _remove_analysis_summary(source)
        applied.append("analysis_summary_findings_only")

    source = _apply_news_refinement(source)
    applied.extend(
        [
            "news_triage_semantics_and_filters",
            "news_active_analysis_lexical_relevance",
            "news_unique_fatal_alert_count",
        ]
    )

    source = _apply_similar_cases_wording_compatibly(source)
    applied.append("similar_cases_full_processed_maira_scope_wording")
    return source, tuple(applied)


def build_bundle(output: Path) -> Path:
    output = output.resolve()
    repo_root = REPO_ROOT.resolve()
    app_source = APP_SOURCE.resolve()
    if output == repo_root or output == app_source or app_source in output.parents:
        raise ValueError("Refusing to overwrite repository source directories.")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    for name in COPIED_APP_FILES:
        source = APP_SOURCE / name
        if not source.is_file():
            raise FileNotFoundError(f"Missing required App source file: {source}")
        shutil.copy2(source, output / name)

    original_app_source = (APP_SOURCE / "app.py").read_text(encoding="utf-8")
    transformed_app_source, applied_policy = transform_app_source(original_app_source)
    transformed_app_source, applied_files_api = transform_app_files_api_source(transformed_app_source)
    transformed_app_source, applied_audio = transform_app_audio_source(transformed_app_source)
    transformed_app_source, applied_timeline = transform_app_timeline_source(transformed_app_source)
    transformed_app_source, applied_ui = transform_app_ui_source(transformed_app_source)
    transformed_app_source, applied_workflow = transform_app_workflow_source(transformed_app_source)
    transformed_app_source, applied_simplification = transform_app_simplification_source(transformed_app_source)
    transformed_app_source, applied_parakeet = transform_app_parakeet_source(transformed_app_source)
    transformed_app_source, applied_audio_fixup = transform_app_audio_fixup_source(transformed_app_source)
    transformed_app_source, applied_news = transform_app_news_source(transformed_app_source)
    transformed_app_source, applied_branding = transform_app_branding_source(transformed_app_source)
    transformed_app_source, applied_operational = _apply_operational_refinement_compatibly(transformed_app_source)
    transformed_app_source, applied_similarity = transform_app_similarity_refinement(transformed_app_source)
    transformed_app_source, applied_visual = transform_app_visual_refinement(transformed_app_source)
    transformed_app_source, applied_classification = transform_app_direct_text_classification_guard(transformed_app_source)
    transformed_app_source, applied_pseudonymisation = transform_app_pseudonymisation_source(transformed_app_source)
    transformed_app_source, applied_pseudonymisation_persistence = transform_app_pseudonymisation_persistence(
        transformed_app_source
    )
    # Navigation is deliberately last: all prior transforms retain their
    # established top-level tab anchors, then inactive capabilities are gated.
    transformed_app_source, applied_lazy_navigation = transform_app_lazy_navigation(
        transformed_app_source
    )
    compile(transformed_app_source, str(output / "app.py"), "exec")
    (output / "app.py").write_text(transformed_app_source, encoding="utf-8")

    bundle_package = output / "src" / "ikf"
    shutil.copytree(IKF_SOURCE, bundle_package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))

    marker = output / MATERIALIZED_MARKER
    marker.write_text("\n".join([
        ADOPTION_VERSION, FILES_API_DOWNLOAD_ADOPTION_VERSION, AUDIO_ADOPTION_VERSION,
        AUDIO_FIXUP_VERSION, TIMELINE_ADOPTION_VERSION, UI_ADOPTION_VERSION,
        WORKFLOW_ADOPTION_VERSION, SIMPLIFICATION_ADOPTION_VERSION, PARAKEET_ADOPTION_VERSION,
        NEWS_ADOPTION_VERSION, BRANDING_ADOPTION_VERSION, OPERATIONAL_REFINEMENT_VERSION,
        SIMILARITY_REFINEMENT_VERSION, VISUAL_REFINEMENT_VERSION,
        DIRECT_TEXT_CLASSIFICATION_GUARD_VERSION, PSEUDONYMISATION_ADOPTION_VERSION,
        PSEUDONYMISATION_PERSISTENCE_VERSION, LAZY_NAVIGATION_VERSION,
    ]) + "\n", encoding="utf-8")

    manifest = {
        "bundle_contract": "IKF_DATABRICKS_APP_BUNDLE_V0.16",
        "adoption_version": ADOPTION_VERSION,
        "files_api_download_adoption_version": FILES_API_DOWNLOAD_ADOPTION_VERSION,
        "audio_adoption_version": AUDIO_ADOPTION_VERSION,
        "audio_fixup_version": AUDIO_FIXUP_VERSION,
        "parakeet_adoption_version": PARAKEET_ADOPTION_VERSION,
        "timeline_adoption_version": TIMELINE_ADOPTION_VERSION,
        "ui_adoption_version": UI_ADOPTION_VERSION,
        "workflow_adoption_version": WORKFLOW_ADOPTION_VERSION,
        "simplification_adoption_version": SIMPLIFICATION_ADOPTION_VERSION,
        "news_adoption_version": NEWS_ADOPTION_VERSION,
        "branding_adoption_version": BRANDING_ADOPTION_VERSION,
        "operational_refinement_version": OPERATIONAL_REFINEMENT_VERSION,
        "similarity_refinement_version": SIMILARITY_REFINEMENT_VERSION,
        "visual_refinement_version": VISUAL_REFINEMENT_VERSION,
        "direct_text_classification_guard_version": DIRECT_TEXT_CLASSIFICATION_GUARD_VERSION,
        "pseudonymisation_adoption_version": PSEUDONYMISATION_ADOPTION_VERSION,
        "pseudonymisation_persistence_version": PSEUDONYMISATION_PERSISTENCE_VERSION,
        "lazy_navigation_version": LAZY_NAVIGATION_VERSION,
        "source_app_sha256": _sha256_text(original_app_source),
        "materialized_app_sha256": _sha256_text(transformed_app_source),
        "applied_policy_adoptions": list(applied_policy),
        "applied_files_api_adoptions": list(applied_files_api),
        "applied_audio_adoptions": list(applied_audio) + list(applied_audio_fixup),
        "applied_parakeet_adoptions": list(applied_parakeet),
        "applied_timeline_adoptions": list(applied_timeline),
        "applied_ui_adoptions": list(applied_ui),
        "applied_workflow_adoptions": list(applied_workflow),
        "applied_simplification_adoptions": list(applied_simplification),
        "applied_news_adoptions": list(applied_news),
        "applied_branding_adoptions": list(applied_branding),
        "applied_operational_refinements": list(applied_operational),
        "applied_similarity_refinements": list(applied_similarity),
        "applied_visual_refinements": list(applied_visual),
        "applied_classification_guards": list(applied_classification),
        "applied_pseudonymisation_adoptions": list(applied_pseudonymisation),
        "applied_pseudonymisation_persistence": list(applied_pseudonymisation_persistence),
        "applied_lazy_navigation": list(applied_lazy_navigation),
        "shared_package_path": "src/ikf",
    }
    (output / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    required = [
        output / "app.py", output / "bootstrap.py", output / "app.yaml", output / "requirements.txt",
        marker, output / MANIFEST_NAME,
        bundle_package / "app_adoption.py", bundle_package / "app_files_api_adoption.py",
        bundle_package / "app_audio_adoption.py", bundle_package / "app_audio_fixup.py",
        bundle_package / "app_parakeet_adoption.py", bundle_package / "app_timeline_adoption.py",
        bundle_package / "app_ui_adoption.py", bundle_package / "app_workflow_adoption.py",
        bundle_package / "app_simplification_adoption.py", bundle_package / "app_news_adoption.py",
        bundle_package / "app_branding_adoption.py", bundle_package / "app_operational_refinement.py",
        bundle_package / "app_similarity_refinement.py", bundle_package / "app_visual_refinement.py",
        bundle_package / "app_direct_text_classification_guard.py",
        bundle_package / "app_pseudonymisation_adoption.py",
        bundle_package / "app_pseudonymisation_persistence.py",
        bundle_package / "app_lazy_navigation.py",
        bundle_package / "pseudonymisation.py", bundle_package / "pseudonymisation_sources.py",
        bundle_package / "pseudonymised_source.py",
        bundle_package / "timeline.py", bundle_package / "transcription_governance.py",
        bundle_package / "source_routing.py", bundle_package / "evidence_locations.py",
        bundle_package / "question_scope.py", bundle_package / "review_governance.py",
        bundle_package / "shield_governance.py", bundle_package / "emcip_governance.py",
        bundle_package / "graph_governance.py", bundle_package / "retention.py",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("Incomplete App bundle: " + ", ".join(missing))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = build_bundle(args.output)
    print(f"Databricks App bundle ready: {output}")


if __name__ == "__main__":
    main()
