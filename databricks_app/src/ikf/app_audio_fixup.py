"""Strict post-transform fixups for the Type-D transcription workspace.

This tiny layer exists because the canonical App already imports ``Fernet`` but
has no reusable decrypt helper for persisted direct-text payloads. The audio
workspace stores reviewed transcript text with the same FERNET key and needs to
reload it when an investigator returns to the review screen.
"""

from __future__ import annotations


AUDIO_FIXUP_VERSION = "IKF_APP_AUDIO_FIXUP_V0.1"


def transform_app_audio_fixup_source(source: str) -> tuple[str, tuple[str, ...]]:
    old = '''                        reviewed_default = decrypt_direct_text(
                            latest_review["encrypted_text"]
                        )'''
    new = '''                        reviewed_default = Fernet(
                            DIRECT_TEXT_ENCRYPTION_KEY.encode("utf-8")
                        ).decrypt(
                            latest_review["encrypted_text"].encode("utf-8")
                        ).decode("utf-8")'''

    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            "IKF App audio fixup failed at reviewed-transcript decryption: "
            f"expected exactly one match, found {count}."
        )
    return source.replace(old, new, 1), ("reviewed_transcript_decryption",)
