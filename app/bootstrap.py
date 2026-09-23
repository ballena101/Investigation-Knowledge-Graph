"""Databricks App bootstrap.

Keeps the Streamlit entrypoint small while making the repository's canonical
``src/ikf`` package importable when the App is deployed from the repository
checkout. The existing ``app.py`` remains the user-facing application during
the incremental refactor.

The bootstrap is intentionally behavior-preserving: if the sibling ``src``
directory is not present in a particular deployment bundle, the legacy App can
still start because no shared-module import is forced here.
"""

from __future__ import annotations

from pathlib import Path
import runpy
import sys


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
SRC_DIR = REPO_ROOT / "src"

if SRC_DIR.is_dir():
    src_text = str(SRC_DIR)
    if src_text not in sys.path:
        sys.path.insert(0, src_text)

runpy.run_path(str(APP_DIR / "app.py"), run_name="__main__")
