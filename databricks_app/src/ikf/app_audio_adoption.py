"""Materialize the governed Type-D audio workflow into the IKF Streamlit App.

The transcription surface has one responsibility:

    select audio -> process -> review -> accept/publish

After publication the validated transcript is an ordinary Class-D
``SourceDocument`` and appears in the existing Analyse Documents catalogue.
There is deliberately no second audio/transcript analysis panel.
"""

from __future__ import annotations

import re


AUDIO_ADOPTION_VERSION = "IKF_APP_AUDIO_ADOPTION_V0.4"


_ENV_ANCHOR = '''SIMILAR_CASES_JOB_ID = os.getenv(
    "SIMILAR_CASES_JOB_ID"
)
'''
_ENV_REPLACEMENT = _ENV_ANCHOR + '''TRANSCRIPTION_JOB_ID = os.getenv(
    "TRANSCRIPTION_JOB_ID"
)
'''

_IMPORT_ANCHOR = "from neo4j import GraphDatabase\n"
_IMPORT_REPLACEMENT = _IMPORT_ANCHOR + '''from ikf.transcription_governance import (
    SUPPORTED_AUDIO_EXTENSIONS,
    normalise_transcription_model,
    normalise_type_d_audio_path,
)
'''

_ACCESS_PATTERN = re.compile(
    r"def type_d_transcript_access\(\):\n"
    r"    # The app runs with a service identity\. Never use its Volume grant as the\n"
    r"    # end user's authority to view protected transcripts\.\n"
    r"    user = get_current_user_key\(\)\n"
    r"    return user != \"unknown\" and user in TYPE_D_TRANSCRIPT_REVIEWERS\n"
)
_ACCESS_REPLACEMENT = '''def type_d_transcript_access():
    # The protected IKF App access boundary authorises Type-D transcript use.
    # File visibility is still evaluated with the logged-in user's forwarded
    # Databricks token, matching the existing MAIRA source-file route.
    return get_current_user_key() != "unknown"
'''

_TRANSCRIPT_HELPERS_PATTERN = re.compile(
    r"def list_type_d_transcripts\(\):\n.*?\n\ndef transcript_text_with_timestamps",
    re.DOTALL,
)

