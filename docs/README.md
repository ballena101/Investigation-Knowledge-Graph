# IKF documentation index

This directory documents the generic **Investigation Knowledge Framework / Safety Investigation Knowledge & AI Support PoC**.

The Commodore Clipper material is retained as a controlled reference and benchmark asset; it is not the product architecture.

## Read these first — current baseline

1. [28_app_information_architecture.md](28_app_information_architecture.md)  
   Current operational App separation: Analyse Documents, Findings & Evidence, Knowledge Graph, Ask / Compare LLMs, Review & Validate, with News & Alerts kept separate as an external-signal capability.

2. [25_implementation_status_and_roadmap.md](25_implementation_status_and_roadmap.md)  
   Current DONE / NEXT / PENDING operational implementation tracker.

3. [08_roadmap.md](08_roadmap.md)  
   Current capability objectives, baseline-consolidation milestone, validation maturity model and future phases.

4. [30_cost_efficient_validation_strategy.md](30_cost_efficient_validation_strategy.md)  
   Authoritative engineering rule for local/GitHub-first validation and minimal-cost Databricks integration proof.

5. [18_model_validation_and_feedback.md](18_model_validation_and_feedback.md)  
   Model validation, benchmark metrics and the controlled use of human-validated knowledge as evaluation/retrieval/feedback material.

6. [16_unified_input_and_model_routing.md](16_unified_input_and_model_routing.md)  
   Input modes, information classes, model routing and privacy controls.

7. [15_data_protection_confidentiality.md](15_data_protection_confidentiality.md)  
   Confidentiality, minimisation, Article-9-oriented design and privacy gate.

8. [13_automated_analysis_orchestration.md](13_automated_analysis_orchestration.md)  
   Lakeflow Job lifecycle and processing stages.

9. [03_architecture.md](03_architecture.md) and [04_data_model.md](04_data_model.md)  
   Technical architecture and graph/data model.

10. [22_maira_passage_integration.md](22_maira_passage_integration.md)  
    MAIRA passage contract, provenance preservation and removal of parallel document-chunking logic from IKF.

## Current source/knowledge ownership

- **MAIRA** — canonical published investigation documents, passages, provenance, governed terminology and governed retrieval.
- **IKF** — orchestration, analysis runs, questions, review, graph/knowledge presentation and validated-knowledge workflows.
- **REFERENCE_CONTEXT** — separate legal / IMO / technical reference corpus.
- **SHIELD** — separate persistent classification/taxonomy corpus.
- **EMCIP controlled vocabulary** — MAIRA-owned governed analytical vocabulary consumed by IKF.
- **News & Alerts** — external/unvalidated signals kept separate from validated investigation knowledge.

## Current operational App flow

```text
Governed source selection
        ↓
Analyse Documents
(question-independent extraction)
        ↓
structured candidate outputs + provenance
        ├──────────────→ Findings & Evidence
        │                 item-level evidence + cited source pages
        │
        ├──────────────→ Knowledge Graph
        │                 graph exploration + scoped graph questions
        │
        ├──────────────→ Ask / Compare LLMs
        │                 scoped questions + governed retrieval + citations
        │
        └──────────────→ Review & Validate
                          relationship review → EMCIP → SHIELD
```

Human review remains authoritative. AI output is candidate knowledge unless and until the relevant validation workflow records a human decision.

## Validation principle

The project does **not** use Databricks as the routine debugging environment.

The validation order is:

```text
local/static tests
        ↓
frozen benchmark replay
        ↓
mocked/contract integration tests
        ↓
release-candidate freeze
        ↓
minimal Databricks integration proof
```

A validator notebook does not imply a fresh analysis or fresh LLM execution. Persisted analyses, retrieval snapshots, model outputs and graph/review artefacts should be reused whenever the behaviour under test is downstream or deterministic.

See [30_cost_efficient_validation_strategy.md](30_cost_efficient_validation_strategy.md).

## Methodology and governance

- [02_methodology.md](02_methodology.md) — evidence-first graph methodology.
- [05_review_and_governance.md](05_review_and_governance.md) — review and governance.
- [06_source_types.md](06_source_types.md) — supported and target source types.
- [07_future_corpus_analysis.md](07_future_corpus_analysis.md) — future corpus analysis.
- [12_group_analysis_architecture.md](12_group_analysis_architecture.md) — multi-document group analysis.
- [14_tooling_inventory.md](14_tooling_inventory.md) — tool-by-tool inventory and transition decisions.

## Controlled reference case — not the main product

These files document the Commodore Clipper demonstrator and the review mechanics first developed against it:

- [09_commodore_clipper_case.md](09_commodore_clipper_case.md)
- [10_manual_relationship_review.md](10_manual_relationship_review.md)
- [11_manual_emcip_mapping_review.md](11_manual_emcip_mapping_review.md)

The reference case is retained because it provides reviewed graph/evidence material useful for regression tests and future benchmarks.

## Integration and governed classification

- [23_maira_bosuil_integration_plan.md](23_maira_bosuil_integration_plan.md) — MAIRA reuse, EMCIP/query/relationship governance, selective Bosuil-derived design experiments, Directive/IMO reference context, Class-D safeguards and SHIELD sequencing.
- [26_generic_emcip_mapping_review.md](26_generic_emcip_mapping_review.md) — MAIRA-registry shortlist, LLM proposal, human validation and provenance controls.
- [27_reference_context_retrieval.md](27_reference_context_retrieval.md) — separation of SOURCE_EVIDENCE, REFERENCE_CONTEXT and controlled-taxonomy roles.
- [29_shield_two_gate_workflow.md](29_shield_two_gate_workflow.md) — persistent SHIELD corpus, Gate-1 contributing-factor validation, grounded assistant proposal and Gate-2 human review.

## Runtime validation

- [26_consolidated_runtime_validation.md](26_consolidated_runtime_validation.md) — Databricks-oriented integration checklist.

This checklist should now be executed according to the cost-efficient strategy in document 30: reuse persisted artefacts, batch checks around one release candidate, and avoid separate cloud/model runs when local or read-only validation is sufficient.

## Documentation maintenance note

Earlier documents may preserve historical PoC design decisions that have since been superseded. The authoritative current baseline is the combination of:

- `08_roadmap.md`;
- `25_implementation_status_and_roadmap.md`;
- `28_app_information_architecture.md`;
- `30_cost_efficient_validation_strategy.md`.

Future documentation updates should prefer revising these current baseline documents over creating additional overlapping architecture descriptions.
