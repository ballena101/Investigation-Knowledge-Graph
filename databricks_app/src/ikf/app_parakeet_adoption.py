"""Materialize NVIDIA Parakeet as an independent Type-D ASR option."""

from __future__ import annotations


PARAKEET_ADOPTION_VERSION = "IKF_APP_PARAKEET_ADOPTION_V0.3"


def transform_app_parakeet_source(source: str) -> tuple[str, tuple[str, ...]]:
    applied: list[str] = []

    import_old = '''from ikf.transcription_governance import (
    SUPPORTED_AUDIO_EXTENSIONS,
    normalise_transcription_model,
    normalise_type_d_audio_path,
)
'''
    import_new = '''from ikf.transcription_governance import (
    PARAKEET_TDT_06B_V3,
    SUPPORTED_AUDIO_EXTENSIONS,
    model_display_name,
    normalise_transcription_model,
    normalise_type_d_audio_path,
)
'''
    if import_old not in source:
        raise RuntimeError("Parakeet adoption could not locate transcription imports")
    source = source.replace(import_old, import_new, 1)
    applied.append("parakeet_governance_imports")

    whisper_only_regex = '(?:large-v3|turbo)\\.json'
    parakeet_regex = '(?:large-v3|turbo|parakeet-tdt-0\\.6b-v3)\\.json'
    regex_count = source.count(whisper_only_regex)
    if regex_count < 2:
        raise RuntimeError(
            "Parakeet adoption expected both transcript discovery/validation regexes; "
            f"found {regex_count}."
        )
    source = source.replace(whisper_only_regex, parakeet_regex)
    applied.append("parakeet_transcript_discovery")

    model_old = '''            model = st.selectbox(
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
'''
    model_new = '''            model = st.selectbox(
                "Transcription engine / model",
                options=["turbo", PARAKEET_TDT_06B_V3, "large-v3"],
                index=0,
                format_func=model_display_name,
                key="type_d_audio_model",
                help=(
                    "Whisper large-v3-turbo remains the default. NVIDIA Parakeet TDT "
                    "0.6B v3 is an independent ASR technology for supported languages. "
                    "All machine output remains unverified until human review."
                ),
            )
            run_independent_comparison = st.checkbox(
                "Also run the independent Whisper / Parakeet comparison",
                value=False,
                key="type_d_audio_compare_engines",
                help=(
                    "Queues the alternative ASR engine on the same audio. Results remain "
                    "separate; switch this selector to inspect either transcript. Only the "
                    "human-reviewed transcript is published."
                ),
            )
            if model == PARAKEET_TDT_06B_V3:
                st.caption(
                    "Parakeet supports 25 published languages. Norwegian and Icelandic "
                    "are not in that set; use Whisper for those languages."
                )
'''
    if model_old not in source:
        raise RuntimeError("Parakeet adoption could not locate transcription model selector")
    source = source.replace(model_old, model_new, 1)
    applied.append("parakeet_model_selector")

    run_old = '''                        new_run_id = create_transcription_run(
                            source_path=selected_audio_path,
                            source_name=selected_audio["name"],
                            model=model,
                        )
                        job_run_id = trigger_type_d_transcription_job(new_run_id)
                        st.success(
                            "Transcription queued. Job run: " + job_run_id
                        )
'''
    run_new = '''                        models_to_run = [model]
                        if run_independent_comparison:
                            comparison_model = (
                                "turbo"
                                if model == PARAKEET_TDT_06B_V3
                                else PARAKEET_TDT_06B_V3
                            )
                            if comparison_model not in models_to_run:
                                models_to_run.append(comparison_model)

                        queued_runs = []
                        for requested_model in models_to_run:
                            existing_path, _existing_record = find_type_d_machine_transcript(
                                selected_audio_path,
                                requested_model,
                            )
                            existing_run = load_latest_transcription_run(
                                selected_audio_path,
                                requested_model,
                            )
                            if existing_path or (
                                existing_run
                                and existing_run.get("status") in {"PENDING", "QUEUED", "RUNNING"}
                            ):
                                continue
                            new_run_id = create_transcription_run(
                                source_path=selected_audio_path,
                                source_name=selected_audio["name"],
                                model=requested_model,
                            )
                            job_run_id = trigger_type_d_transcription_job(new_run_id)
                            queued_runs.append(
                                model_display_name(requested_model) + ": " + job_run_id
                            )

                        if queued_runs:
                            st.success("Transcription queued — " + " | ".join(queued_runs))
                        else:
                            st.info("The requested transcript(s) already exist or are processing.")
'''
    if run_old not in source:
        raise RuntimeError("Parakeet adoption could not locate transcription queue action")
    source = source.replace(run_old, run_new, 1)
    applied.append("independent_dual_engine_queue")

    metrics_anchor = '''            if transcription_run and transcription_run.get("error_message"):
                st.error(transcription_run["error_message"])
'''
    metrics_insert = metrics_anchor + '''

            alternative_model = (
                "turbo" if model == PARAKEET_TDT_06B_V3 else PARAKEET_TDT_06B_V3
            )
            _alt_path, alternative_record = find_type_d_machine_transcript(
                selected_audio_path,
                alternative_model,
            )
            if machine_record and alternative_record:
                st.markdown("#### Independent ASR comparison")
                st.dataframe(
                    [
                        {
                            "Engine/model": model_display_name(model),
                            "Runtime (s)": machine_record.get("elapsed_s"),
                            "RTF": machine_record.get("real_time_factor"),
                            "Language": machine_record.get("detected_language") or "—",
                        },
                        {
                            "Engine/model": model_display_name(alternative_model),
                            "Runtime (s)": alternative_record.get("elapsed_s"),
                            "RTF": alternative_record.get("real_time_factor"),
                            "Language": alternative_record.get("detected_language") or "—",
                        },
                    ],
                    hide_index=True,
                    use_container_width=True,
                )
                st.caption(
                    "Independent machine outputs, not a consensus transcript. Switch the "
                    "engine/model selector to inspect either result."
                )
'''
    if metrics_anchor not in source:
        raise RuntimeError("Parakeet adoption could not locate processing metrics anchor")
    source = source.replace(metrics_anchor, metrics_insert, 1)
    applied.append("independent_asr_comparison")

    review_anchor = '''                st.warning(
                    "Machine-generated transcript — not validated evidence. "
                    "Listen to the original recording and correct uncertain or inaudible spans."
                )
'''
    review_insert = review_anchor + '''                st.caption(
                    "Engine: "
                    + str(machine_record.get("engine") or "—")
                    + " · version: "
                    + str(machine_record.get("engine_version") or "—")
                    + " · model: "
                    + model_display_name(model)
                )
'''
    if review_anchor not in source:
        raise RuntimeError("Parakeet adoption could not locate transcript review warning")
    source = source.replace(review_anchor, review_insert, 1)
    applied.append("asr_engine_provenance_display")

    whisper_caption = '''            st.caption(
                "Transcription engine: faster-whisper 1.2.1 · "
                "Whisper large-v3-turbo or large-v3. Machine output is Class D "
                "and requires human review before publication or analysis."
            )
'''
    dual_caption = '''            st.caption(
                "Transcription engines: faster-whisper 1.2.1 (Whisper large-v3-turbo / "
                "large-v3) and NVIDIA Parakeet TDT 0.6B v3 via Transformers 5.17.0. "
                "Machine output is Class D and requires human review before publication."
            )
'''
    if whisper_caption in source:
        source = source.replace(whisper_caption, dual_caption, 1)
        applied.append("dual_engine_disclosure")

    source = source.replace(
        "- Audio transcription uses **faster-whisper 1.2.1** with Whisper large-v3-turbo\n  or large-v3. Machine transcripts remain unverified until a person listens,\n  corrects and accepts them; the original recording remains authoritative.",
        "- Audio transcription can use **faster-whisper 1.2.1** with Whisper large-v3-turbo/large-v3 or **NVIDIA Parakeet TDT 0.6B v3** through Transformers 5.17.0. Machine transcripts remain unverified until a person listens, corrects and accepts them; the original recording remains authoritative.",
        1,
    )
    applied.append("parakeet_confidentiality_disclosure")

    return source, tuple(applied)
