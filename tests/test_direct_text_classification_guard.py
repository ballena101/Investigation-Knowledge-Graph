from pathlib import Path

from ikf.app_direct_text_classification_guard import (
    DIRECT_TEXT_CLASSIFICATION_GUARD_VERSION,
    transform_app_direct_text_classification_guard,
)


def test_direct_text_requires_explicit_information_classification():
    source = Path("app/app.py").read_text(encoding="utf-8")
    transformed, applied = transform_app_direct_text_classification_guard(source)

    assert DIRECT_TEXT_CLASSIFICATION_GUARD_VERSION == "IKF_DIRECT_TEXT_CLASSIFICATION_GUARD_V0.1.3"
    assert "explicit_information_class_selection" in applied
    assert "unclassified_catalogue_fail_closed" in applied
    assert "direct_text_constructor_fail_closed" in applied
    assert 'options=[None] + list(INFORMATION_CLASSES)' in transformed
    assert 'disabled=not classification_selected' in transformed
    assert 'if not classification_selected:\n        available_documents = []' in transformed
    assert (
        "Direct text requires an explicit valid information classification."
        in transformed
    )
    assert (
        "Select an information classification before processing this input."
        in transformed
    )

    compile(transformed, "app/app.py", "exec")
