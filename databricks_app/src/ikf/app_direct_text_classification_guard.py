"""Require an explicit information classification before direct-text processing.

This refinement is intentionally small and deterministic. It changes the
Analyse Documents UI so information classification has an explicit unselected
state, disables input/submission until a class is chosen, and adds a server-side
guard in the direct-text analysis constructor.
"""

from __future__ import annotations


DIRECT_TEXT_CLASSIFICATION_GUARD_VERSION = "IKF_DIRECT_TEXT_CLASSIFICATION_GUARD_V0.1.3"


def _replace_once(source: str, old: str, new: str, name: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Direct-text classification guard failed at {name}: "
            f"expected one match, found {count}."
        )
    return source.replace(old, new, 1)


def transform_app_direct_text_classification_guard(source: str):
    """Apply the explicit-classification requirement to the Streamlit App."""

    applied = []

    old_select = '''    information_class = st.selectbox(
        "Information classification",
        options=list(INFORMATION_CLASSES),
        format_func=information_class_label,
        key="analysis_information_class",
        help=(
            "This is a processing control, not only a label. It determines "
            "which model path the App is allowed to use."
        ),
    )
'''
    new_select = '''    information_class = st.selectbox(
        "Information classification",
        options=[None] + list(INFORMATION_CLASSES),
        index=0,
        format_func=(
            lambda value: (
                "Select information classification"
                if value is None
                else information_class_label(value)
            )
        ),
        key="analysis_information_class",
        help=(
            "Required before any document or direct text can be processed. "
            "This is a processing control, not only a label; it determines "
            "which model path the App is allowed to use."
        ),
    )
    classification_selected = information_class in INFORMATION_CLASSES
    if not classification_selected:
        st.info(
            "Select an information classification before entering or "
            "processing input."
        )
'''
    source = _replace_once(
        source,
        old_select,
        new_select,
        "information-class selector",
    )
    applied.append("explicit_information_class_selection")

    # Source-routing details are intentionally owned by their existing layer.
    # Enforce the security invariant after that routing has produced the final
    # available_documents collection and immediately before it is exposed to
    # the document selector. This is independent of MAIRA/IKF wording or future
    # routing refinements.
    documents_map_anchor = '''    documents_by_id = {
        document["document_id"]: document
        for document in available_documents
    }
'''
    guarded_documents_map = '''    if not classification_selected:
        available_documents = []
        catalogue_scope_label = "Select an information classification"

    documents_by_id = {
        document["document_id"]: document
        for document in available_documents
    }
'''
    source = _replace_once(
        source,
        documents_map_anchor,
        guarded_documents_map,
        "classification-driven catalogue",
    )
    applied.append("unclassified_catalogue_fail_closed")

    old_policy = '''    policy = resolve_model_policy(information_class)

    st.markdown("**Processing disclosure**")
    st.write(policy["description"])
'''
    new_policy = '''    if classification_selected:
        policy = resolve_model_policy(information_class)
    else:
        policy = {
            "description": "Select an information classification to continue.",
            "model": None,
            "model_name": "Not selected",
            "data_flow": "No model route is available until classification is selected.",
            "ready": False,
        }

    st.markdown("**Processing disclosure**")
    st.write(policy["description"])
'''
    source = _replace_once(
        source,
        old_policy,
        new_policy,
        "policy resolution",
    )
    applied.append("unclassified_policy_fail_closed")

    old_text_area = '''            direct_text = st.text_area(
                "Text to analyse and map",
                height=260,
                key="analysis_direct_text",
'''
    new_text_area = '''            direct_text = st.text_area(
                "Text to analyse and map",
                height=260,
                key="analysis_direct_text",
                disabled=not classification_selected,
'''
    source = _replace_once(
        source,
        old_text_area,
        new_text_area,
        "direct-text input disable",
    )
    applied.append("direct_text_disabled_until_classified")

    old_submit = '''        create_submitted = st.form_submit_button(
            "Create and analyse",
            type="primary",
        )
'''
    new_submit = '''        create_submitted = st.form_submit_button(
            "Create and analyse",
            type="primary",
            disabled=not classification_selected,
        )
'''
    source = _replace_once(
        source,
        old_submit,
        new_submit,
        "analysis submit disable",
    )
    applied.append("analysis_submit_disabled_until_classified")

    old_errors = '''    if create_submitted:
        errors = []
        transcript_origin = st.session_state.get("transcript_analysis_origin")
'''
    new_errors = '''    if create_submitted:
        errors = []
        if information_class not in INFORMATION_CLASSES:
            errors.append(
                "Select an information classification before processing this input."
            )
        transcript_origin = st.session_state.get("transcript_analysis_origin")
'''
    source = _replace_once(
        source,
        old_errors,
        new_errors,
        "submit validation",
    )
    applied.append("server_side_submit_classification_guard")

    old_constructor = '''def create_analysis_from_text(
    title,
    description,
    direct_text,
    language_mode,
    output_language,
    information_class,
    model_service,
    model_selection=None,
):
'''
    new_constructor = '''def create_analysis_from_text(
    title,
    description,
    direct_text,
    language_mode,
    output_language,
    information_class,
    model_service,
    model_selection=None,
):
    if information_class not in INFORMATION_CLASSES:
        raise ValueError(
            "Direct text requires an explicit valid information classification."
        )
'''
    source = _replace_once(
        source,
        old_constructor,
        new_constructor,
        "direct-text constructor guard",
    )
    applied.append("direct_text_constructor_fail_closed")

    return source, tuple(applied)
