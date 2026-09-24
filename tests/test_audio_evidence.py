from ikf.audio_evidence import (
    AudioEvidenceLocation,
    audio_evidence_reference,
    extract_audio_time_range,
    parse_audio_evidence_location,
)


SHA = "a" * 64


def test_extract_audio_time_range_envelopes_reviewed_lines():
    text = (
        "[00:05:28–00:05:34] First reviewed line\n"
        "[00:05:40–00:05:43] Second reviewed line"
    )
    assert extract_audio_time_range(text) == (328.0, 343.0)


def test_extract_audio_time_range_returns_none_without_timestamps():
    assert extract_audio_time_range("plain text") is None


def test_audio_location_round_trip():
    location = AudioEvidenceLocation(
        source_sha256=SHA,
        start_s=328.125,
        end_s=343.875,
    )
    parsed = parse_audio_evidence_location(location.serialise())
    assert parsed.source_sha256 == SHA
    assert parsed.start_s == 328.125
    assert parsed.end_s == 343.875


def test_audio_reference_is_investigator_readable():
    location = AudioEvidenceLocation(
        source_sha256=SHA,
        start_s=328,
        end_s=343,
    )
    assert audio_evidence_reference(
        source_name="VHF call.wav",
        location=location,
    ) == "VHF call.wav · 00:05:28–00:05:43"
