from __future__ import annotations

import pytest

from ikf.transcription_governance import (
    normalise_transcription_model,
    normalise_type_d_audio_path,
    reviewed_transcript_document_id,
    reviewed_transcript_filename,
    transcript_publication_properties,
)


AUDIO_ROOT = "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/audios"
SHA_A = "a" * 64
SHA_B = "b" * 64


def test_audio_path_accepts_direct_governed_child():
    value = normalise_type_d_audio_path(
        AUDIO_ROOT + "/mayday.wav",
        audio_root=AUDIO_ROOT,
    )
    assert value.endswith("/audios/mayday.wav")


def test_audio_path_rejects_outside_or_nested_source():
    with pytest.raises(ValueError):
        normalise_type_d_audio_path(
            "/Volumes/other/audio.wav",
            audio_root=AUDIO_ROOT,
        )
    with pytest.raises(ValueError):
        normalise_type_d_audio_path(
            AUDIO_ROOT + "/nested/audio.wav",
            audio_root=AUDIO_ROOT,
        )


def test_audio_path_rejects_unsupported_extension():
    with pytest.raises(ValueError):
        normalise_type_d_audio_path(
            AUDIO_ROOT + "/notes.txt",
            audio_root=AUDIO_ROOT,
        )


def test_model_fails_closed():
    assert normalise_transcription_model("turbo") == "turbo"
    assert normalise_transcription_model("large-v3") == "large-v3"
    with pytest.raises(ValueError):
        normalise_transcription_model("small")


def test_reviewed_transcript_document_id_is_stable_and_content_bound():
    first = reviewed_transcript_document_id(
        source_sha256=SHA_A,
        reviewed_text_sha256=SHA_B,
        model="turbo",
    )
    second = reviewed_transcript_document_id(
        source_sha256=SHA_A,
        reviewed_text_sha256=SHA_B,
        model="turbo",
    )
    changed = reviewed_transcript_document_id(
        source_sha256=SHA_A,
        reviewed_text_sha256="c" * 64,
        model="turbo",
    )
    assert first == second
    assert first.startswith("doc_")
    assert changed != first


def test_reviewed_transcript_filename_is_investigator_readable():
    assert reviewed_transcript_filename(
        "MV_Summit_Venture_Mayday_Call.flac"
    ) == "MV_Summit_Venture_Mayday_Call — validated transcript.txt"


def test_publication_properties_force_class_d_and_available_catalogue():
    props = transcript_publication_properties(
        source_name="mayday.wav",
        source_path=AUDIO_ROOT + "/mayday.wav",
        source_sha256=SHA_A,
        model="turbo",
        reviewed_text_sha256=SHA_B,
        byte_size=1234,
    )
    assert props["information_class"] == "D"
    assert props["source_managed_by"] == "IKF"
    assert props["source_type"] == "TRANSCRIPT"
    assert props["catalogue_status"] == "AVAILABLE"
    assert props["audio_source_sha256"] == SHA_A
