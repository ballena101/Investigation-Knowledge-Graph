# Governed Databricks App bundle deployment

## Purpose

The investigator-facing Databricks App must be deployed with the canonical `src/ikf` shared policy package. Deploying only the historical `app/` directory is not a supported production/PoC layout because the raw Streamlit source still depends on deterministic source transformations supplied by `src/ikf/app_adoption.py`.

This is especially important for Class D / Article 9 handling: governed source transformation and routing controls must not be bypassed by an incomplete deployment artifact.

## Supported layouts

The bootstrap supports two layouts:

1. Repository checkout: `app/` is beside `src/`. `app/bootstrap.py` imports `ikf.app_adoption` and applies the strict transformation in memory before executing the App.
2. Materialized Databricks App bundle: the deployable folder contains `app.py`, `bootstrap.py`, `app.yaml`, `requirements.txt`, the materialization marker, and `src/ikf`. The App source has already been transformed and locally validated.

The materialized bundle is the preferred deployment source.

## Build

From the repository root:

```bash
python scripts/build_databricks_app_bundle.py --output build/databricks_app
```

The build is deterministic and does not call an LLM, run an IKF analysis Job, or write investigation content.

## Local validation before deployment

```bash
python -m pytest -q
python -m ruff check --select F821 build/databricks_app/app.py src/ikf
```

The `F821` check is important because it detects undefined Python names in the materialized App before cloud deployment.

## Deploy

Deploy the contents of:

```text
build/databricks_app
```

Do **not** deploy the raw `app/` directory by itself.

The deployed folder must contain at minimum:

```text
app.py
bootstrap.py
app.yaml
requirements.txt
.ikf_shared_policy_materialized
src/ikf/
```

## Fail-closed behaviour

`app/bootstrap.py` deliberately raises an error if it cannot locate `src/ikf`. It must not execute the raw App in that state. This converts an incomplete deployment from a fail-open condition into a fail-closed condition.

A previous incomplete deployment exposed this issue through the Class-D Llama route: raw `app.py` referenced the legacy `CLASS_D_OLLAMA_LLAMA70_URL` Python name, while the governed transformation provides the compatibility alias and current `CLASS_D_LLAMA70_ENDPOINT` route. The underlying model endpoint configuration was not the root cause; the deployment artifact was incomplete.

## Cost note

Building and statically validating the bundle does not invoke model-serving endpoints or analysis Jobs. Cloud cost is therefore limited to any compute used to perform the commands and the normal Databricks App runtime after deployment.
