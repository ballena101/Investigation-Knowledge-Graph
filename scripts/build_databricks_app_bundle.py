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

COPIED_APP_FILES = ("bootstrap.py", "app.yaml", "requirements.txt")
MATERIALIZED_MARKER = ".ikf_shared_policy_materialized"
MANIFEST_NAME = "ikf_bundle_manifest.json"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
    compile(transformed_app_source, str(output / "app.py"), "exec")
    (output / "app.py").write_text(transformed_app_source, encoding="utf-8")

    bundle_package = output / "src" / "ikf"
    shutil.copytree(IKF_SOURCE, bundle_package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))

    marker = output / MATERIALIZED_MARKER
    marker.write_text("\n".join([
        ADOPTION_VERSION, FILES_API_DOWNLOAD_ADOPTION_VERSION, AUDIO_ADOPTION_VERSION,
        AUDIO_FIXUP_VERSION, TIMELINE_ADOPTION_VERSION, UI_ADOPTION_VERSION,
        WORKFLOW_ADOPTION_VERSION, SIMPLIFICATION_ADOPTION_VERSION, PARAKEET_ADOPTION_VERSION,
    ]) + "\n", encoding="utf-8")

    manifest = {
        "bundle_contract": "IKF_DATABRICKS_APP_BUNDLE_V0.9",
        "adoption_version": ADOPTION_VERSION,
        "files_api_download_adoption_version": FILES_API_DOWNLOAD_ADOPTION_VERSION,
        "audio_adoption_version": AUDIO_ADOPTION_VERSION,
        "audio_fixup_version": AUDIO_FIXUP_VERSION,
        "parakeet_adoption_version": PARAKEET_ADOPTION_VERSION,
        "timeline_adoption_version": TIMELINE_ADOPTION_VERSION,
        "ui_adoption_version": UI_ADOPTION_VERSION,
        "workflow_adoption_version": WORKFLOW_ADOPTION_VERSION,
        "simplification_adoption_version": SIMPLIFICATION_ADOPTION_VERSION,
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
        bundle_package / "app_simplification_adoption.py", bundle_package / "timeline.py",
        bundle_package / "transcription_governance.py", bundle_package / "source_routing.py",
        bundle_package / "evidence_locations.py", bundle_package / "question_scope.py",
        bundle_package / "review_governance.py", bundle_package / "shield_governance.py",
        bundle_package / "emcip_governance.py", bundle_package / "graph_governance.py",
        bundle_package / "retention.py",
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
