from __future__ import annotations

import pytest

from ikf.transcription_governance import (
    PARAKEET_TDT_06B_V3,
    model_display_name,
    normalise_transcription_model,
    normalise_type_d_audio_path,
    parakeet_supports_language,
    reviewed_transcript_document_id,
    reviewed_transcript_filename,
    transcript_publication_properties,
    transcription_engine,
)

AUDIO_ROOT = "/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/audios"
SHA_A = "a" * 64
SHA_B = "b" * 64


def test_audio_path_accepts_direct_governed_child():
    value = normalise_type_d_audio_path(AUDIO_ROOT + "/mayday.wav", audio_root=AUDIO_ROOT)
    assert value.endswith("/audios/mayday.wav")


def test_audio_path_rejects_outside_or_nested_source():
    with pytest.raises(ValueError):
        normalise_type_d_audio_path("/Volumes/other/audio.wav", audio_root=AUDIO_ROOT)
    with pytest.raises(ValueError):
        normalise_type_d_audio_path(AUDIO_ROOT + "/nested/audio.wav", audio_root=AUDIO_ROOT)


def test_audio_path_rejects_unsupported_extension():
    with pytest.raises(ValueError):
        normalise_type_d_audio_path(AUDIO_ROOT + "/notes.txt", audio_root=AUDIO_ROOT)


def test_model_fails_closed_and_supports_independent_asr():
    assert normalise_transcription_model("turbo") == "turbo"
    assert normalise_transcription_model("large-v3") == "large-v3"
    assert normalise_transcription_model(PARAKEET_TDT_06B_V3) == PARAKEET_TDT_06B_V3
    assert transcription_engine("turbo") == "faster-whisper"
    assert transcription_engine(PARAKEET_TDT_06B_V3) == "parakeet"
    assert "Parakeet" in model_display_name(PARAKEET_TDT_06B_V3)
    with pytest.raises(ValueError):
        normalise_transcription_model("small")


def test_parakeet_language_gate_matches_published_scope():
    assert parakeet_supports_language("en")
    assert parakeet_supports_language("es")
    assert parakeet_supports_language("pt")
    assert not parakeet_supports_language("no")
    assert not parakeet_supports_language("is")
    assert parakeet_supports_language(None)


def test_reviewed_transcript_document_id_is_stable_and_content_bound():
    first = reviewed_transcript_document_id(
        source_sha256=SHA_A, reviewed_text_sha256=SHA_B, model="turbo"
    )
    second = reviewed_transcript_document_id(
        source_sha256=SHA_A, reviewed_text_sha256=SHA_B, model="turbo"
    )
    changed = reviewed_transcript_document_id(
        source_sha256=SHA_A, reviewed_text_sha256="c" * 64, model="turbo"
    )
    parakeet = reviewed_transcript_document_id(
        source_sha256=SHA_A, reviewed_text_sha256=SHA_B, model=PARAKEET_TDT_06B_V3
    )
    assert first == second
    assert first.startswith("doc_")
    assert changed != first
    assert parakeet != first


def test_reviewed_transcript_filename_is_investigator_readable():
    assert reviewed_transcript_filename(
        "MV_Summit_Venture_Mayday_Call.flac"
    ) == "MV_Summit_Venture_Mayday_Call — validated transcript.txt"


def test_publication_properties_force_class_d_and_preserve_engine():
    props = transcript_publication_properties(
        source_name="mayday.wav",
        source_path=AUDIO_ROOT + "/mayday.wav",
        source_sha256=SHA_A,
        model=PARAKEET_TDT_06B_V3,
        reviewed_text_sha256=SHA_B,
        byte_size=1234,
    )
    assert props["information_class"] == "D"
    assert props["source_managed_by"] == "IKF"
    assert props["source_repository"] == "IKF_TYPE_D_TRANSCRIPT"
    assert props["source_type"] == "TXT"
    assert props["document_kind"] == "TRANSCRIPT"
    assert props["catalogue_status"] == "AVAILABLE"
    assert props["audio_source_sha256"] == SHA_A
    assert props["transcription_engine"] == "parakeet"
