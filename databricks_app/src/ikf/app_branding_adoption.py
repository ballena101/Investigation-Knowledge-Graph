"""Final user-facing branding for the Databricks App."""

from __future__ import annotations


BRANDING_ADOPTION_VERSION = "IKF_APP_BRANDING_ADOPTION_V0.1"


def transform_app_branding_source(source: str) -> tuple[str, tuple[str, ...]]:
    """Apply the approved App name after all other UI transformations."""

    old_title = "Safety Investigation Knowledge & AI Support"
    new_title = "Safety Investigation AI Sandbox"

    page_old = f'page_title="{old_title}"'
    page_new = f'page_title="{new_title}"'
    title_old = f'st.title("{old_title}")'
    title_new = f'st.title("{new_title}")'

    if page_old not in source:
        raise RuntimeError("Branding adoption could not locate the Streamlit page title.")
    if title_old not in source:
        raise RuntimeError("Branding adoption could not locate the visible App title.")

    source = source.replace(page_old, page_new, 1)
    source = source.replace(title_old, title_new, 1)
    return source, ("safety_investigation_ai_sandbox",)
