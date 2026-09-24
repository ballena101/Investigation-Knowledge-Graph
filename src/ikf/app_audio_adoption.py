"""Deterministic Type-D audio/transcript adoption for the IKF Streamlit App.

This module keeps audio-specific App integration separate from the canonical
base Streamlit source. It is materialized into the deployable App bundle before
Databricks runtime starts.

Policy implemented here:
- access to the protected IKF App is the user access boundary for Type-D audio;
- machine transcripts remain MACHINE_GENERATED_UNVERIFIED;
- a transcript may be viewed and corrected in Analyse Documents;
- downstream analysis is enabled only after an authenticated user confirms a
  human listening review against the original audio;
- the reviewed transcript then enters the existing Class-D direct-text analysis
  path, preserving the original audio hash and transcript model provenance.
"""

from __future__ import annotations

import re


AUDIO_ADOPTION_VERSION = "IKF_APP_AUDIO_ADOPTION_V0.1"


_ACCESS_PATTERN = re.compile(
    r"def type_d_transcript_access\(\):\n"
    r"    # The app runs with a service identity\. Never use its Volume grant as the\n"
    r"    # end user's authority to view protected transcripts\.\n"
    r"    user = get_current_user_key\(\)\n"
    r"    return user != \"unknown\" and user in TYPE_D_TRANSCRIPT_REVIEWERS\n"
)

_ACCESS_REPLACEMENT = '''def type_d_transcript_access():
    # The protected IKF App access boundary authorises Type-D transcript use.
    # We still require a resolved end-user identity so every review remains
    # attributable; the App service identity alone is never sufficient.
    return get_current_user_key() != "unknown"
'''


_ANALYSE_DOCUMENTS_ANCHOR = '''with tab_new_analysis:
    st.subheader("Analyse Documents")
    st.caption(
        "Prepare and analyse a governed evidence set from indexed documents or "
        "direct text. Questions are asked later in Ask / Compare LLMs so the "
        "evidence structure does not depend on one initial question."
    )
'''