_TRANSCRIPT_HELPERS_REPLACEMENT = '''def list_uc_directory_as_user(path):
    """List one governed UC-volume directory using the logged-in user's token."""

    normalized = normalise_allowed_source_path(path)
    token = get_user_access_token()
    if not token:
        raise PermissionError(
            "No forwarded Databricks user token is available. "
            "User authorization with the files scope is required."
        )

    host = get_workspace_client().config.host.rstrip("/")
    encoded_path = urllib.parse.quote(normalized, safe="/")
    base_url = host + "/api/2.0/fs/directories" + encoded_path

    contents = []
    page_token = None
    while True:
        url = base_url
        if page_token:
            url += "?" + urllib.parse.urlencode({"page_token": page_token})

        request = urllib.request.Request(
            url,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise PermissionError(
                    "Your Databricks user does not have permission to list this governed Volume directory."
                ) from exc
            if exc.code == 404:
                raise FileNotFoundError(
                    "The governed Volume directory does not exist."
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


def list_type_d_audio_sources():
    if not type_d_transcript_access():
        return []

    audio_root = IKF_SOURCE_VOLUME_ROOT.rstrip("/") + "/audios"
    entries = list_uc_directory_as_user(audio_root)
    sources = []
    for entry in entries:
        if entry.get("is_directory"):
            continue
        name = str(entry.get("name") or "")
        path = str(entry.get("path") or "")
        extension = Path(name).suffix.lower()
        if extension not in SUPPORTED_AUDIO_EXTENSIONS:
            continue
        try:
            normalized = normalise_type_d_audio_path(
                path,
                audio_root=audio_root,
            )
        except ValueError:
            continue
        size = int(entry.get("file_size") or 0)
        if size <= 0 or size > 100 * 1024 * 1024:
            continue
        sources.append(
            {
                "name": name,
                "path": normalized,
                "file_size": size,
                "last_modified": int(entry.get("last_modified") or 0),
            }
        )

    sources.sort(
        key=lambda item: (item["name"].lower(), item["path"])
    )
    return sources


def list_type_d_transcripts():
    if not type_d_transcript_access():
        return []

    try:
        entries = list_uc_directory_as_user(str(TYPE_D_TRANSCRIPT_ROOT))
    except FileNotFoundError:
        return []

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
        raise ValueError("Transcript exceeds the current size limit")

    record = json.loads(raw.decode("utf-8"))
    if (
        record.get("classification") != "D"
        or record.get("status") != "MACHINE_GENERATED_UNVERIFIED"
        or record.get("source_sha256") != path.name.split("__")[0]
        or record.get("model") != path.name.split("__")[1][:-5]
        or not isinstance(record.get("segments"), list)
    ):
        raise ValueError("Transcript provenance or classification is invalid")

    if any(
        not isinstance(item, dict)
        or not isinstance(item.get("text"), str)
        or not isinstance(item.get("start_s"), (int, float))
        or not isinstance(item.get("end_s"), (int, float))
        or item["start_s"] < 0
        or item["end_s"] < item["start_s"]
        for item in record["segments"]
    ):
        raise ValueError("Transcript segments have invalid time offsets")
    return record


def find_type_d_machine_transcript(source_path, model):
    source_path = normalise_type_d_audio_path(
        source_path,
        audio_root=IKF_SOURCE_VOLUME_ROOT.rstrip("/") + "/audios",
    )
    model = normalise_transcription_model(model)
    for transcript_path in list_type_d_transcripts():
        try:
            record = read_type_d_transcript(transcript_path)
        except (OSError, ValueError, PermissionError, json.JSONDecodeError):
            continue
        if (
            str(record.get("source_path") or "") == source_path
            and record.get("model") == model
        ):
            return transcript_path, record
    return None, None


def load_type_d_audio_bytes_for_path(source_path):
    source_path = normalise_type_d_audio_path(
        source_path,
        audio_root=IKF_SOURCE_VOLUME_ROOT.rstrip("/") + "/audios",
    )
    audio_bytes = download_source_file_as_user(source_path)
    if len(audio_bytes) > 100 * 1024 * 1024:
        raise ValueError("Source audio exceeds the current App review size limit")
    return audio_bytes


def load_type_d_audio_bytes(record):
    audio_bytes = load_type_d_audio_bytes_for_path(
        record.get("source_path") or ""
    )
    if hashlib.sha256(audio_bytes).hexdigest() != record.get("source_sha256"):
        raise ValueError("Original audio hash does not match transcript provenance")
    return audio_bytes


def create_transcription_run(*, source_path, source_name, model):
    source_path = normalise_type_d_audio_path(
        source_path,
        audio_root=IKF_SOURCE_VOLUME_ROOT.rstrip("/") + "/audios",
    )
    model = normalise_transcription_model(model)
    run_id = "transcription_" + uuid.uuid4().hex
    with get_driver().session() as session:
        session.run(
            """
            CREATE (r:TranscriptionRun {
                transcription_run_id: $run_id,
                source_path: $source_path,
                source_name: $source_name,
                model: $model,
                classification: 'D',
                status: 'PENDING',
                processing_stage: 'PENDING',
                created_by: $created_by,
                created_at: datetime(),
                updated_at: datetime()
            })
            """,
            run_id=run_id,
            source_path=source_path,
            source_name=source_name,
            model=model,
            created_by=get_current_user_key(),
        ).consume()
    return run_id


def load_latest_transcription_run(source_path, model):
    with get_driver().session() as session:
        record = session.run(
            """
            MATCH (r:TranscriptionRun {
                source_path: $source_path,
                model: $model,
                classification: 'D'
            })
            RETURN
                r.transcription_run_id AS transcription_run_id,
                r.status AS status,
                r.processing_stage AS processing_stage,
                r.job_run_id AS job_run_id,
                r.source_sha256 AS source_sha256,
                r.output_path AS output_path,
                r.detected_language AS detected_language,
                r.language_probability AS language_probability,
                r.duration_s AS duration_s,
                r.elapsed_s AS elapsed_s,
                r.real_time_factor AS real_time_factor,
                r.device AS device,
                r.compute_type AS compute_type,
                r.error_message AS error_message,
                toString(r.created_at) AS created_at,
                toString(r.updated_at) AS updated_at
            ORDER BY r.created_at DESC
            LIMIT 1
            """,
            source_path=source_path,
            model=model,
        ).single()
    return record.data() if record else None


def trigger_type_d_transcription_job(transcription_run_id):
    if not TRANSCRIPTION_JOB_ID:
        raise RuntimeError(
            "The Type D transcription Job is not attached to this App."
        )

    response = get_workspace_client().api_client.do(
        "POST",
        "/api/2.2/jobs/run-now",
        body={
            "job_id": int(TRANSCRIPTION_JOB_ID),
            "job_parameters": {
                "action": "TRANSCRIBE",
                "transcription_run_id": transcription_run_id,
            },
        },
    )
    job_run_id = response.get("run_id")
    if not job_run_id:
        raise RuntimeError("Databricks did not return a transcription Job run_id")

    with get_driver().session() as session:
        session.run(
            """
            MATCH (r:TranscriptionRun {transcription_run_id: $run_id})
            SET r.status = 'QUEUED',
                r.processing_stage = 'JOB_QUEUED',
                r.job_run_id = $job_run_id,
                r.updated_at = datetime(),
                r.error_message = NULL
            """,
            run_id=transcription_run_id,
            job_run_id=str(job_run_id),
        ).consume()
    return str(job_run_id)


def save_transcript_review(record, reviewed_text):
    reviewer = get_current_user_key()
    reviewed_text = str(reviewed_text or "").strip()
    if not reviewed_text:
        raise ValueError("A reviewed transcript is required")
    if not DIRECT_TEXT_ENCRYPTION_KEY:
        raise RuntimeError(
            "Secure transcript-review encryption is not configured."
        )

    text_hash = hashlib.sha256(reviewed_text.encode("utf-8")).hexdigest()
    identity = hashlib.sha256(
        (
            record["source_sha256"]
            + "|"
            + record["model"]
            + "|"
            + text_hash
        ).encode("utf-8")
    ).hexdigest()[:24]
    review_id = "transcript_review_" + identity
    encrypted_text = encrypt_direct_text(reviewed_text)

    with get_driver().session() as session:
        result = session.run(
            """
            MERGE (r:TypeDTranscriptReview {review_id: $review_id})
            ON CREATE SET
                r.created_at = datetime(),
                r.publication_status = 'PENDING'
            SET
                r.source_sha256 = $source_sha256,
                r.source_name = $source_name,
                r.source_path = $source_path,
                r.model = $model,
                r.reviewed_text_sha256 = $text_hash,
                r.encrypted_text = $encrypted_text,
                r.encryption_scheme = 'FERNET',
                r.reviewed_by = $reviewer,
                r.reviewed_at = datetime(),
                r.status = 'HUMAN_REVIEWED',
                r.updated_at = datetime()
            RETURN
                r.review_id AS review_id,
                r.publication_status AS publication_status,
                r.source_document_id AS source_document_id
            """,
            review_id=review_id,
            source_sha256=record["source_sha256"],
            source_name=record.get("source_name"),
            source_path=record.get("source_path"),
            model=record["model"],
            text_hash=text_hash,
            encrypted_text=encrypted_text,
            reviewer=reviewer,
        ).single()

    payload = result.data() if result else {}
    payload["reviewed_text_sha256"] = text_hash
    return payload


def load_latest_transcript_review(source_sha256, model):
    with get_driver().session() as session:
        record = session.run(
            """
            MATCH (r:TypeDTranscriptReview {
                source_sha256: $source_sha256,
                model: $model,
                status: 'HUMAN_REVIEWED'
            })
            RETURN
                r.review_id AS review_id,
                r.reviewed_text_sha256 AS reviewed_text_sha256,
                r.encrypted_text AS encrypted_text,
                r.encryption_scheme AS encryption_scheme,
                r.publication_status AS publication_status,
                r.publication_job_run_id AS publication_job_run_id,
                r.publication_error AS publication_error,
                r.source_document_id AS source_document_id,
                toString(r.reviewed_at) AS reviewed_at,
                toString(r.published_at) AS published_at
            ORDER BY r.reviewed_at DESC
            LIMIT 1
            """,
            source_sha256=source_sha256,
            model=model,
        ).single()
    return record.data() if record else None


def trigger_transcript_publication_job(review_id):
    if not TRANSCRIPTION_JOB_ID:
        raise RuntimeError(
            "The Type D transcription Job is not attached to this App."
        )

    response = get_workspace_client().api_client.do(
        "POST",
        "/api/2.2/jobs/run-now",
        body={
            "job_id": int(TRANSCRIPTION_JOB_ID),
            "job_parameters": {
                "action": "PUBLISH_REVIEW",
                "review_id": review_id,
            },
        },
    )
    job_run_id = response.get("run_id")
    if not job_run_id:
        raise RuntimeError("Databricks did not return a publication Job run_id")

    with get_driver().session() as session:
        session.run(
            """
            MATCH (r:TypeDTranscriptReview {review_id: $review_id})
            SET r.publication_status = 'QUEUED',
                r.publication_job_run_id = $job_run_id,
                r.publication_error = NULL,
                r.updated_at = datetime()
            """,
            review_id=review_id,
            job_run_id=str(job_run_id),
        ).consume()
    return str(job_run_id)


def load_accepted_transcript_document(source_path, model):
    with get_driver().session() as session:
        record = session.run(
            """
            MATCH (d:SourceDocument)
            WHERE d.audio_source_path = $source_path
              AND d.transcript_model = $model
              AND d.information_class = 'D'
              AND d.document_kind = 'TRANSCRIPT'
              AND coalesce(d.catalogue_status, 'AVAILABLE') = 'AVAILABLE'
            RETURN
                d.document_id AS document_id,
                d.filename AS filename,
                d.volume_path AS volume_path,
                d.sha256 AS sha256,
                d.transcript_review_id AS transcript_review_id,
                toString(d.validated_at) AS validated_at
            ORDER BY d.validated_at DESC
            LIMIT 1
            """,
            source_path=source_path,
            model=model,
        ).single()
    return record.data() if record else None


def transcript_text_with_timestamps'''

