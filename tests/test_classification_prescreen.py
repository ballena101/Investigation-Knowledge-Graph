"""Tests for deterministic IKF information-class pre-screen."""

from ikf.classification_prescreen import (
    combine_results,
    prescreen_metadata,
    prescreen_text,
)


def test_witness_statement_requires_class_d():
    result = prescreen_text(
        "Witness statement: the master described the event."
    )
    assert result.required_class == "D"
    assert "WITNESS_RECORD" in result.rule_ids


def test_vdr_discussion_is_not_raw_vdr_record():
    result = prescreen_text(
        "The published report notes that the VDR was reviewed by investigators."
    )
    assert result.required_class is None


def test_vdr_transcript_is_protected_indicator():
    result = prescreen_text(
        "VDR transcript: 10:21 bridge conversation begins."
    )
    assert result.required_class == "D"
    assert "VDR_RAW_RECORD" in result.rule_ids


def test_generic_public_email_does_not_force_class_d():
    result = prescreen_text(
        "Contact: person@example.org"
    )
    assert result.required_class is None


def test_metadata_rules_are_strong_record_labels():
    result = prescreen_metadata(
        ["case_17_witness_statement.docx"]
    )
    assert result.required_class == "D"


def test_normal_technical_filename_does_not_escalate():
    result = prescreen_metadata(
        ["bridge_resource_management_guidance.pdf"]
    )
    assert result.required_class is None


def test_combined_result_preserves_rule_counts():
    result = combine_results(
        prescreen_text("witness statement"),
        prescreen_metadata(
            ["investigator_notes.txt"]
        ),
    )
    assert result.required_class == "D"
    assert set(result.rule_ids) == {
        "INVESTIGATOR_WORKING_RECORD_METADATA",
        "WITNESS_RECORD",
    }
