"""Build the deployable IKF Databricks App source bundle.

The generated bundle contains the investigator-facing App files plus the
canonical ``src/ikf`` package. This prevents Databricks deployment from falling
back to duplicated policy logic when only the App source folder is uploaded.

The bundle is a derived artefact and is not committed to GitHub.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = REPO_ROOT / "app"
IKF_SOURCE = REPO_ROOT / "src" / "ikf"
DEFAULT_OUTPUT = REPO_ROOT / "build" / "databricks_app"

APP_FILES = (
    "app.py",
    "bootstrap.py",
    "app.yaml",
    "requirements.txt",
)


def build_bundle(output: Path) -> Path:
    output = output.resolve()

    if output == REPO_ROOT.resolve() or REPO_ROOT.resolve() in output.parents and output == APP_SOURCE.resolve():
        raise ValueError("Refusing to overwrite repository source directories.")

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    for name in APP_FILES:
        source = APP_SOURCE / name
        if not source.is_file():
            raise FileNotFoundError(f"Missing required App source file: {source}")
        shutil.copy2(source, output / name)

    bundle_package = output / "src" / "ikf"
    shutil.copytree(
        IKF_SOURCE,
        bundle_package,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    required = [
        output / "app.py",
        output / "bootstrap.py",
        output / "app.yaml",
        output / "requirements.txt",
        bundle_package / "app_adoption.py",
        bundle_package / "source_routing.py",
        bundle_package / "question_scope.py",
        bundle_package / "review_governance.py",
        bundle_package / "shield_governance.py",
        bundle_package / "emcip_governance.py",
        bundle_package / "graph_governance.py",
        bundle_package / "retention.py",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("Incomplete App bundle: " + ", ".join(missing))

    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output directory for the derived Databricks App source bundle.",
    )
    args = parser.parse_args()

    output = build_bundle(args.output)
    print(f"IKF Databricks App bundle ready: {output}")


if __name__ == "__main__":
    main()
