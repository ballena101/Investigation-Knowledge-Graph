"""Execute only the selected top-level IKF capability.

Streamlit renders code placed inside all top-level ``st.tabs`` containers on
every script rerun. IKF now has several data-heavy capabilities, so that eager
execution causes inactive pages to query Neo4j, SQL and build UI unnecessarily.

This transform is deliberately applied last. It preserves the existing
capability bodies, widget keys, inner Ask tabs and fragments, changing only the
top-level execution guard.
"""

from __future__ import annotations

import re


LAZY_NAVIGATION_VERSION = "IKF_LAZY_CAPABILITY_NAVIGATION_V0.1.1"


# These are the user-visible labels after the existing UI/simplification passes.
CAPABILITIES = (
    "Home",
    "News & Alerts",
    "Audio transcription",
    "Analyse Documents",
    "Findings & Evidence",
    "Knowledge Graph",
    "Ask LLMs",
    "Review & Validate",
    "Terms of reference",
)


def _replace_exact(source: str, old: str, new: str, name: str, *, expected: int = 1) -> str:
    count = source.count(old)
    if count != expected:
        raise RuntimeError(
            f"Lazy navigation transform failed at {name}: "
            f"expected {expected} match(es), found {count}."
        )
    return source.replace(old, new)


def transform_app_lazy_navigation(source: str):
    """Replace eager top-level tabs with one lazily executed capability."""

    applied = []

    # Match the navigation by stable variable structure, not wording. Earlier
    # presentation passes legitimately rename user-visible labels.
    tab_pattern = re.compile(
        r"\(\n"
        r"    tab_home,\n"
        r"    tab_news,\n"
        r"    tab_transcriptions,\n"
        r"    tab_new_analysis,\n"
        r"    tab_findings,\n"
        r"    tab_knowledge_graph,\n"
        r"    tab_analyses,\n"
        r"    tab_review,\n"
        r"    tab_about,\n"
        r"\) = st\.tabs\(\n"
        r"    \[\n"
        r"(?:        \"[^\"]+\",\n){9}"
        r"    \]\n"
        r"\)\n"
    )

    selector = '''# LAZY_CAPABILITY_NAVIGATION
# Only the selected top-level capability executes on each Streamlit rerun.
# Existing widget keys, fragments, job triggers and governance controls remain
# inside their original capability bodies.
active_capability = st.radio(
    "Capability",
    options=[
        "Home",
        "News & Alerts",
        "Audio transcription",
        "Analyse Documents",
        "Findings & Evidence",
        "Knowledge Graph",
        "Ask LLMs",
        "Review & Validate",
        "Terms of reference",
    ],
    horizontal=True,
    key="ikf_active_capability",
    label_visibility="collapsed",
)
'''

    source, tab_count = tab_pattern.subn(selector, source, count=1)
    if tab_count != 1:
        raise RuntimeError(
            "Lazy navigation transform failed at top-level capability selector: "
            f"expected one top-level tabs block, found {tab_count}."
        )
    applied.append("top_level_tabs_replaced_with_single_capability_selector")

    single_guards = {
        "with tab_home:\n": 'if active_capability == "Home":\n',
        "with tab_news:\n": 'if active_capability == "News & Alerts":\n',
        "with tab_transcriptions:\n": 'if active_capability == "Audio transcription":\n',
        "with tab_new_analysis:\n": 'if active_capability == "Analyse Documents":\n',
        "with tab_findings:\n": 'if active_capability == "Findings & Evidence":\n',
        "with tab_knowledge_graph:\n": 'if active_capability == "Knowledge Graph":\n',
        "with tab_analyses:\n": 'if active_capability == "Ask LLMs":\n',
        "with tab_about:\n": 'if active_capability == "Terms of reference":\n',
    }

    for old, new in single_guards.items():
        source = _replace_exact(source, old, new, old.strip())

    # At this final transform stage the old EMCIP alias and the separate SHIELD
    # UI have already been removed by existing workflow/visual refinements. The
    # two remaining review sections are relationship review and optional quality
    # review; both stay under Review & Validate.
    source = _replace_exact(
        source,
        "with tab_review:\n",
        'if active_capability == "Review & Validate":\n',
        "review capability guards",
        expected=2,
    )

    if "with tab_mapping_review:\n" in source:
        raise RuntimeError(
            "Lazy navigation found a legacy mapping-review tab after final UI transforms."
        )

    applied.extend(
        [
            "inactive_capability_bodies_do_not_execute",
            "ask_inner_tabs_preserved",
            "review_sections_preserved_under_one_capability",
        ]
    )

    forbidden = (
        "with tab_home:",
        "with tab_news:",
        "with tab_transcriptions:",
        "with tab_new_analysis:",
        "with tab_findings:",
        "with tab_knowledge_graph:",
        "with tab_analyses:",
        "with tab_review:",
        "with tab_mapping_review:",
        "with tab_about:",
    )
    leftovers = [item for item in forbidden if item in source]
    if leftovers:
        raise RuntimeError(
            "Lazy navigation transform left eager top-level tab guards: "
            + ", ".join(leftovers)
        )

    compile(source, "<ikf-lazy-navigation>", "exec")
    return source, tuple(applied)
