"""Databricks App bootstrap for incremental shared-policy adoption.

The canonical deterministic governance logic lives in ``src/ikf``. During the
transition away from the historical monolithic ``app.py``, this bootstrap
loads that package and applies a strict, tested source transformation so the
running App calls the shared policy modules without requiring a risky one-shot
rewrite of the full Streamlit application.

If the deployment bundle does not contain the repository ``src`` directory,
the legacy App still starts unchanged. That fallback is temporary and should
be removed after the deployment source is confirmed to include the packaged
IKF modules.
"""

from __future__ import annotations

from pathlib import Path
import sys


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
SRC_DIR = REPO_ROOT / "src"
APP_FILE = APP_DIR / "app.py"

source = APP_FILE.read_text(encoding="utf-8")

if SRC_DIR.is_dir():
    src_text = str(SRC_DIR)
    if src_text not in sys.path:
        sys.path.insert(0, src_text)

    from ikf.app_adoption import transform_app_source

    source, _applied_policy_adoptions = transform_app_source(source)

code = compile(source, str(APP_FILE), "exec")
exec(code, {"__name__": "__main__", "__file__": str(APP_FILE)})
