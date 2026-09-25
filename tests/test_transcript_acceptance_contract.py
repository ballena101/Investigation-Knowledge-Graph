"""Regression guard for accepting and publishing reviewed Class-D transcripts."""

from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDER = REPO_ROOT / "scripts" / "build_databricks_app_bundle.py"


def test_materialized_app_keeps_only_publication_aware_transcript_review(tmp_path):
    output = tmp_path / "ikf_app"
    subprocess.run(
        [sys.executable, str(BUILDER), "--output", str(output)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    app_source = (output / "app.py").read_text(encoding="utf-8")

    assert app_source.count("def save_transcript_review") == 1
    assert (
        "def save_transcript_review(record, reviewed_text, analysis_context_id=None):"
        in app_source
    )
    assert "r.analysis_context_id = $analysis_context_id" in app_source
    assert "analysis_context_id=analysis_context_id" in app_source
    assert "review = save_transcript_review(" in app_source
    assert 'review["review_id"]' in app_source
    assert "def save_transcript_review(record, reviewed_text):" not in app_source
