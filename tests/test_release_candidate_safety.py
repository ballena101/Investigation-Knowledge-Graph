"""Static safety guards for the cost-controlled IKF release candidate.

These tests intentionally avoid Databricks. They protect the files that are
supposed to be safe to run before paid integration work begins.
"""

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_YAML = REPO_ROOT / "app" / "app.yaml"
READ_ONLY_NOTEBOOK = (
    REPO_ROOT / "notebooks" / "60_validate_persisted_release_candidate_read_paths.py"
)
COST_AUDIT_SQL = REPO_ROOT / "sql" / "02_databricks_cost_audit.sql"


EXPECTED_APP_ENV_NAMES = {
    "NEO4J_URI",
    "NEO4J_USERNAME",
    "NEO4J_PASSWORD",
    "ANALYSIS_JOB_ID",
    "CLASS_D_ANALYSIS_JOB_ID",
    "ASK_JOB_ID",
    "EMCIP_MAPPING_JOB_ID",
    "SHIELD_PROPOSAL_JOB_ID",
    "RELATIONSHIP_CORRECTION_JOB_ID",
    "SIMILAR_CASES_JOB_ID",
    "CLASS_D_GPT20_ENDPOINT",
    "CLASS_D_LLAMA70_ENDPOINT",
    "CLASS_D_OLLAMA_LLAMA70_URL",
    "DIRECT_TEXT_ENCRYPTION_KEY",
    "IKG_ADMIN_USERS",
    "LLAMA_DAILY_QUESTION_LIMIT",
    "NEWS_DASHBOARD_URL",
    "STREAMLIT_GATHER_USAGE_STATS",
}


def _env_names_from_app_yaml(text: str) -> set[str]:
    return set(re.findall(r"(?m)^\s*- name:\s*([A-Z0-9_]+)\s*$", text))


def test_app_yaml_exposes_expected_release_candidate_environment_contract():
    text = APP_YAML.read_text(encoding="utf-8")
    assert _env_names_from_app_yaml(text) == EXPECTED_APP_ENV_NAMES
    assert "streamlit\n  - run\n  - bootstrap.py" in text


def test_class_d_llama_has_canonical_endpoint_binding():
    text = APP_YAML.read_text(encoding="utf-8")
    assert "name: CLASS_D_LLAMA70_ENDPOINT" in text
    assert "ikf-llama-3-3-70b-poc" in text


def test_notebook_60_remains_read_only_and_no_inference():
    text = READ_ONLY_NOTEBOOK.read_text(encoding="utf-8")
    lower = text.lower()

    forbidden_fragments = (
        ".run_now(",
        "jobs/run-now",
        "serving-endpoints/",
        "chat.completions",
        "foundation model",
        "saveastable(",
        ".write.",
        "insert into ",
        "update ",
        "delete from ",
        "merge into ",
        "create table ",
        "drop table ",
        "detach delete",
        "session.run(",
        "%pip install",
    )

    # Comments describe prohibited actions, so check executable-looking forms
    # rather than generic words such as "model" or "job".
    for fragment in forbidden_fragments:
        assert fragment not in lower, fragment

    assert "spark.table(" in text
    assert "spark.catalog.tableExists(" in text
    assert "PASS — IKF PERSISTED RELEASE-CANDIDATE READ PATHS" in text


def test_cost_audit_sql_remains_select_only():
    text = COST_AUDIT_SQL.read_text(encoding="utf-8")

    # Remove -- comments before checking SQL verbs so explanatory prose cannot
    # create false positives.
    sql = "\n".join(
        line.split("--", 1)[0]
        for line in text.splitlines()
    ).lower()

    forbidden_statements = (
        r"\binsert\s+into\b",
        r"\bupdate\s+[a-z0-9_.]+\s+set\b",
        r"\bdelete\s+from\b",
        r"\bmerge\s+into\b",
        r"\bcreate\s+(?:or\s+replace\s+)?(?:table|view)\b",
        r"\bdrop\s+(?:table|view)\b",
        r"\balter\s+(?:table|view)\b",
        r"\btruncate\s+table\b",
    )
    for pattern in forbidden_statements:
        assert re.search(pattern, sql) is None, pattern

    assert "system.billing.usage" in sql
    assert "system.billing.list_prices" in sql
    assert re.search(r"\bselect\b", sql)
