# Resilient user-scoped Files API downloads

## Problem observed

The Databricks App previously downloaded a governed source file with one call to
`response.read()` against `GET /api/2.0/fs/files...`.

A Type-D audio read failed after receiving 17,580,032 bytes with only 410,552
bytes remaining. Python raised `http.client.IncompleteRead` because the HTTP
connection closed before the advertised response body was complete.

This is a transport failure. It does not indicate a damaged audio file, a
Whisper/transcription failure, or a governance failure.

## Decision

IKF now materializes a resilient Files API downloader into the App.

The downloader:

1. performs `HEAD /api/2.0/fs/files{path}` to obtain `Content-Length` and, when
   available, `Last-Modified`;
2. downloads the file in verified 4 MiB byte ranges using the Files API `Range`
   header;
3. retries only the failed range, up to three attempts;
4. catches transient short reads, remote disconnects, resets and timeouts;
5. sends `If-Unmodified-Since` when `Last-Modified` is available, so a file that
   changes mid-download is rejected rather than assembled from different
   versions;
6. verifies every range length and the final assembled size before returning
   bytes to the caller.

The logged-in user's forwarded Databricks token remains the authorization
boundary. No broader App service-principal Volume access is introduced.

## Scope

`download_source_file_as_user()` is shared by Type-D audio/transcripts and
other App source-file reads, so the resilience improvement applies to the
existing governed file-view path as well.

## Databricks API basis

The Databricks Files API supports:

- `HEAD /api/2.0/fs/files{file_path}`;
- `GET /api/2.0/fs/files{file_path}`;
- `Range` byte requests;
- `If-Unmodified-Since` conditional reads.

The implementation deliberately uses these standard Files API capabilities
instead of increasing the timeout or retrying the entire protected file.

## Cost and runtime impact

This change does not start Databricks compute and does not invoke an LLM.
It may issue several small Files API requests for a large source file instead of
one large request. Only a failed range is retried.

## Deployment contract

The transformation is implemented in:

`src/ikf/app_files_api_adoption.py`

and is materialized into the lean `databricks_app/` bundle by:

`scripts/build_databricks_app_bundle.py`

The raw-bootstrap fallback applies the same transformation through
`app/bootstrap.py`.
