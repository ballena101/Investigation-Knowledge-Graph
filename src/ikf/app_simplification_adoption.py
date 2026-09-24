"""Final deterministic simplification pass for the IKF Streamlit App.

This pass removes user-visible legacy wording and duplicated governance copy
without changing the underlying evidence, review or model-routing controls.
It is deliberately applied last so it can clean materialized text introduced
by older source layers while keeping the canonical raw source auditable.
"""

from __future__ import annotations

import re


SIMPLIFICATION_ADOPTION_VERSION = "IKF_APP_SIMPLIFICATION_ADOPTION_V0.2"


_COMPACT_HEADER_AND_NOTICES = r'''st.title("Safety Investigation Knowledge & AI Support")
st.caption(
    "AI-assisted evidence analysis for safety investigators. Source evidence remains "
    "authoritative; AI outputs remain proposals until investigator review."
)

with st.expander(
    "AI routing and information classes",
    expanded=False,
):
    st.dataframe(
        [
            {
                "Class": "A / B — Public or published",
                "Model": "Llama 3.3 70B Instruct",
                "Route": "Databricks system.ai",
                "Use": "Public, technical or published investigation material",
            },
            {
                "Class": "C — Internal / restricted",
                "Model": "GPT-OSS 120B",
                "Route": "Databricks system.ai",
                "Use": "Internal analytical material",
            },
            {
                "Class": "D — Protected / Article 9",
                "Model": "GPT-OSS 20B and/or Llama 3.3 70B",
                "Route": "Dedicated IKF Databricks services",
                "Use": "Protected investigation evidence; no fallback to A/B/C",
            },
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "The information class determines the permitted model route. The selected "
        "model/service is recorded with the analysis. Class D never falls back to "
        "A/B/C routes."
    )

with st.expander(
    "Confidentiality and Article 9",
    expanded=False,
):
    st.markdown(
        """
IKF applies **Article 9-aligned handling rules** to protected investigation
records in this PoC. This is a system-design and processing control, not a legal
certification of compliance.

- Original evidence remains authoritative and stays in governed storage.
- Protected material uses **Class D** and dedicated model routes.
- Machine audio transcripts remain unverified until a person listens, corrects
  and accepts them.
- AI-generated findings and relationships remain proposals; **human validation
  is authoritative** and drives the reviewed graph.
- Analytical outputs minimise unnecessary personal data while preserving source
  provenance for authorised review.

These controls are designed to support the confidentiality requirements of
**Article 9 of Directive 2009/18/EC, updated by Directive (EU) 2024/3017**, and
the applicable data-protection framework. Detailed technical, retention and
provider-specific controls remain in the project documentation rather than in
the operational UI.
        """
    )
'''


def _replace_slice(
    source: str,
    *,
    start_marker: str,
    end_marker: str,
    replacement: str,
    name: str,
) -> str:
    start = source.find(start_marker)
    if start < 0:
        raise RuntimeError(
            f"IKF simplification adoption could not locate {name} start marker."
        )
    end = source.find(end_marker, start)
    if end < 0:
        raise RuntimeError(
            f"IKF simplification adoption could not locate {name} end marker."
        )
    return source[:start] + replacement + "\n\n" + source[end:]


