"""Strict post-transform fixups for the Type-D transcription workspace.

This layer keeps the materialized audio workflow aligned with the main App:
- reviewed Class-D text is decrypted with the existing FERNET control;
- processing metadata uses the compact visual scale of the Active analysis header;
- a transcription remembers the active analysis as non-evidentiary context;
- a published transcript is associated with that analysis without silently adding
  it to ``HAS_SOURCE`` or changing already-completed findings/graph results.
"""

from __future__ import annotations


AUDIO_FIXUP_VERSION = "IKF_APP_AUDIO_FIXUP_V0.2"


def _replace_once(source: str, old: str, new: str, name: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"IKF App audio fixup failed at {name}: expected exactly one match, found {count}."
        )
    return source.replace(old, new, 1)


def transform_app_audio_fixup_source(source: str) -> tuple[str, tuple[str, ...]]:
    applied: list[str] = []

    source = _replace_once(
        source,
        '''                        reviewed_default = decrypt_direct_text(
                            latest_review["encrypted_text"]
                        )''',
        '''                        reviewed_default = Fernet(
                            DIRECT_TEXT_ENCRYPTION_KEY.encode("utf-8")
                        ).decrypt(
                            latest_review["encrypted_text"].encode("utf-8")
                        ).decode("utf-8")''',
        "reviewed-transcript decryption",
    )
    applied.append("reviewed_transcript_decryption")

    source = _replace_once(
        source,
        "def create_transcription_run(*, source_path, source_name, model):",
        "def create_transcription_run(*, source_path, source_name, model, analysis_context_id=None):",
        "transcription context signature",
    )
    source = _replace_once(
        source,
        '''                model: $model,
                classification: 'D',''',
        '''                model: $model,
                analysis_context_id: $analysis_context_id,
                classification: 'D',''',
        "transcription context property",
    )
    source = _replace_once(
        source,
        '''            model=model,
            created_by=get_current_user_key(),''',
        '''            model=model,
            analysis_context_id=analysis_context_id,
            created_by=get_current_user_key(),''',
        "transcription context parameter",
    )
    source = _replace_once(
        source,
        '''                r.job_run_id AS job_run_id,
                r.source_sha256 AS source_sha256,''',
        '''                r.job_run_id AS job_run_id,
                r.analysis_context_id AS analysis_context_id,
                r.source_sha256 AS source_sha256,''',
        "transcription context read",
    )
    source = _replace_once(
        source,
        '''                                source_name=selected_audio["name"],
                                model=requested_model,
                            )''',
        '''                                source_name=selected_audio["name"],
                                model=requested_model,
                                analysis_context_id=active_analysis_id,
                            )''',
        "transcription context creation",
    )
    applied.append("active_analysis_transcription_context")

    source = _replace_once(
        source,
        "def save_transcript_review(record, reviewed_text):\n    reviewer = get_current_user_key()\n    reviewed_text = str(reviewed_text or \"\").strip()",
        "def save_transcript_review(record, reviewed_text, analysis_context_id=None):\n    reviewer = get_current_user_key()\n    reviewed_text = str(reviewed_text or \"\").strip()",
        "review context signature",
    )
    source = _replace_once(
        source,
        '''                r.model = $model,
                r.reviewed_text_sha256 = $text_hash,''',
        '''                r.model = $model,
                r.analysis_context_id = $analysis_context_id,
                r.reviewed_text_sha256 = $text_hash,''',
        "review context property",
    )
    source = _replace_once(
        source,
        '''            model=record["model"],
            text_hash=text_hash,''',
        '''            model=record["model"],
            analysis_context_id=analysis_context_id,
            text_hash=text_hash,''',
        "review context parameter",
    )
    source = _replace_once(
        source,
        '''                r.source_document_id AS source_document_id,
                toString(r.reviewed_at) AS reviewed_at,''',
        '''                r.source_document_id AS source_document_id,
                r.analysis_context_id AS analysis_context_id,
                toString(r.reviewed_at) AS reviewed_at,''',
        "review context load",
    )
    source = _replace_once(
        source,
        '''                            review = save_transcript_review(
                                machine_record,
                                reviewed_text,
                            )''',
        '''                            review = save_transcript_review(
                                machine_record,
                                reviewed_text,
                                analysis_context_id=(transcription_run or {}).get(
                                    "analysis_context_id"
                                ) or active_analysis_id,
                            )''',
        "review context save",
    )

    helper_anchor = "def trigger_transcript_publication_job(review_id):\n"
    helper = '''def ensure_transcript_analysis_association(document_id, analysis_context_id):
    """Persist case context without changing the analysis evidence set."""
    if not document_id or not analysis_context_id:
        return False
    with get_driver().session() as session:
        record = session.run(
            """
            MATCH (d:SourceDocument {document_id: $document_id})
            MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
            MERGE (d)-[rel:ASSOCIATED_WITH_ANALYSIS]->(a)
            SET rel.context_only = true,
                rel.updated_at = datetime(),
                rel.updated_by = $updated_by
            RETURN d.document_id AS document_id
            """,
            document_id=document_id,
            analysis_id=analysis_context_id,
            updated_by=get_current_user_key(),
        ).single()
    return record is not None


'''
    source = _replace_once(
        source,
        helper_anchor,
        helper + helper_anchor,
        "analysis association helper",
    )
    source = _replace_once(
        source,
        '''                latest_review = load_latest_transcript_review(
                    machine_record["source_sha256"],
                    model,
                )
                reviewed_default = machine_text''',
        '''                latest_review = load_latest_transcript_review(
                    machine_record["source_sha256"],
                    model,
                )
                if accepted_document and latest_review:
                    ensure_transcript_analysis_association(
                        accepted_document.get("document_id"),
                        latest_review.get("analysis_context_id"),
                    )
                reviewed_default = machine_text''',
        "published transcript analysis association",
    )
    applied.append("published_transcript_analysis_association")

    source = _replace_once(
        source,
        '''            st.markdown("### Processing")
            process_status = (''',
        '''            if active_analysis_id and active_analysis:
                st.caption(
                    "Investigation context: "
                    + str(active_analysis.get("analysis_title") or active_analysis_id)
                    + " · association only; this transcript changes findings/graph only "
                      "when explicitly included in an analysis."
                )
            else:
                st.caption(
                    "No active analysis context. The accepted transcript will remain "
                    "available as a normal Class-D document."
                )

            st.markdown("### Processing")
            process_status = (''',
        "transcription context caption",
    )

    source = _replace_once(
        source,
        '''            status_col, stage_col, run_col, refresh_col = st.columns(
                [1.0, 1.45, 1.0, 0.35]
            )
            status_col.metric("Status", process_status)
            stage_col.metric("Stage", process_stage)
            run_col.metric(
                "Job run",
                (transcription_run or {}).get("job_run_id") or "—",
            )''',
        '''            status_col, stage_col, run_col, refresh_col = st.columns(
                [1.0, 1.45, 1.0, 0.35]
            )
            status_col.markdown(
                '<div style="font-size:0.70rem;color:#6b7280;line-height:1.1;">Status</div>'
                '<div style="font-size:1.05rem;font-weight:600;line-height:1.3;">'
                + html.escape(str(process_status)) + '</div>',
                unsafe_allow_html=True,
            )
            stage_col.markdown(
                '<div style="font-size:0.70rem;color:#6b7280;line-height:1.1;">Stage</div>'
                '<div style="font-size:1.05rem;font-weight:600;line-height:1.3;">'
                + html.escape(str(process_stage)) + '</div>',
                unsafe_allow_html=True,
            )
            run_col.markdown(
                '<div style="font-size:0.70rem;color:#6b7280;line-height:1.1;">Job run</div>'
                '<div style="font-size:1.05rem;font-weight:600;line-height:1.3;">'
                + html.escape(str((transcription_run or {}).get("job_run_id") or "—"))
                + '</div>',
                unsafe_allow_html=True,
            )''',
        "compact processing metadata",
    )
    applied.append("compact_processing_metadata")

    return source, tuple(applied)
