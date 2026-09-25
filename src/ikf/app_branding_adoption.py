"""Final user-facing branding and release-safe cleanup for the Databricks App."""

from __future__ import annotations

import re


BRANDING_ADOPTION_VERSION = "IKF_APP_BRANDING_ADOPTION_V0.1"


_LEGACY_TRANSCRIPT_REVIEW_PATTERN = re.compile(
    r'\n\ndef save_transcript_review\(record, reviewed_text\):\n'
    r'    reviewer = get_current_user_key\(\)\n'
    r'    text_hash = hashlib\.sha256\(reviewed_text\.encode\("utf-8"\)\)\.hexdigest\(\)\n'
    r'    with get_driver\(\)\.session\(\) as session:\n'
    r'        session\.run\(\n'
    r'            """\n'
    r'            MERGE \(r:TypeDTranscriptReview \{\n'
    r'                source_sha256: \$source_sha256,\n'
    r'                model: \$model,\n'
    r'                reviewed_text_sha256: \$text_hash\n'
    r'            \}\)\n'
    r'            ON CREATE SET r\.reviewed_by = \$reviewer,\n'
    r"                r\.reviewed_at = datetime\(\), r\.status = 'HUMAN_REVIEWED'\n"
    r'            """,\n'
    r'            source_sha256=record\["source_sha256"\], model=record\["model"\],\n'
    r'            text_hash=text_hash, reviewer=reviewer,\n'
    r'        \)\.consume\(\)\n'
    r'    return text_hash\n',
    re.MULTILINE,
)


def transform_app_branding_source(source: str) -> tuple[str, tuple[str, ...]]:
    """Apply the approved App name and remove one obsolete transcript helper."""

    # The latest App baseline contains the governed publication-aware function
    # earlier in the module. An obsolete review-only helper appears later and,
    # because Python uses the last definition, would otherwise shadow the
    # governed function and reject the analysis_context_id keyword used by the UI.
    source, legacy_review_count = _LEGACY_TRANSCRIPT_REVIEW_PATTERN.subn(
        "",
        source,
        count=1,
    )
    if legacy_review_count != 1:
        raise RuntimeError(
            "Final App adoption expected one obsolete transcript-review helper."
        )

    expected_signature = (
        "def save_transcript_review(record, reviewed_text, analysis_context_id=None):"
    )
    if source.count("def save_transcript_review") != 1:
        raise RuntimeError(
            "Final App adoption requires exactly one transcript-review function."
        )
    if expected_signature not in source:
        raise RuntimeError(
            "Final App adoption could not locate the publication-aware transcript-review function."
        )

    old_title = "Safety Investigation Knowledge & AI Support"
    new_title = "Safety Investigation AI Sandbox"

    page_old = f'page_title="{old_title}"'
    page_new = f'page_title="{new_title}"'
    title_old = f'st.title("{old_title}")'
    title_new = f'st.title("{new_title}")'

    if page_old not in source:
        raise RuntimeError("Branding adoption could not locate the Streamlit page title.")
    if title_old not in source:
        raise RuntimeError("Branding adoption could not locate the visible App title.")

    source = source.replace(page_old, page_new, 1)
    source = source.replace(title_old, title_new, 1)
    return source, ("safety_investigation_ai_sandbox",)
