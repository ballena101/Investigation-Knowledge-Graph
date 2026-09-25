# Safety Investigation AI Sandbox — user App merge

## Purpose

This update integrates the user-maintained `app.py` / `app.yaml` changes supplied on 25 September 2026 without replacing the canonical deterministic App build architecture.

The deployed App name is now **Safety Investigation AI Sandbox**.

## Integrated user changes

The supplied App introduced a live News & Alerts view backed by the Databricks SQL Statement Execution API. The integration preserves:

- `SQL_WAREHOUSE_ID=372b5b52ba082619` in the App configuration;
- the existing published News dashboard URL as a fallback;
- read-only querying of `bdw_analysis_prod.siana.eu_eea_alerts_hierarchy_v`;
- MARINFO enrichment from `bdw_marinfo_prod.marinfo5.lot2a_ship`;
- the seven-day alert window and the supplied exclusion logic;
- the live alert KPIs, map, detail table, vessel/country/event charts and daily alert count;
- the explicit rule that news remains external, unvalidated information and is not silently mixed with validated investigation findings.

The user-supplied generated `app.py` was not copied wholesale into canonical `app/app.py`. Instead, its functional changes are captured in `src/ikf/app_news_adoption.py` and materialised deterministically with the rest of the App. This avoids double-applying existing audio, Parakeet, timeline, workflow and simplification transformations.

Branding is applied last by `src/ikf/app_branding_adoption.py` so later source transformations cannot restore a legacy title.

## Accidental `=0.34` artefact

No tracked file or notebook named `=0.34` (or containing that path fragment) exists in the GitHub repository. The name is consistent with the earlier shell-redirection error caused by an unquoted pip requirement such as `huggingface-hub>=0.34,<2`.

The actual notebook commands are already quoted. `.gitignore` now also excludes `=0.34*` so such a local/workspace artefact is not accidentally committed. If an untracked `=0.34` item remains visible in the Databricks workspace, it can be removed there after confirming it is the shell artefact; no legitimate GitHub notebook is being deleted by this update.

## Bundle contract

The materialised bundle contract advances to `IKF_DATABRICKS_APP_BUNDLE_V0.10` and records both:

- `IKF_APP_NEWS_ADOPTION_V0.1`
- `IKF_APP_BRANDING_ADOPTION_V0.1`

## Cost and governance

The News query is read-only and cached in Streamlit for 300 seconds. It uses the configured Databricks SQL warehouse and therefore can incur SQL warehouse consumption when the News tab is loaded/refreshed. It does not call an LLM.

Existing evidence classification, Article 9 handling, Class-D model routing, transcription validation and human-governance controls remain unchanged.

## Status

Done:

- merge supplied App configuration and News functionality;
- rename App to Safety Investigation AI Sandbox;
- preserve deterministic materialisation;
- protect against accidental `=0.34` commits;
- add regression assertions for the merged behaviour.

Pending runtime validation:

- pull the refreshed generated bundle in Databricks;
- redeploy the existing App;
- verify the App service principal can use SQL warehouse `372b5b52ba082619` and SELECT the two News source tables/views;
- verify live News rendering and existing transcription/analysis flows in the deployed App.
