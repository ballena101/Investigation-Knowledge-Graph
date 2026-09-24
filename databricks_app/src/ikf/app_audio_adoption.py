"""Deterministic Type-D audio/transcript adoption for the IKF Streamlit App.

This module keeps audio-specific App integration separate from the canonical
base Streamlit source. It is materialized into the deployable App bundle before
Databricks runtime starts.

Policy implemented here:
- access to the protected IKF App is the user access boundary for Type-D audio;
- Volume access is evaluated with the logged-in user's forwarded Databricks
  token, matching the existing MAIRA source-file access pattern;
- machine transcripts remain MACHINE_GENERATED_UNVERIFIED;
- a transcript may be viewed and corrected in Analyse Documents;
- downstream analysis is enabled only after an authenticated user confirms a
  human listening review against the original audio;
- the reviewed transcript then enters the existing Class-D direct-text analysis
  path, preserving the original audio hash and transcript model provenance.
"""

from __future__ import annotations

import re


AUDIO_ADOPTION_VERSION = "IKF_APP_AUDIO_ADOPTION_V0.3"


_ACCESS_PATTERN = re.compile(
    r"def type_d_transcript_access\(\):\n"
    r"    # The app runs with a service identity\. Never use its Volume grant as the\n"
    r"    # end user's authority to view protected transcripts\.\n"
    r"    user = get_current_user_key\(\)\n"
    r"    return user != \"unknown\" and user in TYPE_D_TRANSCRIPT_REVIEWERS\n"
)

_ACCESS_REPLACEMENT = '''def type_d_transcript_access():
    # The protected IKF App access boundary authorises Type-D transcript use.
    # Volume/file access itself is evaluated with the logged-in user's forwarded
    # Databricks token, matching the existing MAIRA file-viewer route.
    return get_current_user_key() != "unknown"
'''


_TRANSCRIPT_HELPERS_PATTERN = re.compile(
    r"def list_type_d_transcripts\(\):\n.*?\n\ndef transcript_text_with_timestamps",
    re.DOTALL,
)

_TRANSCRIPT_HELPERS_REPLACEMENT = '''def list_uc_directory_as_user(path):
    """List one UC-volume directory through Files API as the logged-in user."""

    normalized = normalise_allowed_source_path(path)
    token = get_user_access_token()
    if not token:
        raise PermissionError(
            "No forwarded Databricks user token is available. "
            "User authorization with the files scope is required."
        )

    host = get_workspace_client().config.host.rstrip("/")
    encoded_path = urllib.parse.quote(
        normalized,
        safe="/",
    )
    base_url = (
        host
        + "/api/2.0/fs/directories"
        + encoded_path
    )

    contents = []
    page_token = None
    while True:
        url = base_url
        if page_token:
            url += "?" + urllib.parse.urlencode(
                {"page_token": page_token}
            )

        request = urllib.request.Request(
            url,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/json",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=90,
            ) as response:
                payload = json.loads(
                    response.read().decode("utf-8")
                )
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise PermissionError(
                    "Your Databricks user does not have permission to list this governed Volume directory."
                ) from exc
            if exc.code == 404:
                raise FileNotFoundError(
                    "The governed Type D transcript directory does not exist."
                ) from exc
            raise OSError(
                "Databricks Files API directory listing failed with HTTP "
                + str(exc.code)
            ) from exc

        contents.extend(payload.get("contents") or [])
        page_token = payload.get("next_page_token")
        if not page_token:
            break

    return contents


def list_type_d_transcripts():
    if not type_d_transcript_access():
        return []

    entries = list_uc_directory_as_user(
        str(TYPE_D_TRANSCRIPT_ROOT)
    )
    candidates = [
        entry
        for entry in entries
        if not entry.get("is_directory")
        and re.fullmatch(
            r"[0-9a-f]{64}__(?:large-v3|turbo)\\.json",
            str(entry.get("name") or ""),
        )
        and int(entry.get("file_size") or 0) <= 10 * 1024 * 1024
    ]
    candidates.sort(
        key=lambda entry: int(entry.get("last_modified") or 0),
        reverse=True,
    )
    return [
        Path(entry["path"])
        for entry in candidates
        if entry.get("path")
    ]


def read_type_d_transcript(path):
    path = Path(path)
    if not type_d_transcript_access() or path.parent != TYPE_D_TRANSCRIPT_ROOT:
        raise PermissionError("Class D transcript access denied")
    if not re.fullmatch(r"[0-9a-f]{64}__(?:large-v3|turbo)\\.json", path.name):
        raise ValueError("Unexpected transcript filename")

    raw = download_source_file_as_user(str(path))
    if len(raw) > 10 * 1024 * 1024:
        raise ValueError("Transcript exceeds the pilot size limit")

    record = json.loads(raw.decode("utf-8"))
    if (record.get("classification") != "D"
            or record.get("status") != "MACHINE_GENERATED_UNVERIFIED"
            or record.get("source_sha256") != path.name.split("__")[0]
            or record.get("model") != path.name.split("__")[1][:-5]
            or not isinstance(record.get("segments"), list)):
        raise ValueError("Transcript provenance or classification is invalid")
    segments = record["segments"]
    if any(not isinstance(item, dict) or not isinstance(item.get("text"), str)
           or not isinstance(item.get("start_s"), (int, float))
           or not isinstance(item.get("end_s"), (int, float))
           or item["start_s"] < 0 or item["end_s"] < item["start_s"]
           for item in segments):
        raise ValueError("Transcript segments have invalid time offsets")
    return record


def load_type_d_audio_bytes(record):
    """Read and verify the original Class-D audio through the user-scoped Files API."""

    source_path = normalise_allowed_source_path(
        record.get("source_path") or ""
    )
    audio_root = IKF_SOURCE_VOLUME_ROOT.rstrip("/") + "/audios/"
    if not source_path.startswith(audio_root):
        raise PermissionError(
            "The transcript source is outside the governed Type D audio directory."
        )

    audio_bytes = download_source_file_as_user(source_path)
    if len(audio_bytes) > 100 * 1024 * 1024:
        raise ValueError(
            "Source audio exceeds the current App review size limit."
        )
    if hashlib.sha256(audio_bytes).hexdigest() != record.get("source_sha256"):
        raise ValueError(
            "Original audio hash does not match transcript provenance."
        )
    return audio_bytes


def transcript_text_with_timestamps'''


