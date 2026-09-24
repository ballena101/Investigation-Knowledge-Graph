"""Materialize resilient user-scoped Databricks Files API downloads.

The IKF App reads protected source files with the logged-in user's forwarded
Databricks token. A single large ``response.read()`` is vulnerable to a
transient connection close near the end of an otherwise successful download.

Databricks Files API supports HEAD metadata requests, byte-range GET requests
and If-Unmodified-Since. This adoption replaces the legacy one-shot download
with small verified ranges. Only a failed range is retried, and ranges are
conditionally read against the same Last-Modified value when available.
"""

from __future__ import annotations

import re


FILES_API_DOWNLOAD_ADOPTION_VERSION = "IKF_APP_FILES_API_DOWNLOAD_V0.1"

_IMPORT_ANCHOR = "import urllib.request\n"
_IMPORT_REPLACEMENT = _IMPORT_ANCHOR + "import http.client\nimport socket\nimport time\n"

_DOWNLOAD_PATTERN = re.compile(
    r"def download_source_file_as_user\(path\):\n.*?\n\ndef parse_evidence_location",
    re.DOTALL,
)

_DOWNLOAD_REPLACEMENT = '''FILES_API_DOWNLOAD_CHUNK_BYTES = 4 * 1024 * 1024
FILES_API_DOWNLOAD_MAX_ATTEMPTS = 3


def _raise_source_files_api_http_error(exc):
    if exc.code in {401, 403}:
        raise PermissionError(
            "You are not authorised to read this source document from its "
            "Unity Catalog volume."
        ) from exc
    if exc.code == 404:
        raise FileNotFoundError(
            "The source document is no longer available at the registered "
            "Unity Catalog path."
        ) from exc
    if exc.code == 412:
        raise RuntimeError(
            "The source file changed while it was being downloaded. Refresh "
            "the source and try again."
        ) from exc
    raise RuntimeError(
        f"Databricks Files API returned HTTP {exc.code}."
    ) from exc


def _source_files_api_metadata(url, token):
    """Return Content-Length and Last-Modified with transient retries."""

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept-Encoding": "identity",
        },
        method="HEAD",
    )
    last_error = None
    for attempt in range(FILES_API_DOWNLOAD_MAX_ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw_length = response.headers.get("Content-Length")
                if raw_length is None:
                    raise OSError(
                        "Databricks Files API did not return Content-Length metadata."
                    )
                total_size = int(raw_length)
                if total_size < 0:
                    raise OSError("Databricks Files API returned an invalid file size.")
                return total_size, response.headers.get("Last-Modified")
        except urllib.error.HTTPError as exc:
            _raise_source_files_api_http_error(exc)
        except (
            http.client.IncompleteRead,
            http.client.RemoteDisconnected,
            ConnectionResetError,
            TimeoutError,
            socket.timeout,
            urllib.error.URLError,
            OSError,
        ) as exc:
            last_error = exc
            if attempt + 1 >= FILES_API_DOWNLOAD_MAX_ATTEMPTS:
                break
            time.sleep(0.25 * (attempt + 1))

    raise OSError(
        "Databricks Files API metadata request failed after transient retries."
    ) from last_error


def _source_files_api_range(url, token, start, end, total_size, last_modified):
    """Download and verify one byte range, retrying only that range."""

    expected_length = end - start + 1
    last_error = None

    for attempt in range(FILES_API_DOWNLOAD_MAX_ATTEMPTS):
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept-Encoding": "identity",
            "Range": f"bytes={start}-{end}",
        }
        if last_modified:
            headers["If-Unmodified-Since"] = last_modified

        request = urllib.request.Request(
            url,
            headers=headers,
            method="GET",
        )

        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                status = getattr(response, "status", response.getcode())
                content_range = response.headers.get("Content-Range")
                body = response.read()

            # RFC-compliant range response. Validate both coordinates and byte
            # count before appending anything to the assembled file.
            if status == 206:
                expected_prefix = f"bytes {start}-{end}/"
                if content_range and not content_range.startswith(expected_prefix):
                    raise OSError(
                        "Databricks Files API returned an unexpected Content-Range."
                    )
                if len(body) != expected_length:
                    raise http.client.IncompleteRead(
                        body,
                        expected_length - len(body),
                    )
                return body, False

            # Defensive fallback if an intermediary ignores Range but returns
            # the complete file on the first request.
            if status == 200 and start == 0 and len(body) == total_size:
                return body, True

            raise OSError(
                "Databricks Files API did not honor the requested byte range."
            )

        except urllib.error.HTTPError as exc:
            _raise_source_files_api_http_error(exc)
        except (
            http.client.IncompleteRead,
            http.client.RemoteDisconnected,
            ConnectionResetError,
            TimeoutError,
            socket.timeout,
            urllib.error.URLError,
            OSError,
        ) as exc:
            last_error = exc
            if attempt + 1 >= FILES_API_DOWNLOAD_MAX_ATTEMPTS:
                break
            time.sleep(0.25 * (attempt + 1))

    raise OSError(
        "Databricks Files API download failed after retries for byte range "
        f"{start}-{end}."
    ) from last_error


def download_source_file_as_user(path):
    """Read a UC-volume file through Databricks Files API as the logged-in user.

    Files are downloaded in verified 4 MiB ranges. A transient short read or
    connection close retries only the affected range instead of restarting the
    whole protected file download.
    """

    normalized = normalise_allowed_source_path(path)
    token = get_user_access_token()

    if not token:
        raise PermissionError(
            "No forwarded Databricks user token is available. "
            "User authorization with the files scope is required."
        )

    host = get_workspace_client().config.host.rstrip("/")
    encoded_path = urllib.parse.quote(normalized, safe="/")
    url = host + "/api/2.0/fs/files" + encoded_path

    total_size, last_modified = _source_files_api_metadata(url, token)
    if total_size == 0:
        return b""

    assembled = bytearray()
    start = 0
    while start < total_size:
        end = min(
            start + FILES_API_DOWNLOAD_CHUNK_BYTES - 1,
            total_size - 1,
        )
        chunk, complete_file = _source_files_api_range(
            url,
            token,
            start,
            end,
            total_size,
            last_modified,
        )
        if complete_file:
            return chunk
        assembled.extend(chunk)
        start = end + 1

    if len(assembled) != total_size:
        raise OSError(
            "Databricks Files API download size did not match file metadata."
        )
    return bytes(assembled)


def parse_evidence_location'''


def transform_app_files_api_source(source: str) -> tuple[str, tuple[str, ...]]:
    """Replace the App's one-shot Files API download with resilient ranges."""

    applied: list[str] = []

    if "import http.client\n" not in source:
        if _IMPORT_ANCHOR not in source:
            raise RuntimeError(
                "IKF Files API adoption could not locate the urllib import anchor."
            )
        source = source.replace(
            _IMPORT_ANCHOR,
            _IMPORT_REPLACEMENT,
            1,
        )
    applied.append("files_api_transport_imports")

    source, count = _DOWNLOAD_PATTERN.subn(
        _DOWNLOAD_REPLACEMENT,
        source,
        count=1,
    )
    if count != 1:
        raise RuntimeError(
            "IKF Files API adoption failed at source download helper: "
            f"expected exactly one match, found {count}."
        )
    applied.append("ranged_files_api_download")

    return source, tuple(applied)
