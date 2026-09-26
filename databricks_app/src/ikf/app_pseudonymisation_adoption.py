"""Adopt IKF pseudonymisation v0.1 into Analyse Documents.

The UI reuses the existing direct-text entry and information classification.
It does not create a second text-ingress path. Pseudonymised text is a derived
output that can be reviewed and downloaded; v0.1 does not silently replace the
analysis input.
"""

from __future__ import annotations


PSEUDONYMISATION_ADOPTION_VERSION = "IKF_APP_PSEUDONYMISATION_V0.1"


def _replace_once(source: str, old: str, new: str, name: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Pseudonymisation adoption failed at {name}: "
            f"expected one match, found {count}."
        )
    return source.replace(old, new, 1)


def transform_app_pseudonymisation_source(source: str):
    applied = []

    source = _replace_once(
        source,
        "import streamlit as st\n",
        "import streamlit as st\n"
        "from ikf.pseudonymisation import (\n"
        "    ALL_CATEGORIES as PSEUDONYMISATION_CATEGORIES,\n"
        "    DEFAULT_CATEGORIES as PSEUDONYMISATION_DEFAULTS,\n"
        "    pseudonymise_text,\n"
        ")\n",
        "pseudonymisation import",
    )
    applied.append("pseudonymisation_core_import")

    form_anchor = '''        language_mode = st.selectbox(
            "Source language handling",
'''
    controls = '''        pseudonymisation_categories = []
        pseudonymisation_manual_names = ""
        pseudonymisation_manual_terms = ""
        if input_mode == "Direct text":
            st.markdown("#### Pseudonymisation output")
            st.caption(
                "Optional derived output. The original direct text remains the source "
                "for the analysis unless a later reviewed workflow explicitly adopts "
                "the pseudonymised version."
            )
            pseudonymisation_categories = st.multiselect(
                "Elements to pseudonymise",
                options=list(PSEUDONYMISATION_CATEGORIES),
                default=list(PSEUDONYMISATION_DEFAULTS),
                help=(
                    "Person names, email, telephone and personal identifiers are the "
                    "recommended defaults. Vessel, IMO/MMSI, organisation, port and "
                    "location data are optional because they may be analytically important."
                ),
                key="pseudonymisation_categories",
            )
            if "PERSON" in pseudonymisation_categories:
                pseudonymisation_manual_names = st.text_area(
                    "Person names to pseudonymise (optional in v0.1)",
                    height=90,
                    placeholder="One name per line",
                    help=(
                        "V0.1 does not guess person names with a regex. Enter known names "
                        "here for deterministic replacement. Classification-aware LLM "
                        "name detection can be added as a separate detector later."
                    ),
                    key="pseudonymisation_manual_names",
                )
            pseudonymisation_manual_terms = st.text_area(
                "Additional terms to pseudonymise (optional)",
                height=90,
                placeholder="CATEGORY | exact text, one per line\ne.g. ORGANISATION | Example Shipping Ltd",
                help=(
                    "Use a selected category followed by | and the exact term. This is "
                    "useful for organisations, vessels, ports or locations when stricter "
                    "pseudonymisation is required."
                ),
                key="pseudonymisation_manual_terms",
            )

'''
    source = _replace_once(
        source,
        form_anchor,
        controls + form_anchor,
        "pseudonymisation controls",
    )
    applied.append("pseudonymisation_category_controls")

    submit_anchor = '''        create_submitted = st.form_submit_button(
            "Create and analyse",
            type="primary",
            disabled=not classification_selected,
        )
'''
    submit_new = submit_anchor + '''        pseudonymise_submitted = st.form_submit_button(
            "Generate pseudonymised text",
            disabled=(
                not classification_selected
                or input_mode != "Direct text"
            ),
        )
'''
    source = _replace_once(
        source,
        submit_anchor,
        submit_new,
        "pseudonymisation submit",
    )
    applied.append("pseudonymisation_generate_action")

    after_form_anchor = '''    if create_submitted:
        errors = []
'''
    after_form = '''    if pseudonymise_submitted:
        if input_mode != "Direct text":
            st.error("Pseudonymisation v0.1 currently uses the direct-text input.")
        elif information_class not in INFORMATION_CLASSES:
            st.error("Select an information classification before pseudonymisation.")
        elif not direct_text.strip():
            st.error("Enter direct text before generating a pseudonymised version.")
        else:
            manual_terms = {}
            names = [
                value.strip()
                for value in pseudonymisation_manual_names.splitlines()
                if value.strip()
            ]
            if names:
                manual_terms["PERSON"] = names
            for raw_line in pseudonymisation_manual_terms.splitlines():
                line = raw_line.strip()
                if not line or "|" not in line:
                    continue
                category, value = [part.strip() for part in line.split("|", 1)]
                category = category.upper()
                if category in pseudonymisation_categories and value:
                    manual_terms.setdefault(category, []).append(value)
            result = pseudonymise_text(
                direct_text,
                categories=pseudonymisation_categories,
                manual_terms=manual_terms,
            )
            st.session_state["pseudonymisation_result"] = {
                "text": result["text"],
                "version": result["version"],
                "categories": list(result["categories"]),
                "mapping": result["mapping"],
                "information_class": information_class,
            }

    pseudonymisation_result = st.session_state.get("pseudonymisation_result")
    if pseudonymisation_result and input_mode == "Direct text":
        st.markdown("### Pseudonymised text")
        st.caption(
            f"{pseudonymisation_result['version']} · "
            f"Class {pseudonymisation_result['information_class']} · "
            "derived output; original source retained separately"
        )
        st.text_area(
            "Review pseudonymised output",
            value=pseudonymisation_result["text"],
            height=260,
            key="pseudonymisation_output_preview",
        )
        st.download_button(
            "Download pseudonymised text (.txt)",
            data=pseudonymisation_result["text"].encode("utf-8"),
            file_name="ikf_pseudonymised_text.txt",
            mime="text/plain",
            key="download_pseudonymised_text",
        )
        with st.expander("Authorised mapping review", expanded=False):
            mapping_rows = [
                {"Pseudonym": key, "Original": value}
                for key, value in pseudonymisation_result["mapping"].items()
            ]
            if mapping_rows:
                st.dataframe(mapping_rows, use_container_width=True, hide_index=True)
            else:
                st.caption("No replacements were generated with the selected categories.")

''' + after_form_anchor
    source = _replace_once(
        source,
        after_form_anchor,
        after_form,
        "pseudonymisation result output",
    )
    applied.append("pseudonymisation_preview_download_mapping")

    return source, tuple(applied)