_TAB_PATTERN = re.compile(
    r"with tab_transcriptions:\n.*?\nwith tab_new_analysis:",
    re.DOTALL,
)

_TAB_REPLACEMENT = '''with tab_transcriptions:
    st.subheader("Type D audio transcriptions")
    st.caption(
        "Select any governed audio recording, transcribe it, validate the machine "
        "transcript against the original audio, and accept it. Once accepted, the "
        "validated transcript appears automatically as a normal Class D document in "
        "Analyse Documents."
    )

    # Retire the former direct-text hand-off if an older browser session still
    # contains it. Accepted transcripts now enter Analyse Documents only through
    # the ordinary Class-D SourceDocument catalogue.
    st.session_state.pop("transcript_analysis_origin", None)

    if not type_d_transcript_access():
        st.error(
            "Your authenticated App user identity could not be resolved. "
            "Type D audio processing is blocked."
        )
    else:
        try:
            audio_sources = list_type_d_audio_sources()
        except (OSError, ValueError, PermissionError, FileNotFoundError) as exc:
            audio_sources = []
            st.error(
                "The governed Type D audio folder could not be listed through "
                "your Databricks user access."
            )
            st.caption(str(exc))

        if not audio_sources:
            st.info("No supported audio recordings are available in the governed audio folder.")
        else:
            audio_by_path = {
                item["path"]: item
                for item in audio_sources
            }
            selected_audio_path = st.selectbox(
                "Audio recording",
                options=list(audio_by_path),
                format_func=lambda value: audio_by_path[value]["name"],
                key="type_d_audio_selection",
            )
            selected_audio = audio_by_path[selected_audio_path]

            model = st.selectbox(
                "Transcription model",
                options=["turbo", "large-v3"],
                index=0,
                format_func=lambda value: (
                    "Whisper large-v3-turbo" if value == "turbo" else "Whisper large-v3"
                ),
                key="type_d_audio_model",
                help=(
                    "Turbo is the current CPU cost/performance candidate. Machine output "
                    "remains unverified regardless of model and must pass human review."
                ),
            )

            accepted_document = load_accepted_transcript_document(
                selected_audio_path,
                model,
            )
            machine_path, machine_record = find_type_d_machine_transcript(
                selected_audio_path,
                model,
            )
            transcription_run = load_latest_transcription_run(
                selected_audio_path,
                model,
            )

            st.markdown("### Processing")
            process_status = (
                "VALIDATED"
                if accepted_document
                else (
                    "MACHINE TRANSCRIPT READY"
                    if machine_record
                    else (
                        (transcription_run or {}).get("status")
                        or "NOT STARTED"
                    )
                )
            )
            process_stage = (
                "CLASS D DOCUMENT AVAILABLE"
                if accepted_document
                else (
                    "HUMAN REVIEW REQUIRED"
                    if machine_record
                    else (
                        (transcription_run or {}).get("processing_stage")
                        or "SELECT AND TRANSCRIBE"
                    )
                )
            )

            status_col, stage_col, run_col, refresh_col = st.columns(
                [1.0, 1.45, 1.0, 0.35]
            )
            status_col.metric("Status", process_status)
            stage_col.metric("Stage", process_stage)
            run_col.metric(
                "Job run",
                (transcription_run or {}).get("job_run_id") or "—",
            )
            with refresh_col:
                st.caption("Refresh")
                if st.button(
                    "↻",
                    key=(
                        "refresh_transcription_"
                        + hashlib.sha256(
                            (selected_audio_path + "|" + model).encode("utf-8")
                        ).hexdigest()[:12]
                    ),
                    help="Refresh transcription/publication status",
                    use_container_width=True,
                ):
                    load_source_documents.clear()
                    st.rerun()

            if transcription_run and transcription_run.get("error_message"):
                st.error(transcription_run["error_message"])

            if accepted_document:
                st.success(
                    "Validated transcript is available as a Class D document: "
                    + str(accepted_document.get("filename") or accepted_document["document_id"])
                )
                load_source_documents.clear()

            if not machine_record:
                if not TRANSCRIPTION_JOB_ID:
                    st.warning(
                        "The Type D transcription Job is not attached to this App. "
                        "Add the Lakeflow Job resource with key transcription_job and Can manage run permission."
                    )
                running = bool(
                    transcription_run
                    and transcription_run.get("status") in {"PENDING", "QUEUED", "RUNNING"}
                )
                button_label = (
                    "Transcription processing…"
                    if running
                    else (
                        "Retry transcription"
                        if transcription_run and transcription_run.get("status") == "FAILED"
                        else "Transcribe selected audio"
                    )
                )
                if st.button(
                    button_label,
                    type="primary",
                    disabled=running or not TRANSCRIPTION_JOB_ID,
                    key="start_selected_audio_transcription",
                ):
                    try:
                        new_run_id = create_transcription_run(
                            source_path=selected_audio_path,
                            source_name=selected_audio["name"],
                            model=model,
                        )
                        job_run_id = trigger_type_d_transcription_job(new_run_id)
                        st.success(
                            "Transcription queued. Job run: " + job_run_id
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error("The transcription could not be started.")
                        st.caption(str(exc))

            if machine_record:
                st.divider()
                st.markdown("### Review and validate")
                st.warning(
                    "Machine-generated transcript — not validated evidence. "
                    "Listen to the original recording and correct uncertain or inaudible spans."
                )

                try:
                    audio_bytes = load_type_d_audio_bytes(machine_record)
                    audio_verified = True
                    st.audio(audio_bytes)
                except (OSError, ValueError, PermissionError) as exc:
                    audio_verified = False
                    st.error(
                        "The original audio could not be loaded and verified. "
                        "Acceptance is blocked."
                    )
                    st.caption(str(exc))

                machine_text = transcript_text_with_timestamps(machine_record)
                st.text_area(
                    "Timestamped machine transcript",
                    machine_text,
                    height=300,
                    disabled=True,
                    key=(
                        "machine_transcript_"
                        + machine_record["source_sha256"][:12]
                        + "_"
                        + model
                    ),
                )
                st.download_button(
                    "Download machine transcript (.txt)",
                    data=machine_text.encode("utf-8"),
                    file_name=(
                        machine_record["source_sha256"][:16]
                        + "_"
                        + model
                        + "_unverified.txt"
                    ),
                    mime="text/plain",
                    key="download_type_d_machine_transcript",
                )

                latest_review = load_latest_transcript_review(
                    machine_record["source_sha256"],
                    model,
                )
                reviewed_default = machine_text
                if (
                    latest_review
                    and latest_review.get("encrypted_text")
                    and latest_review.get("encryption_scheme") == "FERNET"
                ):
                    try:
                        reviewed_default = decrypt_direct_text(
                            latest_review["encrypted_text"]
                        )
                    except Exception:
                        reviewed_default = machine_text

                reviewed_text = st.text_area(
                    "Reviewed transcript",
                    value=reviewed_default,
                    height=360,
                    key=(
                        "reviewed_transcript_"
                        + machine_record["source_sha256"][:12]
                        + "_"
                        + model
                    ),
                    help=(
                        "Correct only after listening. Keep timestamps, mark inaudible "
                        "spans explicitly, and do not infer missing words from context or an LLM."
                    ),
                )
                st.download_button(
                    "Download reviewed transcript (.txt)",
                    data=reviewed_text.encode("utf-8"),
                    file_name=(
                        Path(machine_record.get("source_name") or "audio").stem
                        + "_validated_transcript.txt"
                    ),
                    mime="text/plain",
                    key="download_type_d_reviewed_transcript",
                )

                confirmed = st.checkbox(
                    "I listened to the original audio and checked this transcript; "
                    "corrections and inaudible spans are explicit.",
                    key=(
                        "confirm_transcript_"
                        + machine_record["source_sha256"][:12]
                        + "_"
                        + model
                    ),
                )

                publication_status = (
                    (latest_review or {}).get("publication_status")
                    or ("PUBLISHED" if accepted_document else "NOT ACCEPTED")
                )
                pub_status_col, pub_run_col, pub_refresh_col = st.columns(
                    [1.35, 1.0, 0.35]
                )
                pub_status_col.metric("Validation / publication", publication_status)
                pub_run_col.metric(
                    "Publication run",
                    (latest_review or {}).get("publication_job_run_id") or "—",
                )
                with pub_refresh_col:
                    st.caption("Refresh")
                    if st.button(
                        "↻",
                        key=(
                            "refresh_transcript_publication_"
                            + machine_record["source_sha256"][:12]
                            + "_"
                            + model
                        ),
                        help="Refresh validation/publication status",
                        use_container_width=True,
                    ):
                        load_source_documents.clear()
                        st.rerun()

                if latest_review and latest_review.get("publication_error"):
                    st.error(latest_review["publication_error"])

                publication_busy = publication_status in {"PENDING", "QUEUED", "RUNNING"}
                if not accepted_document:
                    if not DIRECT_TEXT_ENCRYPTION_KEY:
                        st.error(
                            "Secure transcript-review encryption is not configured; acceptance is blocked."
                        )
                    if not TRANSCRIPTION_JOB_ID:
                        st.warning(
                            "The Type D transcription Job is required to publish an accepted transcript as a Class D document."
                        )

                    if st.button(
                        "Accept validated transcript",
                        type="primary",
                        disabled=not (
                            audio_verified
                            and confirmed
                            and reviewed_text.strip()
                            and DIRECT_TEXT_ENCRYPTION_KEY
                            and TRANSCRIPTION_JOB_ID
                            and not publication_busy
                        ),
                        key="accept_validated_transcript",
                    ):
                        try:
                            review = save_transcript_review(
                                machine_record,
                                reviewed_text,
                            )
                            if review.get("publication_status") != "PUBLISHED":
                                publication_job_run_id = trigger_transcript_publication_job(
                                    review["review_id"]
                                )
                                st.success(
                                    "Validated transcript accepted and publication queued. "
                                    "Job run: " + publication_job_run_id
                                )
                            else:
                                st.success(
                                    "This exact validated transcript is already available as a Class D document."
                                )
                            load_source_documents.clear()
                            st.rerun()
                        except Exception as exc:
                            st.error("The validated transcript could not be accepted/published.")
                            st.caption(str(exc))

with tab_new_analysis:'''


