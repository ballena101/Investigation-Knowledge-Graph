"""Databricks App bootstrap for shared IKF policy modules.

The canonical deterministic governance logic lives in ``src/ikf``.

Supported layouts:

1. repository checkout: ``app/`` beside ``src/`` — the strict transitional
   source transformation is applied in memory;
2. generated Databricks App bundle: ``src/`` inside the deployed App folder
   and ``.ikf_shared_policy_materialized`` present — the App source was already
   transformed during the local bundle build and is executed directly.

The generated bundle is the preferred deployment source because policy
adoption is then validated before any Databricks compute is used.
"""

from __future__ import annotations

from pathlib import Path
import sys


APP_DIR = Path(__file__).resolve().parent
APP_FILE = APP_DIR / "app.py"
MATERIALIZED_MARKER = APP_DIR / ".ikf_shared_policy_materialized"

SRC_CANDIDATES = (
    APP_DIR.parent / "src",
    APP_DIR / "src",
)
SRC_DIR = next(
    (candidate for candidate in SRC_CANDIDATES if (candidate / "ikf").is_dir()),
    None,
)

source = APP_FILE.read_text(encoding="utf-8")

if SRC_DIR is None:
    raise RuntimeError(
        "Invalid IKF App deployment: the canonical shared policy package "
        "src/ikf is missing. Deploy the generated Databricks App bundle "
        "produced by `python scripts/build_databricks_app_bundle.py` rather "
        "than the raw app/ directory. Execution is blocked because running "
        "the raw App without the shared policy package can bypass Class-D "
        "and other governed source transformations."
    )

src_text = str(SRC_DIR)
if src_text not in sys.path:
    sys.path.insert(0, src_text)

if not MATERIALIZED_MARKER.is_file():
    from ikf.app_adoption import transform_app_source

    source, _applied_policy_adoptions = transform_app_source(source)

code = compile(source, str(APP_FILE), "exec")
exec(code, {"__name__": "__main__", "__file__": str(APP_FILE)})
