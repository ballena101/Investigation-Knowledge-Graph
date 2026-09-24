# Governed Databricks App deployment

## Purpose

The investigator-facing Databricks App must be deployed together with the canonical `src/ikf` shared policy package. Deploying only the historical `app/` directory is not supported because the raw Streamlit source depends on deterministic governed transformations supplied by `src/ikf/app_adoption.py`.

This is especially important for Class D / Article 9 handling: governed source transformation and routing controls must not be bypassed by an incomplete deployment artifact.

## Preferred deployment: Git repository root

The repository root is directly deployable by Databricks Apps.

The root now contains:

- `app.yaml`, whose command is `streamlit run app/bootstrap.py`;
- `requirements.txt`, which includes `app/requirements.txt`;
- `app/`, containing the investigator-facing Streamlit application;
- `src/ikf/`, containing the canonical shared policy package.

When Databricks deploys from Git, configure the Git reference to `main` and leave **Source code path empty** so the repository root becomes the App top-level directory.

Do **not** set Source code path to `app`. Databricks treats a selected Git subdirectory as the App top-level directory and the App cannot access files outside that directory. In that configuration, `src/ikf` is intentionally invisible to `app/bootstrap.py`.

## Alternative deployment: materialized workspace bundle

A deterministic deployable bundle can still be produced when a workspace-folder deployment is preferred:

```bash
python scripts/build_databricks_app_bundle.py --output build/databricks_app
```

The generated bundle contains the materialized App plus `src/ikf` and can be synced to a Databricks workspace folder before deployment.

## Local validation before deployment

```bash
python -m pytest -q
python scripts/build_databricks_app_bundle.py --output build/databricks_app
python -m ruff check --select F821 build/databricks_app/app.py src/ikf
```

The `F821` check detects undefined Python names in the materialized App before cloud deployment.

## Fail-closed behaviour

`app/bootstrap.py` deliberately raises an error if it cannot locate `src/ikf`. It must not execute the raw App in that state. This converts an incomplete deployment from a fail-open condition into a fail-closed condition.

An incomplete deployment previously exposed this issue through the Class-D Llama route: raw `app.py` referenced the legacy `CLASS_D_OLLAMA_LLAMA70_URL` Python name, while the governed transformation provides the compatibility alias and current `CLASS_D_LLAMA70_ENDPOINT` route. The underlying model endpoint configuration was not the root cause; the deployment source path was incomplete.

## Cost note

Changing the Databricks App deployment source, building the local bundle and running static validation do not invoke LLM model-serving endpoints or IKF analysis Jobs. The first runtime proof after redeployment should therefore be limited to opening the App and checking the Class-D model selector before any analysis is submitted.
