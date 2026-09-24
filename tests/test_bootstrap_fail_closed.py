from pathlib import Path
import runpy
import shutil

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_bootstrap_fails_closed_when_shared_policy_package_is_missing(tmp_path):
    shutil.copy2(REPO_ROOT / "app" / "bootstrap.py", tmp_path / "bootstrap.py")
    (tmp_path / "app.py").write_text(
        "raise AssertionError('raw app source must not execute')\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match=r"src/ikf is missing"):
        runpy.run_path(str(tmp_path / "bootstrap.py"), run_name="__main__")