def transform_app_simplification_source(
    source: str,
) -> tuple[str, tuple[str, ...]]:
    """Remove legacy/duplicated UI wording after all other App transforms."""

    applied: list[str] = []

    # The build identifier is available in the bundle manifest. Showing a dated
    # hard-coded string in the operational UI caused stale version information.
    source, build_count = re.subn(
        r'^APP_BUILD = "[^"]+"\n',
        "",
        source,
        count=1,
        flags=re.MULTILINE,
    )
    if build_count != 1:
        raise RuntimeError(
            "IKF simplification adoption expected one legacy APP_BUILD definition."
        )
    applied.append("remove_stale_app_build_label")

    # App access is now the Type-D transcript boundary. The historical separate
    # reviewer allow-list is no longer consulted and should not remain as dead
    # configuration in the deployed source.
    source, reviewer_count = re.subn(
        r'TYPE_D_TRANSCRIPT_REVIEWERS = \{\n.*?\n\}\n\n',
        "",
        source,
        count=1,
        flags=re.DOTALL,
    )
    if reviewer_count != 1:
        raise RuntimeError(
            "IKF simplification adoption expected one legacy transcript reviewer block."
        )
    applied.append("remove_legacy_transcript_reviewer_allowlist")

    # Retire the historical Ollama compatibility alias. Class-D Llama now has
    # one canonical Databricks service environment variable and code path.
    legacy_endpoint_block = '''CLASS_D_OLLAMA_LLAMA70_URL = os.getenv("CLASS_D_OLLAMA_LLAMA70_URL")
CLASS_D_LLAMA70_ENDPOINT = (
    os.getenv("CLASS_D_LLAMA70_ENDPOINT")
    or CLASS_D_OLLAMA_LLAMA70_URL
)
'''
    canonical_endpoint_block = '''CLASS_D_LLAMA70_ENDPOINT = os.getenv(
    "CLASS_D_LLAMA70_ENDPOINT"
)
'''
    if legacy_endpoint_block not in source:
        raise RuntimeError(
            "IKF simplification adoption could not locate the legacy Ollama endpoint alias."
        )
    source = source.replace(
        legacy_endpoint_block,
        canonical_endpoint_block,
        1,
    )
    source = source.replace(
        "if CLASS_D_OLLAMA_LLAMA70_URL:",
        "if CLASS_D_LLAMA70_ENDPOINT:",
    )
    applied.append("retire_ollama_endpoint_alias")

    source = source.replace(
        '"model_name": "Dedicated IKG GPT-OSS 20B and/or Llama 3.3 70B Databricks model services"',
        '"model_name": "Dedicated IKF GPT-OSS 20B and/or Llama 3.3 70B Databricks model services"',
        1,
    )

    source = _replace_slice(
        source,
        start_marker='st.title("Safety Investigation Knowledge & AI Support")',
        end_marker='NEO4J_URI = os.getenv("NEO4J_URI")',
        replacement=_COMPACT_HEADER_AND_NOTICES,
        name="duplicated governance notices",
    )
    applied.append("compact_governance_notices")

    wording_replacements = (
        (
            "Controlled Ollama Llama 3.3 70B service is not configured.",
            "Llama 3.3 70B Databricks service is not configured.",
        ),
        (
            "Today's Ollama quota has been reset for ",
            "Today's Llama 70B quota has been reset for ",
        ),
        (
            "Only an IKG administrator can reset the Llama daily quota.",
            "Only an IKF administrator can reset the Llama daily quota.",
        ),
        (
            "concept/relationship filters, layout controls and graph-scoped questions.",
            "concept/relationship filters, layout controls and the latest reviewed relationship state.",
        ),
        (
            "correction proposals, EMCIP mappings and SHIELD classifications.",
            "relationship validation and correction proposals, with SHIELD classification after human validation.",
        ),
        (
            "Assistant outputs are proposals. Human relationship, EMCIP and SHIELD review\n"
            "records remain append-only and authoritative according to their governed\n"
            "workflow. Assistant correction checks never overwrite graph edges.",
            "Assistant outputs remain proposals. Human relationship decisions are authoritative;\n"
            "the displayed graph applies the latest reviews, while the raw AI graph is retained\n"
            "for traceability. SHIELD is derived only after contributing-factor validation.",
        ),
    )
    for old, new in wording_replacements:
        source = source.replace(old, new)
    applied.append("remove_ikg_ollama_and_legacy_about_wording")

    # This was a static development milestone and therefore became stale as soon
    # as the project moved on. Operational users do not need repository/test state
    # on the Home page.
    milestone_start = source.find(
        '    st.divider()\n    st.markdown("### Current validation milestone")\n'
    )
    if milestone_start >= 0:
        milestone_end = source.find("\nwith tab_news:\n", milestone_start)
        if milestone_end < 0:
            raise RuntimeError(
                "IKF simplification adoption could not close the legacy milestone block."
            )
        source = source[:milestone_start] + source[milestone_end:]
        applied.append("remove_static_validation_milestone")

    # The EMCIP UI has already been removed by the workflow adoption. Remove its
    # obsolete tab alias/comment so the materialized source reflects the product.
    legacy_mapping_alias = '''# Relationship and EMCIP reviews are deliberately presented in one capability.
# Re-entering the same Streamlit tab later appends the mapping-review section.
tab_mapping_review = tab_review

'''
    if legacy_mapping_alias in source:
        source = source.replace(legacy_mapping_alias, "", 1)
        applied.append("remove_legacy_emcip_tab_alias")

    # The transcription workspace creates and validates a governed source. Once
    # accepted, the transcript is analysed through Analyse Documents. The shorter
    # label makes that distinction clearer.
    source = source.replace(
        '        "Transcriptions",\n',
        '        "Audio transcription",\n',
        1,
    )
    applied.append("clarify_audio_workspace_label")

    return source, tuple(applied)
