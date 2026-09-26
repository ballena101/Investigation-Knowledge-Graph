from ikf.pseudonymised_source import processing_policy, validate_processing_class


def test_class_d_derivative_can_remain_d_or_be_reviewed_for_c():
    policy = processing_policy("D")
    assert policy.default_processing_class == "D"
    assert policy.allowed_processing_classes == ("D", "C")
    assert validate_processing_class("D", "C") == "C"


def test_class_d_derivative_cannot_become_a_or_b():
    for target in ("A", "B"):
        try:
            validate_processing_class("D", target)
        except ValueError:
            pass
        else:
            raise AssertionError("Class D pseudonymisation must not auto-downgrade to A/B")


def test_non_d_derivative_keeps_existing_processing_class():
    for source_class in ("A", "B", "C"):
        policy = processing_policy(source_class)
        assert policy.allowed_processing_classes == (source_class,)
