"""Execute only the selected top-level IKF capability.

Streamlit renders all code placed inside ``st.tabs`` on every script rerun. IKF
has grown into several data-heavy capabilities, so that behaviour causes
inactive pages to query Neo4j, build graphs and prepare UI unnecessarily.

This source transform preserves the existing capability bodies and widget keys,
but changes only their top-level execution guard. Inner tabs and fragments are
left untouched.
"""

from __future__ import annotations


LAZY_NAVIGATION_VERSION = "IKF_LAZY_CAPABILITY_NAVIGATION_V0.1"


CAPABILITIES = (
    "Home",
    "News & Alerts",
    "Transcriptions",
    "Analyse Documents",
    "Findings & Evidence",
    "Knowledge Graph",
    "Ask / Compare LLMs",
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

    tab_block = '''(
    tab_home,
    tab_news,
    tab_transcriptions,
    tab_new_analysis,
    tab_findings,
    tab_knowledge_graph,
    tab_analyses,
    tab_review,
    tab_about,
) = st.tabs(
    [
        "Home",
        "News & Alerts",
        "Transcriptions",
        "Analyse Documents",
        "Findings & Evidence",
        "Knowledge Graph",
        "Ask / Compare LLMs",
        "Review & Validate",
        "Terms of reference",
    ]
)

# Relationship and EMCIP reviews are deliberately presented in one capability.
# Re-entering the same Streamlit tab later appends the mapping-review section.
tab_mapping_review = tab_review
'''

    selector = '''# LAZY_CAPABILITY_NAVIGATION
# Only the selected top-level capability executes on each Streamlit rerun.
# This replaces eager st.tabs execution while preserving all capability bodies,
# widget keys, fragments, job triggers and governance controls.
active_capability = st.radio(
    "Capability",
    options=[
        "Home",
        "News & Alerts",
        "Transcriptions",
        "Analyse Documents",
        "Findings & Evidence",
        "Knowledge Graph",
        "Ask / Compare LLMs",
        "Review & Validate",
        "Terms of reference",
    ],
    horizontal=True,
    key="ikf_active_capability",
    label_visibility="collapsed",
)
'''

    source = _replace_exact(
        source,
        tab_block,
        selector,
        "top-level capability selector",
    )
    applied.append("top_level_tabs_replaced_with_single_capability_selector")

    single_guards = {
        "with tab_home:\n": 'if active_capability == "Home":\n',
        "with tab_news:\n": 'if active_capability == "News & Alerts":\n',
        "with tab_transcriptions:\n": 'if active_capability == "Transcriptions":\n',
        "with tab_new_analysis:\n": 'if active_capability == "Analyse Documents":\n',
        "with tab_findings:\n": 'if active_capability == "Findings & Evidence":\n',
        "with tab_knowledge_graph:\n": 'if active_capability == "Knowledge Graph":\n',
        "with tab_analyses:\n": 'if active_capability == "Ask / Compare LLMs":\n',
        "with tab_about:\n": 'if active_capability == "Terms of reference":\n',
    }

    for old, new in single_guards.items():
        source = _replace_exact(
            source,
            old,
            new,
            old.strip(),
        )

    # Review is intentionally assembled in three consecutive sections:
    # relationship review, optional relationship quality check, and the
    # mapping/SHIELD section that previously reused tab_review via an alias.
    source = _replace_exact(
        source,
        "with tab_review:\n",
        'if active_capability == "Review & Validate":\n',
        "review capability guards",
        expected=2,
    )
    source = _replace_exact(
        source,
        "with tab_mapping_review:\n",
        'if active_capability == "Review & Validate":\n',
        "mapping review capability guard",
    )

    applied.extend(
        [
            "inactive_capability_bodies_do_not_execute",
            "ask_inner_tabs_preserved",
            "review_sections_preserved_under_one_capability",
        ]
    )

    # Fail closed if any old top-level tab guard survived. Inner Ask tabs have
    # different variable names and are intentionally unaffected.
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
