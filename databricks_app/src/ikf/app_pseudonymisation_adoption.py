"""Adopt IKF pseudonymisation v0.1 into Analyse Documents.

Pseudonymisation is source-agnostic: it can operate on direct text or selected
governed PDF/text/transcript documents. The derived output can be reviewed,
downloaded and reused through the existing DirectTextSource ingress, avoiding a
second analysis pipeline. Parent source IDs remain attached to session metadata.
"""

from __future__ import annotations


PSEUDONYMISATION_ADOPTION_VERSION = "IKF_APP_PSEUDONYMISATION_V0.1.1"


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
        ")\n"
        "from ikf.pseudonymisation_sources import read_source_text\n"
        "from ikf.pseudonymised_source import processing_policy\n",
        "pseudonymisation imports",
    )
    applied.append("pseudonymisation_source_agnostic_imports")

    form_anchor = '''        language_mode = st.selectbox(
            "Source language handling",
'''
    controls = '''        pseudonymisation_categories = []
        pseudonymisation_manual_names = ""
        pseudonymisation_manual_terms = ""
        pseudonymisation_target_class = information_class
        st.markdown("#### Pseudonymisation")
        st.caption(
            "Optional privacy transformation for the current input. It works on "
            "direct text and selected governed documents (PDF, text/interview files "
            "and transcript JSON). The canonical source is never overwritten."
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
            disabled=not classification_selected,
        )
        if classification_selected:
            pseudo_policy = processing_policy(information_class)
            if len(pseudo_policy.allowed_processing_classes) > 1:
                pseudonymisation_target_class = st.selectbox(
                    "Processing class for the reviewed pseudonymised derivative",
                    options=list(pseudo_policy.allowed_processing_classes),
                    index=0,
                    help=(
                        "Pseudonymisation does not automatically downgrade Class D. "
                        "Class C may be selected only for a reviewed derivative; A/B "
                        "are not permitted downgrade targets for Class D in v0.1."
                    ),
                    key="pseudonymisation_target_class",
                )
        if "PERSON" in pseudonymisation_categories:
            pseudonymisation_manual_names = st.text_area(
                "Person names to pseudonymise (optional in v0.1)",
                height=90,
                placeholder="One name per line",
                help=(
                    "V0.1 does not guess person names with a regex. Enter known names "
                    "for deterministic replacement. Classification-aware LLM/entity "
                    "detection can be added later without changing this replacement layer."
                ),
                key="pseudonymisation_manual_names",
                disabled=not classification_selected,
            )
        pseudonymisation_manual_terms = st.text_area(
            "Additional terms to pseudonymise (optional)",
            height=90,
            placeholder="CATEGORY | exact text, one per line\\ne.g. ORGANISATION | Example Shipping Ltd",
            help=(
                "Use a selected category followed by | and the exact term. This is "
                "useful for organisations, vessels, ports or locations when stricter "
                "pseudonymisation is required."
            ),
            key="pseudonymisation_manual_terms",
            disabled=not classification_selected,
        )
        pseudonymisation_review_confirmed = st.checkbox(
            "I will review the pseudonymised output before using it as analysis input.",
            value=False,
            key="pseudonymisation_review_confirmed",
            disabled=not classification_selected,
        )

'''
    source = _replace_once(
        source,
        form_anchor,
        controls + form_anchor,
        "pseudonymisation controls",
    )
    applied.append("pseudonymisation_controls_all_input_modes")

    submit_anchor = '''        create_submitted = st.form_submit_button(
            "Create and analyse",
            type="primary",
            disabled=not classification_selected,
        )
'''
    submit_new = submit_anchor + '''        pseudonymise_submitted = st.form_submit_button(
            "Generate pseudonymised version",
            disabled=(
                not classification_selected
                or not pseudonymisation_review_confirmed
            ),
        )
'''
    source = _replace_once(
        source,
        submit_anchor,
        submit_new,
        "pseudonymisation submit",
    )
    applied.append("pseudonymisation_generate_action_all_sources")

    after_form_anchor = '''    if create_submitted:
        errors = []
'''
    after_form = '''    if pseudonymise_submitted:
        pseudo_errors = []
        source_text_for_pseudonymisation = ""
        parent_source_ids = []
        parent_source_labels = []

        if information_class not in INFORMATION_CLASSES:
            pseudo_errors.append(
                "Select an information classification before pseudonymisation."
            )
        elif input_mode == "Direct text":
            if not direct_text.strip():
                pseudo_errors.append(
                    "Enter direct text before generating a pseudonymised version."
                )
            else:
                source_text_for_pseudonymisation = direct_text.strip()
                parent_source_labels = ["Direct text"]
        else:
            if not selected_document_ids:
                pseudo_errors.append(
                    "Select at least one document before generating a pseudonymised version."
                )
            else:
                source_chunks = []
                for document_id in selected_document_ids:
                    document = documents_by_id.get(document_id) or all_documents_by_id.get(document_id)
                    if not document:
                        pseudo_errors.append(
                            f"Selected source is no longer available: {document_id}"
                        )
                        continue
                    source_path = (
                        document.get("viewer_source_path")
                        or document.get("volume_path")
                    )
                    try:
                        extracted = read_source_text(
                            source_path,
                            allowed_roots=ALLOWED_SOURCE_VOLUME_ROOTS,
                        )
                    except Exception as exc:
                        pseudo_errors.append(
                            f"{document.get('filename') or document_id}: {exc}"
                        )
                        continue
                    filename = document.get("filename") or document_id
                    source_chunks.append(
                        f"[[SOURCE {filename}]]\\n{extracted['text']}"
                    )
                    parent_source_ids.append(document_id)
                    parent_source_labels.append(filename)
                source_text_for_pseudonymisation = "\\n\\n".join(source_chunks).strip()

        if not pseudo_errors and source_text_for_pseudonymisation:
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
                source_text_for_pseudonymisation,
                categories=pseudonymisation_categories,
                manual_terms=manual_terms,
            )
            st.session_state["pseudonymisation_result"] = {
                "text": result["text"],
                "version": result["version"],
                "categories": list(result["categories"]),
                "mapping": result["mapping"],
                "source_information_class": information_class,
                "processing_class": pseudonymisation_target_class,
                "parent_source_ids": parent_source_ids,
                "parent_source_labels": parent_source_labels,
                "source_mode": input_mode,
            }
        else:
            for message in pseudo_errors:
                st.error(message)

    pseudonymisation_result = st.session_state.get("pseudonymisation_result")
    if pseudonymisation_result:
        st.markdown("### Pseudonymised derivative")
        parent_labels = pseudonymisation_result.get("parent_source_labels") or []
        st.caption(
            f"{pseudonymisation_result['version']} · source Class "
            f"{pseudonymisation_result['source_information_class']} · processing Class "
            f"{pseudonymisation_result['processing_class']} · "
            + (", ".join(parent_labels) if parent_labels else "direct text")
        )
        st.text_area(
            "Review pseudonymised output",
            value=pseudonymisation_result["text"],
            height=300,
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

        def _adopt_pseudonymised_derivative():
            result = st.session_state.get("pseudonymisation_result") or {}
            if not result.get("text"):
                return
            st.session_state["analysis_input_mode"] = "Direct text"
            st.session_state["analysis_information_class"] = result.get(
                "processing_class"
            )
            st.session_state["analysis_direct_text"] = result["text"]
            st.session_state["pseudonymised_analysis_origin"] = {
                "source_information_class": result.get("source_information_class"),
                "processing_class": result.get("processing_class"),
                "parent_source_ids": list(result.get("parent_source_ids") or []),
                "pseudonymisation_version": result.get("version"),
            }

        st.button(
            "Use reviewed pseudonymised version as analysis input",
            key="use_pseudonymised_as_analysis_input",
            on_click=_adopt_pseudonymised_derivative,
            help=(
                "Reuses the existing governed DirectTextSource analysis ingress; no "
                "second LLM pipeline is created. Parent source IDs are retained in "
                "session provenance for the PoC."
            ),
        )

''' + after_form_anchor
    source = _replace_once(
        source,
        after_form_anchor,
        after_form,
        "pseudonymisation result output",
    )
    applied.append("pseudonymisation_documents_transcripts_direct_text")
    applied.append("pseudonymised_derivative_reusable_analysis_input")

    return source, tuple(applied)
