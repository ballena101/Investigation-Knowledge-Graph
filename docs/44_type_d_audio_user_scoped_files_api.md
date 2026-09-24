# Type-D audio access through the logged-in Databricks user

## Decision

Type-D audio and machine-transcript files in the IKF Unity Catalog Volume are read by the Databricks App through the Databricks Files API using the logged-in user's forwarded Databricks token.

The App does **not** require direct local `/Volumes/...` filesystem visibility for Type-D transcript listing or audio/transcript reads, and the IKF App service principal does not need to be granted broad read access to `bdw_analysis_prod.kg_poc.investigation_sources` solely for this feature.

This aligns Type-D audio with the existing MAIRA source-file access pattern.

## Why the previous implementation failed

The first App integration used Python filesystem calls inside the Databricks App process:

- `TYPE_D_TRANSCRIPT_ROOT.is_dir()`
- `TYPE_D_TRANSCRIPT_ROOT.glob("*.json")`
- `Path.open()` for transcript JSON and original audio.

Notebook 61 had successfully created the transcript in the governed Volume, but the App process did not have the same direct filesystem view. The UI therefore incorrectly reported that no transcript was available.

## Existing MAIRA pattern

MAIRA documents are handled in two layers:

1. catalogue metadata is loaded from persisted `SourceDocument` records rather than by browsing the MAIRA Volume from the App process;
2. when the actual source file is required, `download_source_file_as_user()` calls the Databricks Files API using the logged-in user's forwarded token.

This means file access follows the user's Unity Catalog authorization rather than relying on the App service principal's direct filesystem permissions.

## Type-D audio implementation

The materialized App now follows the same principle.

### Transcript listing

`list_uc_directory_as_user()` calls:

`GET /api/2.0/fs/directories/Volumes/...`

using the forwarded logged-in user token and follows `next_page_token` pagination.

Only transcript files matching the governed naming contract are exposed:

`<64-character-source-sha256>__(large-v3|turbo).json`

### Transcript read

`read_type_d_transcript()` downloads the selected transcript using the existing `download_source_file_as_user()` Files API route. It then validates:

- Class D classification;
- `MACHINE_GENERATED_UNVERIFIED` status;
- source SHA-256 consistency with the filename;
- model consistency with the filename;
- segment structure and timestamps;
- current transcript size limit.

### Original audio read

`load_type_d_audio_bytes()`:

- restricts the path to the governed `investigation_sources/audios/` directory;
- downloads through `download_source_file_as_user()`;
- enforces the current App review size limit;
- verifies the audio SHA-256 against transcript provenance before enabling human review.

## Human-review gate

The storage-access change does not relax Type-D governance.

A machine transcript remains `MACHINE_GENERATED_UNVERIFIED`. It can be viewed and corrected by an authenticated IKF App user, but it cannot be promoted into Findings, Evidence, Knowledge Graph relationships, or SHIELD processing until the user confirms that the transcript has been checked against the original audio.

## Deployment impact

No additional Unity Catalog Volume App resource is required solely to enable this user-scoped read path, provided the logged-in user already has the relevant Unity Catalog permissions and the App receives the Databricks user token with the Files API scope.

The lean `databricks_app/` deployment remains the supported runtime source.
