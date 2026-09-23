"""Tests for the derived Databricks App deployment bundle."""

from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDER = REPO_ROOT / "scripts" / "build_databricks_app_bundle.py"


def test_bundle_contains_app_and_canonical_ikf_package(tmp_path):
    output = tmp_path / "ikf_app"

    subprocess.run(
        [sys.executable, str(BUILDER), "--output", str(output)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert (output / "app.py").is_file()
    assert (output / "bootstrap.py").is_file()
    assert (output / "app.yaml").is_file()
    assert (output / "requirements.txt").is_file()

    shared = output / "src" / "ikf"
    for name in (
        "app_adoption.py",
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


def test_bundled_bootstrap_can_find_packaged_src(tmp_path):
    output = tmp_path / "ikf_app"

    subprocess.run(
        [sys.executable, str(BUILDER), "--output", str(output)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    bootstrap = (output / "bootstrap.py").read_text(encoding="utf-8")
    assert 'APP_DIR / "src"' in bootstrap
    assert (output / "src" / "ikf").is_dir()
