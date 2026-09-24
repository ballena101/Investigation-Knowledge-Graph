# Lean Databricks App deployment — September 2026

## Decision

The IKF repository root remains the authoritative project workspace, containing
notebooks, documentation, tests, scripts, SQL and the canonical `src/ikf`
package. It should no longer be the preferred Databricks App deployment source.

The preferred App source is now the generated, self-contained directory:

`databricks_app/`

This restores the separation between the complete IKF engineering repository
and the small investigator-facing runtime package.

## Why

The repository-root deployment introduced two avoidable startup/deployment
costs:

1. Databricks had to treat the complete repository as the App source, including
   development material that is not needed by Streamlit at runtime.
2. The root launcher executed `app/bootstrap.py`, which read and transformed the
   large historical `app/app.py` source at runtime when the materialized marker
   was absent.

The existing bundle builder already supported the safer target architecture:
materialize governance transformations before cloud runtime, compile the result,
and package only the App plus the required shared IKF modules.

## Materialized source contract

`.github/workflows/materialize-databricks-app.yml` now runs when the App,
`src/ikf`, or the bundle builder changes. It:

1. builds `databricks_app/` with
   `scripts/build_databricks_app_bundle.py`;
2. materializes deterministic governance and UI source transformations;
3. compiles the generated App and shared package;
4. commits the refreshed `databricks_app/` back to `main` only when its contents
   changed.

The generated bundle includes:

- `app.py` — already materialized; no source transformation is needed at App
  startup;
- `app.yaml`;
- `requirements.txt`;
- `bootstrap.py` as a retained compatibility entry point;
- `.ikf_shared_policy_materialized`;
- `ikf_bundle_manifest.json` with source/materialized hashes and adoption
  versions;
- `src/ikf/` containing the required shared package.

The canonical source remains `app/` + `src/ikf/`. `databricks_app/` is a generated
runtime package and should not be hand-edited.

## Databricks switch — one time

After pulling `main`, deploy `investigation-kg-poc` from:

`/Workspace/.../Investigation-Knowledge-Graph-main/databricks_app`

instead of the repository root.

If the App is configured directly from Git rather than a Workspace folder, use
Git branch `main` with source code path:

`databricks_app`

Databricks supports a source-code subdirectory for Git-backed App deployments;
the selected directory becomes the App top-level source.

Do not delete the root launcher yet. Keep it as a compatibility/fallback path
until the lean deployment has been runtime-validated.

## UI adjustment included in this release

The shared active-analysis header is materialized before deployment:

- `Active analysis: <case>` is blue (`#1f77b4`) and visually prominent;
- Active analysis, Class, Sources and Status values use the same 1.05 rem value
  size;
- Class, Sources and Status labels use a smaller 0.70 rem neutral label size;
- the active-analysis column is widened slightly so vessel/case names have more
  room;
- dynamic values are HTML-escaped before rendering.

This is presentation-only. Analysis selection, source counts, information class
and status values are unchanged.

## Validation recorded

The first materialization workflow run completed successfully on 24 September
2026. It passed:

- bundle generation;
- Python compile validation;
- commit of the generated lean source.

Generated bundle commit:

`8a31a29e5340768b34768a94af8f7e7bc146e5d8`

The materialized `app.py` was also checked to confirm the blue active-analysis
header transformation is present.

## Pending runtime validation

- Pull the latest `main` into the Databricks workspace.
- Change the App deployment source from the repository root to
  `Investigation-Knowledge-Graph-main/databricks_app`.
- Deploy once and compare launch time with the previous root-source deployment.
- Confirm the active-analysis header, Class, Sources and Status hierarchy in the
  live App.
- Keep the root deployment fallback until the lean source is confirmed stable.
