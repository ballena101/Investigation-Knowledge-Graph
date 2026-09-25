# Purpose-fit App visual refinement

_Last updated: 2026-09-26_

## Purpose

This change narrows the Databricks App to the investigator-facing workflow that is useful now, while preserving broader IKF project capabilities in the repository for later reuse.

The governing rule is:

**remove unnecessary complexity from the deployed App without deleting project capabilities or governance assets.**

The changes in this document are presentation/workflow changes. They do not alter the evidence/provenance model, Knowledge Graph semantics, human-review authority, MAIRA source ownership or SHIELD project assets.

## 1. Timeline: table-first view replaced by a visual event sequence

The Timeline remains a deterministic projection of the same evidence-derived `Event` nodes and `FOLLOWED_BY` relationships used by the Knowledge Graph.

The primary Timeline presentation is now a Plotly event-sequence visualization instead of a dataframe.

The horizontal axis represents **event sequence**. This is intentional: where the evidence does not support a clock time, the App still shows the event in chronology order without inventing temporal precision.

Each plotted event exposes, on hover:

- event label;
- supported time where available;
- ordering basis;
- evidence-reference count;
- human-review state.

The previous tabular chronology is retained only under a collapsed **View timeline data** expander for auditability and detailed inspection.

No additional LLM call is introduced by the visualization.

## 2. Plotly dependency

Plotly is now an explicit App dependency for the timeline visualization:

```text
plotly>=6,<7
```

It is added to `app/requirements.txt` and therefore propagated into the generated Databricks App bundle.

The App imports:

```python
import plotly.graph_objects as go
```

Plotly is used only as a presentation layer. Timeline data continues to come from governed IKF timeline/KG records.

## 3. Timeline categories simplified to five

The displayed timeline taxonomy is reduced to five broad investigator-facing categories:

1. **Context / operation**
2. **Failure / hazard**
3. **Action / communication**
4. **Accident / consequence**
5. **Response / recovery**

The purpose is readability rather than replacing the underlying Knowledge Graph taxonomy.

Existing older event types are mapped deterministically into these five display categories. For default projected events without a human-reviewed category, a lightweight keyword-based display mapping is used. This mapping does not create a new evidence fact and does not call an LLM.

## 4. Timeline phases simplified to five

The investigator review control is also simplified to five phases:

1. **Before occurrence**
2. **Occurrence**
3. **Escalation**
4. **Response / recovery**
5. **After occurrence**

This is a UI simplification. Existing stored timeline records remain compatible with the underlying timeline model.

## 5. News & Alerts simplified

The News & Alerts page remains an external/unvalidated intelligence capability and is still kept separate from investigation evidence.

The following two summary charts are removed from the App:

- **Alerts by country**
- **Daily alert count**

The following useful elements remain:

- filters;
- summary KPIs;
- alert map;
- alert-detail table;
- **Alerts by vessel type**;
- **Alerts by event type**;
- deterministic active-analysis relevance screening where available.

This change reduces duplicated summary information and keeps the page focused on alert triage.

## 6. SHIELD removed from the App only

The **SHIELD classification of contributing factors** section is removed from the deployed Streamlit App.

This does **not** remove SHIELD from IKF.

The following remain in the project:

- SHIELD taxonomy/reference documents;
- SHIELD governance module;
- SHIELD notebooks/jobs;
- persisted SHIELD data and proposals where they exist;
- two-gate human-validation design;
- project documentation, including `29_shield_two_gate_workflow.md`;
- bundle inclusion of `shield_governance.py`.

The decision is therefore a product-scope choice, not a deletion of functionality.

SHIELD can be exposed again in a different or later App without reconstructing the project capability.

## 7. Purpose-fit UI refinement layer

The changes are implemented in:

`src/ikf/app_visual_refinement.py`

Current version:

`IKF_APP_VISUAL_REFINEMENT_V0.3`

The bundle builder records this refinement in its materialisation marker and manifest under `visual_refinement_version` / `applied_visual_refinements`.

This approach keeps the current App focused while preserving underlying project modules.

## 8. Databricks bundle contract update

The bundle builder was extended to apply the visual refinement after the existing policy, workflow, operational and similarity layers.

The bundle contract was incremented to:

`IKF_DATABRICKS_APP_BUNDLE_V0.13`

The generated bundle must include:

- `app_visual_refinement.py`;
- Plotly in the App requirements;
- the visual-refinement version in the manifest/marker.

## 9. Build compatibility correction found during this update

During materialisation validation, the builder exposed a pre-existing compatibility issue in the operational refinement layer.

The monolithic App source already carried the current Class-D quota constants:

- GPT-OSS 20B: 30 questions/day;
- Llama 3.3 70B: 10 questions/day.

The older operational refinement still expected the legacy Llama-only `5` constant as its transformation anchor. That caused materialisation to stop before the new visual refinement was reached.

The bundle builder now normalises only those pre-applied constants back to the legacy anchor immediately before the operational transform. The operational transform then reapplies the current constants together with its wider quota/UI migration.

This is a build-compatibility correction; it does not change the intended quotas.

## 10. Files changed for this refinement

The implementation from this chat changes:

- `src/ikf/app_visual_refinement.py` — purpose-fit UI transformation;
- `scripts/build_databricks_app_bundle.py` — visual-refinement integration, manifest/bundle update and quota-anchor compatibility normalisation;
- `app/requirements.txt` — Plotly dependency;
- generated `databricks_app/**` — refreshed automatically after successful materialisation;
- documentation — this record plus current documentation/index updates.

## 11. Validation expectations

Before treating this App revision as runtime validated, confirm:

1. materialised bundle builds and compiles successfully in GitHub Actions;
2. generated `databricks_app/app.py` contains the Plotly timeline;
3. Timeline renders as a visual event sequence for an existing completed analysis;
4. **View timeline data** remains available and collapsed by default;
5. only the five simplified timeline categories are exposed in the review UI;
6. News & Alerts no longer shows **Alerts by country** or **Daily alert count**;
7. vessel-type and event-type charts remain available;
8. no SHIELD classification section is visible in the App;
9. SHIELD code/governance/project assets remain present in the repository;
10. no additional LLM execution is triggered by opening the Timeline.

## 12. Product direction

This refinement formalises the current product direction: build **one App fit for the investigator purpose**, rather than exposing every PoC capability simply because it exists in the project.

Project capabilities may remain broader than the operational App. The App should expose only what improves the investigator workflow, while the repository preserves reusable research, governance and future-product components.