_AUDIO_PANEL = '''with tab_new_analysis:
    st.subheader("Analyse Documents")
    st.caption(
        "Prepare and analyse a governed evidence set from indexed documents, "
        "reviewed Type D audio transcripts or direct text. Questions are asked later "
        "in Ask / Compare LLMs so the evidence structure does not depend on one initial question."
    )

    with st.expander("Audio / reviewed transcript — Class D", expanded=False):
        st.caption(
            "Audio recordings and their transcripts are always handled as Class D. "
            "A machine transcript can be inspected here, but it cannot support Findings, "
            "Evidence, Knowledge Graph relationships or SHIELD classification until a user "
            "has listened to the original audio and confirmed/corrected the transcript."
        )

        if not type_d_transcript_access():
            st.error(
                "Your App user identity could not be resolved. Type D audio review is blocked."
            )
        else:
            analysis_audio_transcripts = list_type_d_transcripts()
            if not analysis_audio_transcripts:
                st.info(
                    "No machine transcripts are available in the governed Type D transcript store yet."
                )
            else:
                selected_analysis_audio_transcript = st.selectbox(
                    "Available Type D transcript",
                    options=analysis_audio_transcripts,
                    format_func=lambda path: path.name,
                    key="analysis_audio_transcript_selector",
                )

                try:
                    analysis_audio_record = read_type_d_transcript(
                        selected_analysis_audio_transcript
                    )
                    analysis_audio_text = transcript_text_with_timestamps(
                        analysis_audio_record
                    )

                    st.caption(
                        f"Source: {analysis_audio_record.get('source_name', 'unknown')} · "
                        f"Model: {analysis_audio_record.get('model', 'unknown')} · "
                        f"Status: {analysis_audio_record.get('status', 'unknown')}"
                    )

                    if analysis_audio_record.get("status") == "MACHINE_GENERATED_UNVERIFIED":
                        st.warning(
                            "Machine-generated transcript — not validated evidence. "
                            "Listen to the original audio and correct uncertain or inaudible spans before use."
                        )

                    analysis_audio_verified = False
                    analysis_audio_path = Path(
                        analysis_audio_record.get("source_path") or ""
                    )
                    if analysis_audio_path.is_file():
                        with analysis_audio_path.open("rb") as analysis_audio_file:
                            analysis_audio_bytes = analysis_audio_file.read()
                        if (
                            hashlib.sha256(analysis_audio_bytes).hexdigest()
                            == analysis_audio_record.get("source_sha256")
                        ):
                            analysis_audio_verified = True
                            st.audio(analysis_audio_bytes)
                        else:
                            st.error(
                                "Original audio hash does not match transcript provenance. Review is blocked."
                            )
                    else:
                        st.error(
                            "Original audio is unavailable. Review is blocked because the source cannot be verified."
                        )

                    st.text_area(
                        "Timestamped machine transcript",
                        analysis_audio_text,
                        height=260,
                        disabled=True,
                        key="analysis_audio_machine_transcript",
                    )

                    analysis_audio_reviewed_text = st.text_area(
                        "Reviewed transcript for this analysis",
                        value=analysis_audio_text,
                        height=320,
                        key=(
                            "analysis_audio_review_"
                            + selected_analysis_audio_transcript.name
                        ),
                        help=(
                            "Correct only after listening. Keep timestamps, mark inaudible spans explicitly, "
                            "and do not infer missing words from context or an LLM."
                        ),
                    )

                    analysis_audio_confirmed = st.checkbox(
                        "I listened to the original audio and checked this transcript; corrections and inaudible spans are explicit.",
                        key=(
                            "analysis_audio_confirm_"
                            + selected_analysis_audio_transcript.name
                        ),
                    )

                    if st.button(
                        "Use reviewed audio transcript in this analysis",
                        type="primary",
                        disabled=not (
                            analysis_audio_verified
                            and analysis_audio_confirmed
                            and analysis_audio_reviewed_text.strip()
                        ),
                        key="analysis_audio_use_reviewed",
                    ):
                        reviewed_audio_text = analysis_audio_reviewed_text.strip()
                        reviewed_audio_hash = save_transcript_review(
                            analysis_audio_record,
                            reviewed_audio_text,
                        )
                        st.session_state["transcript_analysis_origin"] = {
                            "source_sha256": analysis_audio_record["source_sha256"],
                            "source_name": analysis_audio_record.get("source_name"),
                            "source_path": analysis_audio_record.get("source_path"),
                            "model": analysis_audio_record["model"],
                            "text_hash": reviewed_audio_hash,
                        }
                        st.session_state["analysis_input_mode"] = "Direct text"
                        st.session_state["analysis_information_class"] = "D"
                        st.session_state["analysis_direct_text"] = reviewed_audio_text
                        st.success(
                            "Reviewed audio transcript loaded as the Class D source for Analyse Documents."
                        )
                        st.rerun()

                except (
                    OSError,
                    ValueError,
                    PermissionError,
                    json.JSONDecodeError,
                ) as exc:
                    st.error("The Type D transcript could not be loaded safely.")
                    st.caption(str(exc))
'''


def transform_app_audio_source(source: str) -> tuple[str, tuple[str, ...]]:
    """Materialize authenticated audio review into the Streamlit App source."""

    applied: list[str] = []

    source, access_count = _ACCESS_PATTERN.subn(
        _ACCESS_REPLACEMENT,
        source,
        count=1,
    )
    if access_count != 1:
        raise RuntimeError(
            "IKF App audio adoption failed at Type-D access boundary: "
            f"expected exactly one match, found {access_count}."
        )
    applied.append("app_access_is_type_d_audio_boundary")

    if _ANALYSE_DOCUMENTS_ANCHOR not in source:
        raise RuntimeError(
            "IKF App audio adoption could not locate Analyse Documents anchor."
        )
    source = source.replace(
        _ANALYSE_DOCUMENTS_ANCHOR,
        _AUDIO_PANEL,
        1,
    )
    applied.append("analyse_documents_audio_review")

    source = source.replace(
        "Transcripts are available to designated Type D reviewers only.",
        "Type D transcript access requires a resolved authenticated App user identity.",
        1,
    )
    applied.append("transcription_access_message")

    return source, tuple(applied)
