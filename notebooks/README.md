# Databricks Notebooks

Notebook `61_compare_whisper_type_d_audio.py` is an on-demand, single-GPU quality
pilot for the three Type D audio files. It compares `large-v3` and `turbo` and
writes restricted, unverified timestamped output; it does not replace the
existing notebook 38/39 `ai_transcribe()` persistence/binding path. See
`docs/40_whisper_quality_pilot.md` before running.

These files use Databricks source format so they remain readable in Git and can
be imported into Databricks.

## Reference-methodology notebooks

The Commodore Clipper notebooks remain as the controlled reference case:

1. `01_neo4j_connection_test.py`
2. `02_publish_commodore_clipper_graph.py`
3. `03_enrich_node_labels.py`
4. `04_enrich_edge_evidence.py`
5. `05_validate_neo4j_projection.py`
6. `06_configure_databricks_app_resources.py`
7. `07_configure_relationship_review.py`
8. `08_configure_emcip_mapping_review.py`

These notebooks validate the graph/evidence/review methodology. They are not the
current product scope.

## Generic source and analysis pipeline

- `12_add_multilingual_metadata.py`
- `13_register_analysis_from_volume_folder.py`
- `14_index_volume_documents_to_neo4j.py`
- `15_extract_analysis_evidence.py`
- `16_analyse_evidence_and_build_graph.py`
- `17_create_automated_analysis_job.py`

Notebook 15 supports governed documents and encrypted direct-text sources.

Notebook 16 is model-run aware: each model can publish an independent graph
namespace under one AnalysisGroup.

## Class D dual-model PoC

- `18_validate_class_d_gpt_oss_20b_endpoint.py` — earlier endpoint validation helper; retained for history.
- `19_create_class_d_dual_model_job.py` — creates the dedicated Lakeflow Job that extracts evidence once and runs GPT-OSS 20B and/or Llama 3.3 70B.
- `20_finalize_class_d_comparison.py` — completes the analysis only when all requested model runs are complete.
- `21_create_class_d_model_endpoints.py` — creates/validates dedicated custom serving endpoints from approved Unity Catalog model registrations.
- `22_model_run_validation_metrics.py` — computes human-review validation metrics once generic model-run reviews exist.
- `25_validate_maira_passage_bridge.py` — validates a read-only MAIRA passage bridge for one IKF analysis.
- `26_create_maira_bridge_test_analysis.py` — registers one idempotent Delta-only IKF test analysis from an existing MAIRA document when no matching analysis exists.
- `27_validate_maira_governed_retrieval.py` — applies a persisted MAIRA query specification to the bridged passages and exposes a deterministic read-only retrieval snapshot.\n- `28_compare_maira_snapshot_dual_model.py` — sends one verified frozen snapshot independently to GPT-OSS 20B and Llama 3.3 70B and exposes temporary run, candidate and exact-label comparison views.\n- `29_persist_maira_dual_model_benchmark.py` — persists the already-executed MAIRA dual-model run, candidate-level human review and governed MAIRA gold/reference relationships without rerunning either model; execute inline from notebook 28 so its session-local views are preserved.\n- `30_verify_maira_persisted_benchmark_metrics.py` — independently verifies one persisted MAIRA benchmark from Delta only and reports descriptive contract, grounding and query-adherence metrics.\n- `31_persist_maira_canonical_gold_matches.py` — persists human-reviewed candidate-to-canonical-gold matches and computes canonical relationship precision/recall without counting multiple supporting passage assessments as multiple relationships.

Normal investigators do **not** execute these notebooks. They use the App.

## Class D App workflow

```text
Documents OR encrypted direct text
        ↓
question/objective
        ↓
Class D
        ↓
GPT-OSS 20B | Llama 3.3 70B | Both
        ↓
evidence extraction once
        ↓
independent model runs
        ↓
privacy validation
        ↓
separate knowledge graphs
        ↓
side-by-side App comparison
        ↓
human review / validation
```

## Llama quota

The PoC limits Llama 3.3 70B to five questions per user per day. The App
persists the count in Neo4j and only configured administrators may reset it.

## Validation

The Commodore Clipper case is a reference/benchmark candidate.

Formal model validation is defined in:

`docs/18_model_validation_and_feedback.md`

Do not claim GPT-OSS 20B or Llama 3.3 70B is validated until the benchmark and
human-review metrics have actually been executed.


## Retention cleanup

- `23_purge_expired_analysis_artifacts.py` — removes expired derived/digested
  analytical artefacts after the default 72-hour retention period, excluding
  analyses explicitly retained for validation.
- `24_create_retention_cleanup_job.py` — one-time setup for the hourly
  Lakeflow retention-cleanup Job.

Raw Class D source ingress remains governed by the separate 24-hour maximum.


## Operational correction — 2026-09-21

Notebook `16_analyse_evidence_and_build_graph.py` previously initialised
`model_run_started = time.perf_counter()` before importing the `time` module.
This caused the automated Lakeflow workflow to fail immediately after successful
evidence extraction, leaving analyses at `EVIDENCE_READY`.

The import order was corrected so notebook 16 can start normally when invoked as
the second task of `Investigation KG - Automated Analysis`. Existing analyses
with persisted evidence passages can be resumed by repairing the failed
`analyse_and_build_graph` task; notebook 15 does not need to be rerun.
