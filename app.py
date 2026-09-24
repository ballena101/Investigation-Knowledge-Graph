"""Root Databricks App launcher for IKF.

Databricks deploys the repository root from ``main``. Keep the governed
application implementation under ``app/`` while exposing a root Python
entry point so deployment works even when the runtime falls back to locating
an app file at repository root.
"""

from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parent
BOOTSTRAP = ROOT / "app" / "bootstrap.py"

if not BOOTSTRAP.is_file():
    raise RuntimeError(f"IKF App bootstrap not found: {BOOTSTRAP}")

runpy.run_path(str(BOOTSTRAP), run_name="__main__")