_TRANSCRIPT_AUDIO_PATTERN = re.compile(
    r'''                audio_verified = False\n'''
    r'''                audio_path = Path\(record\.get\("source_path", ""\)\)\n'''
    r'''                if \(audio_path\.parent == Path\(IKF_SOURCE_VOLUME_ROOT\) / "audios"\n'''
    r'''                        and audio_path\.is_file\(\)\n'''
    r'''                        and audio_path\.stat\(\)\.st_size <= 100 \* 1024 \* 1024\):\n'''
    r'''                    with audio_path\.open\("rb"\) as audio_file:\n'''
    r'''                        audio_bytes = audio_file\.read\(\)\n'''
    r'''                    if hashlib\.sha256\(audio_bytes\)\.hexdigest\(\) == record\["source_sha256"\]:\n'''
    r'''                        audio_verified = True\n'''
    r'''                        st\.audio\(audio_bytes\)\n'''
    r'''                    else:\n'''
    r'''                        st\.error\("Source audio hash does not match the transcript\. Review is blocked\."\)\n'''
    r'''                else:\n'''
    r'''                    st\.error\("Source audio is unavailable for verification\. Review is blocked\."\)'''
)

_TRANSCRIPT_AUDIO_REPLACEMENT = '''                audio_verified = False
                try:
                    audio_bytes = load_type_d_audio_bytes(record)
                    audio_verified = True
                    st.audio(audio_bytes)
                except (OSError, ValueError, PermissionError) as exc:
                    st.error(
                        "The original audio could not be loaded through your Databricks user access. Review is blocked."
                    )
                    st.caption(str(exc))'''


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
            try:
                analysis_audio_transcripts = list_type_d_transcripts()
            except (OSError, ValueError, PermissionError, FileNotFoundError) as exc:
                analysis_audio_transcripts = []
                st.error(
                    "The governed Type D transcript store could not be listed through your Databricks user access."
                )
                st.caption(str(exc))

            if not analysis_audio_transcripts:
                st.info(
                    "No machine transcripts are visible through your current Databricks user access."
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
                    try:
                        analysis_audio_bytes = load_type_d_audio_bytes(
                            analysis_audio_record
                        )
                        analysis_audio_verified = True
                        st.audio(analysis_audio_bytes)
                    except (OSError, ValueError, PermissionError) as exc:
                        st.error(
                            "The original audio could not be loaded through your Databricks user access. Review is blocked."
                        )
                        st.caption(str(exc))

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

    source, helper_count = _TRANSCRIPT_HELPERS_PATTERN.subn(
        _TRANSCRIPT_HELPERS_REPLACEMENT,
        source,
        count=1,
    )
    if helper_count != 1:
        raise RuntimeError(
            "IKF App audio adoption failed at transcript Files API helpers: "
            f"expected exactly one match, found {helper_count}."
        )
    applied.append("user_scoped_transcript_files_api")

    source, audio_count = _TRANSCRIPT_AUDIO_PATTERN.subn(
        _TRANSCRIPT_AUDIO_REPLACEMENT,
        source,
        count=1,
    )
    if audio_count != 1:
        raise RuntimeError(
            "IKF App audio adoption failed at Transcriptions audio reader: "
            f"expected exactly one match, found {audio_count}."
        )
    applied.append("transcriptions_audio_files_api")

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
    source = source.replace(
        "No Whisper pilot results are available yet.",
        "No machine transcripts are visible through your current Databricks user access.",
        1,
    )
    applied.append("transcription_access_message")

    return source, tuple(applied)
