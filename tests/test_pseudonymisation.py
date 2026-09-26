from ikf.pseudonymisation import pseudonymise_text


def test_structured_identifiers_are_replaced_consistently():
    text = (
        "Contact john@example.org or john@example.org. "
        "IMO 1234567 and MMSI 123456789 remain selectable identifiers."
    )
    result = pseudonymise_text(
        text,
        categories=["EMAIL", "IMO", "MMSI"],
    )

    assert result["text"].count("EMAIL_001") == 2
    assert "IMO_001" in result["text"]
    assert "MMSI_001" in result["text"]
    assert result["mapping"]["EMAIL_001"] == "john@example.org"


def test_manual_person_terms_preserve_relationship_text():
    text = "Chief engineer John Smith instructed Jane Brown to inspect the pump."
    result = pseudonymise_text(
        text,
        categories=["PERSON"],
        manual_terms={"PERSON": ["John Smith", "Jane Brown"]},
    )

    assert result["text"] == (
        "Chief engineer PERSON_001 instructed PERSON_002 to inspect the pump."
    )
    assert result["mapping"] == {
        "PERSON_001": "John Smith",
        "PERSON_002": "Jane Brown",
    }


def test_unselected_categories_are_not_changed():
    text = "IMO 1234567 john@example.org"
    result = pseudonymise_text(text, categories=["EMAIL"])
    assert "IMO 1234567" in result["text"]
    assert "EMAIL_001" in result["text"]
