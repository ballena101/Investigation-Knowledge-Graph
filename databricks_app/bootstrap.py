"""Databricks App bootstrap for deterministic App transforms."""

from __future__ import annotations

from pathlib import Path
import sys


APP_DIR = Path(__file__).resolve().parent
APP_FILE = APP_DIR / "app.py"
MATERIALIZED_MARKER = APP_DIR / ".ikf_shared_policy_materialized"

SRC_CANDIDATES = (APP_DIR.parent / "src", APP_DIR / "src")
SRC_DIR = next(
    (candidate for candidate in SRC_CANDIDATES if (candidate / "ikf").is_dir()),
    None,
)

source = APP_FILE.read_text(encoding="utf-8")

if SRC_DIR is None:
    raise RuntimeError(
        "Invalid App deployment: the canonical shared policy package src/ikf is "
        "missing. Deploy the generated Databricks App bundle produced by "
        "`python scripts/build_databricks_app_bundle.py`."
    )

src_text = str(SRC_DIR)
if src_text not in sys.path:
    sys.path.insert(0, src_text)

if not MATERIALIZED_MARKER.is_file():
    from ikf.app_adoption import transform_app_source
    from ikf.app_files_api_adoption import transform_app_files_api_source
    from ikf.app_audio_adoption import transform_app_audio_source
    from ikf.app_audio_fixup import transform_app_audio_fixup_source
    from ikf.app_parakeet_adoption import transform_app_parakeet_source
    from ikf.app_timeline_adoption import transform_app_timeline_source
    from ikf.app_ui_adoption import transform_app_ui_source
    from ikf.app_workflow_adoption import transform_app_workflow_source
    from ikf.app_simplification_adoption import transform_app_simplification_source
    from ikf.app_news_adoption import transform_app_news_source
    from ikf.app_branding_adoption import transform_app_branding_source
    from ikf.app_operational_refinement import transform_app_operational_refinement
    from ikf.app_similarity_refinement import transform_app_similarity_refinement
    from ikf.app_direct_text_classification_guard import (
        transform_app_direct_text_classification_guard,
    )
    from ikf.app_pseudonymisation_adoption import (
        transform_app_pseudonymisation_source,
    )
    from ikf.app_pseudonymisation_persistence import (
        transform_app_pseudonymisation_persistence,
    )
    from ikf.app_lazy_navigation import (
        transform_app_lazy_navigation,
    )

    source, _ = transform_app_source(source)
    source, _ = transform_app_files_api_source(source)
    source, _ = transform_app_audio_source(source)
    source, _ = transform_app_timeline_source(source)
    source, _ = transform_app_ui_source(source)
    source, _ = transform_app_workflow_source(source)
    source, _ = transform_app_simplification_source(source)
    source, _ = transform_app_parakeet_source(source)
    source, _ = transform_app_audio_fixup_source(source)
    source, _ = transform_app_news_source(source)
    source, _ = transform_app_branding_source(source)
    source, _ = transform_app_operational_refinement(source)
    source, _ = transform_app_similarity_refinement(source)
    source, _ = transform_app_direct_text_classification_guard(source)
    source, _ = transform_app_pseudonymisation_source(source)
    source, _ = transform_app_pseudonymisation_persistence(source)
    # Apply navigation last so every earlier capability transform still sees
    # the original tab anchors it was designed to modify.
    source, _ = transform_app_lazy_navigation(source)

code = compile(source, str(APP_FILE), "exec")
exec(code, {"__name__": "__main__", "__file__": str(APP_FILE)})
