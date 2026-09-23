"""Databricks App bootstrap for incremental shared-policy adoption.

The canonical deterministic governance logic lives in ``src/ikf``. During the
transition away from the historical monolithic ``app.py``, this bootstrap
loads that package and applies a strict, tested source transformation so the
running App calls the shared policy modules without requiring a risky one-shot
rewrite of the full Streamlit application.

Two source layouts are supported:

1. repository checkout: ``app/`` beside ``src/``;
2. generated Databricks App bundle: ``src/`` inside the deployed App folder.

If neither layout contains the shared package, the legacy App still starts
unchanged. That fallback is temporary and should be removed once the generated
bundle is the only supported deployment source.
"""

from __future__ import annotations

from pathlib import Path
import sys


APP_DIR = Path(__file__).resolve().parent
APP_FILE = APP_DIR / "app.py"

SRC_CANDIDATES = (
    APP_DIR.parent / "src",
    APP_DIR / "src",
)
SRC_DIR = next(
    (candidate for candidate in SRC_CANDIDATES if (candidate / "ikf").is_dir()),
    None,
)

source = APP_FILE.read_text(encoding="utf-8")

if SRC_DIR is not None:
    src_text = str(SRC_DIR)
    if src_text not in sys.path:
        sys.path.insert(0, src_text)

    from ikf.app_adoption import transform_app_source

    source, _applied_policy_adoptions = transform_app_source(source)

code = compile(source, str(APP_FILE), "exec")
exec(code, {"__name__": "__main__", "__file__": str(APP_FILE)})
