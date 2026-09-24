"""Deterministic UI source transformations for the IKF Streamlit App.

These transformations are deliberately separated from governance adoption. They
only change investigator-facing presentation and are applied both by the raw
bootstrap path and by the materialized Databricks App bundle builder.
"""

from __future__ import annotations

import re


UI_ADOPTION_VERSION = "IKF_APP_UI_ADOPTION_V0.1"


_ACTIVE_ANALYSIS_PATTERN = re.compile(
    r"        h1, h2, h3, h4 = st\.columns\(\n"
    r"(?:.|\n)*?"
    r"        h4\.metric\(\n"
    r"            \"Status\",\n"
    r"            active_analysis\.get\(\n"
    r"                \"status\"\n"
    r"            \)\n"
    r"            or \"UNKNOWN\",\n"
    r"        \)\n",
)


_ACTIVE_ANALYSIS_REPLACEMENT = '''        h1, h2, h3, h4 = st.columns(
            [2.6, 0.7, 0.8, 1.0]
        )
        active_analysis_title = html.escape(
            str(
                active_analysis.get(
                    "analysis_title"
                )
                or active_analysis_id
            )
        )
        active_analysis_class = html.escape(
            str(
                active_analysis.get(
                    "information_class"
                )
                or "—"
            )
        )
        active_analysis_sources = html.escape(
            "Text"
            if active_analysis.get(
                "input_mode"
            ) == "DIRECT_TEXT"
            else str(
                active_analysis.get(
                    "document_count"
                )
                or 0
            )
        )
        active_analysis_status = html.escape(
            str(
                active_analysis.get(
                    "status"
                )
                or "UNKNOWN"
            )
        )

        with h1:
            st.markdown(
                (
                    '<div style="font-size:1.05rem;font-weight:700;'
                    'color:#1f77b4;line-height:1.3;margin-top:0.18rem;">'
                    f'Active analysis: {active_analysis_title}</div>'
                ),
                unsafe_allow_html=True,
            )
            st.caption(
                "ID: " + active_analysis_id
            )

        h2.markdown(
            (
                '<div style="font-size:0.70rem;color:#6b7280;line-height:1.1;">Class</div>'
                '<div style="font-size:1.05rem;font-weight:600;line-height:1.3;">'
                f'{active_analysis_class}</div>'
            ),
            unsafe_allow_html=True,
        )
        h3.markdown(
            (
                '<div style="font-size:0.70rem;color:#6b7280;line-height:1.1;">Sources</div>'
                '<div style="font-size:1.05rem;font-weight:600;line-height:1.3;">'
                f'{active_analysis_sources}</div>'
            ),
            unsafe_allow_html=True,
        )
        h4.markdown(
            (
                '<div style="font-size:0.70rem;color:#6b7280;line-height:1.1;">Status</div>'
                '<div style="font-size:1.05rem;font-weight:600;line-height:1.3;">'
                f'{active_analysis_status}</div>'
            ),
            unsafe_allow_html=True,
        )
'''


def transform_app_ui_source(source: str) -> tuple[str, tuple[str, ...]]:
    """Apply strict presentation-only transformations to the App source."""

    applied: list[str] = []

    if "import html\n" not in source:
        import_anchor = "import hashlib\n"
        if import_anchor not in source:
            raise RuntimeError(
                "IKF App UI adoption could not locate the import anchor."
            )
        source = source.replace(
            import_anchor,
            import_anchor + "import html\n",
            1,
        )
        applied.append("html_escape_import")

    source, count = _ACTIVE_ANALYSIS_PATTERN.subn(
        _ACTIVE_ANALYSIS_REPLACEMENT,
        source,
        count=1,
    )
    if count != 1:
        raise RuntimeError(
            "IKF App UI adoption failed at active-analysis header: "
            f"expected exactly one match, found {count}."
        )
    applied.append("active_analysis_header")

    return source, tuple(applied)
