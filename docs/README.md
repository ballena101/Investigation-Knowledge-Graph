# IKG documentation index

This directory documents the **generic Investigation Knowledge Graph PoC**.
The Commodore Clipper material is a reference/benchmark case only; it is not
the product architecture.

## Read these first — current PoC

1. [28_app_information_architecture.md](28_app_information_architecture.md)  
   Current operational App separation: Analyse Documents, Ask / Compare,
   Findings & Knowledge, Review & Validate, and the external News capability.

2. [18_model_validation_and_feedback.md](18_model_validation_and_feedback.md)  
   What has and has not been validated; benchmark metrics; how human-validated
   graph knowledge can be used for evaluation, retrieval, few-shot examples or
   future training without contaminating source evidence.

3. [16_unified_input_and_model_routing.md](16_unified_input_and_model_routing.md)  
   Input modes, information classes, model-routing and privacy controls.

4. [15_data_protection_confidentiality.md](15_data_protection_confidentiality.md)  
   Confidentiality, minimisation, Article 9-oriented design and privacy gate.

5. [13_automated_analysis_orchestration.md](13_automated_analysis_orchestration.md)  
   Lakeflow Job lifecycle and processing stages.

6. [03_architecture.md](03_architecture.md) and [04_data_model.md](04_data_model.md)  
   Technical architecture and graph/data model.

7. [22_maira_passage_integration.md](22_maira_passage_integration.md)  
   Read-only MAIRA passage contract, controlled test-analysis registration,
   parity gate and staged removal of duplicate document chunking from IKF.

8. [24_simple_capability_ui.md](24_simple_capability_ui.md)
   Simplified App navigation, Findings & Knowledge, optional graph views and
   the human-controlled LLM graph-correction workflow.

## Methodology and governance

- [02_methodology.md](02_methodology.md) — evidence-first graph methodology.
- [05_review_and_governance.md](05_review_and_governance.md) — review and governance.
- [06_source_types.md](06_source_types.md) — supported/target source types.
- [07_future_corpus_analysis.md](07_future_corpus_analysis.md) — future corpus analysis.
- [08_roadmap.md](08_roadmap.md) — roadmap.
- [12_group_analysis_architecture.md](12_group_analysis_architecture.md) — multi-document group analysis.
- [14_tooling_inventory.md](14_tooling_inventory.md) — authoritative tooling inventory.

## Controlled reference case — not the main product

These files document the Commodore Clipper demonstrator and the review mechanics
first developed against it:

- [09_commodore_clipper_case.md](09_commodore_clipper_case.md)
- [10_manual_relationship_review.md](10_manual_relationship_review.md)
- [11_manual_emcip_mapping_review.md](11_manual_emcip_mapping_review.md)

The reference case is retained because it provides reviewed graph/evidence
material useful for regression tests and future benchmarks.

## Current operational App flow

```text
Governed source selection
        ↓
Analyse Documents
(question-independent extraction)
        ↓
structured outputs + provenance
        ├──────────────→ Ask / Compare LLMs
        │                 scoped questions + citations
        │
        ├──────────────→ Findings & Knowledge
        │                 read-only evidence / graph / similar cases
        │
        └──────────────→ Review & Validate
                          human relationship / EMCIP / SHIELD decisions
```

Class D model routing remains a governed sub-capability of this wider flow;
it is no longer the organising principle of the whole App.


## Integrated architecture and roadmap

- `23_maira_bosuil_integration_plan.md` — authoritative integration plan for
  MAIRA reuse, EMCIP/query/relationship governance, selective Bosuil-derived
  design experiments, Directive/IMO reference context, human review, Class D
  safeguards and SHIELD sequencing.

- [25 — Implementation status and roadmap](25_implementation_status_and_roadmap.md) — current operational DONE / NEXT / PENDING tracker.

- [26 — Generic EMCIP mapping review](26_generic_emcip_mapping_review.md) — MAIRA-registry shortlist, LLM proposal, human validation and provenance controls.

- [27 — Reference-context retrieval](27_reference_context_retrieval.md) — separate SOURCE_EVIDENCE, REFERENCE_CONTEXT and controlled-taxonomy roles in Ask.

- [29 — SHIELD two-gate classification workflow](29_shield_two_gate_workflow.md) — persistent SHIELD corpus, Gate-1 contributing-factor validation, grounded assistant proposal and Gate-2 human review.

- [26 — Consolidated runtime validation](26_consolidated_runtime_validation.md) — one-shot Databricks preflight, deployment and feature-validation checklist.