def transform_app_audio_source(source: str) -> tuple[str, tuple[str, ...]]:
    """Materialize the single governed audio workflow into the App source."""

    applied: list[str] = []

    if _ENV_ANCHOR not in source:
        raise RuntimeError("IKF App audio adoption could not locate Job environment anchor")
    source = source.replace(_ENV_ANCHOR, _ENV_REPLACEMENT, 1)
    applied.append("transcription_job_environment")

    if _IMPORT_ANCHOR not in source:
        raise RuntimeError("IKF App audio adoption could not locate import anchor")
    source = source.replace(_IMPORT_ANCHOR, _IMPORT_REPLACEMENT, 1)
    applied.append("transcription_governance_import")

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
            "IKF App audio adoption failed at transcript workflow helpers: "
            f"expected exactly one match, found {helper_count}."
        )
    applied.append("user_scoped_audio_and_transcript_files_api")
    applied.append("transcription_job_orchestration")
    applied.append("transcript_review_publication")

    catalogue_field = (
        "        d.source_type AS source_type,\n"
        "        d.byte_size AS byte_size,\n"
    )
    catalogue_replacement = (
        "        d.source_type AS source_type,\n"
        "        properties(d)[\"information_class\"] AS information_class,\n"
        "        d.byte_size AS byte_size,\n"
    )
    catalogue_count = source.count(catalogue_field)
    if catalogue_count < 1:
        raise RuntimeError(
            "IKF App audio adoption could not expose SourceDocument information_class"
        )
    source = source.replace(catalogue_field, catalogue_replacement)
    applied.append("class_d_transcript_catalogue_scope")

    source, tab_count = _TAB_PATTERN.subn(
        _TAB_REPLACEMENT,
        source,
        count=1,
    )
    if tab_count != 1:
        raise RuntimeError(
            "IKF App audio adoption failed at Transcriptions workspace: "
            f"expected exactly one match, found {tab_count}."
        )
    applied.append("single_transcription_workspace")

    return source, tuple(applied)
