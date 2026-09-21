# Safety Investigation Knowledge & AI Support

Proof of Concept for artificial-intelligence-assisted safety investigation analysis, evidence-grounded knowledge structuring and investigator review.

## Product identity

**Working product name:** Safety Investigation Knowledge & AI Support

The product is not defined by a knowledge graph alone. The knowledge graph is
one analytical representation used inside a broader safety-investigation
support environment.

The PoC evaluates how AI and structured-knowledge tools can support
investigators while preserving evidence provenance, confidentiality,
human-review authority and clear separation between source evidence and
machine-generated analysis.

## Purpose

This repository contains a standalone Proof of Concept (PoC) for representing investigation knowledge as an evidence-grounded graph.

The current PoC is the **generic Class D dual-model investigation-analysis workflow**. The Commodore Clipper 2010 case is retained as a controlled reference/benchmark, not as the scope of the product. The longer-term objective is broader: analyse one document, multiple documents, or an entire investigation evidence set, including heterogeneous sources such as:

- accident investigation reports;
- interview transcripts;
- witness statements;
- VDR or communications transcripts;
- technical inspection notes;
- procedures and manuals;
- correspondence and emails;
- recommendations and actions taken;
- other documentary evidence.

The system is designed so that graph relationships remain traceable to source evidence and analytical mappings can be reviewed rather than silently accepted.

## Current PoC

**Start here for the current PoC:** `docs/19_current_poc_functional_specification.md`.

It is the authoritative functional description. Commodore Clipper material is
reference/benchmark documentation only.


The current PoC demonstrates:

- documents or encrypted direct text as source input;
- an investigator-defined question/objective;
- information classification A/B/C/D;
- Class D selection of GPT-OSS 20B, Llama 3.3 70B Instruct, or both through Databricks Unity Gateway;
- one evidence extraction followed by independent model runs;
- side-by-side model outputs when both are selected;
- evidence-grounded graph generation;
- privacy validation before graph publication;
- de-identified analytical output by default;
- a 5-question/day Llama 3.3 70B usage limit per user;
- admin-controlled quota reset;
- Neo4j graph projection and Databricks App exploration;
- human-review provenance.

The **Commodore Clipper 2010** graph remains a controlled reference case for
methodology and future model benchmarking.

## Long-term target

The future target is an investigation knowledge environment in which:

```text
heterogeneous source material
        ↓
evidence units / passages / utterances
        ↓
LLM-assisted analytical extraction
        ↓
candidate entities / events / factors / claims / findings
        ↓
candidate relationships
        ↓
evidence grounding and validation
        ↓
human review where required
        ↓
case graph + cross-case graph
        ↓
query / comparison / pattern discovery
```

The future unit of analysis is therefore not "one PDF". It is an **investigation evidence corpus** that may contain many source types.

## Relationship to MAIRA

This project is independent from MAIRA.

A later generic-ingestion stage may reuse MAIRA's existing capabilities for:

- report acquisition;
- PDF extraction;
- page and passage generation;
- document provenance;
- retrieval.

This avoids rebuilding mature document-processing components. The Investigation Knowledge Graph layer remains conceptually separate and adds evidence-grounded entities, relationships, graph structure, analytical mappings and review.

The current Commodore Clipper PoC reuses existing Delta tables that were created during the workshop under the `bdw_analysis_prod.maira` schema. This is an implementation convenience, not project ownership. A dedicated schema is recommended for future development.

## Documentation

Start with `docs/README.md`. It separates the current generic/Class D PoC
documentation from the older Commodore Clipper reference-case material.

The two most important current documents are:

- `docs/17_class_d_dual_model_poc.md`
- `docs/18_model_validation_and_feedback.md`

## Repository structure

```text
app/
    app.py
    app.yaml
    requirements.txt

docs/
    00_project_charter.md
    01_current_poc_scope.md
    02_methodology.md
    03_architecture.md
    04_data_model.md
    05_review_and_governance.md
    06_source_types.md
    07_future_corpus_analysis.md
    08_roadmap.md
    09_commodore_clipper_case.md
    10_manual_relationship_review.md
    11_manual_emcip_mapping_review.md
    12_group_analysis_architecture.md
    13_automated_analysis_orchestration.md
    14_tooling_inventory.md
    15_data_protection_confidentiality.md
    16_unified_input_and_model_routing.md
    17_class_d_dual_model_poc.md
    18_model_validation_and_feedback.md
    19_current_poc_functional_specification.md
    20_class_d_neo4j_assurance.md
    21_class_d_model_services_and_first_benchmark.md

notebooks/
    01_neo4j_connection_test.py
    02_publish_commodore_clipper_graph.py
    03_enrich_node_labels.py
    04_enrich_edge_evidence.py
    05_validate_neo4j_projection.py
    06_configure_databricks_app_resources.py

sql/
    01_future_human_review_tables.sql
```

## Core principle

> Evidence first. Analysis is reviewable. Graph relationships are not accepted solely because they are plausible.

Chronology, causality, contribution and effect are distinct concepts and must not be conflated.

## Current technology

See `docs/14_tooling_inventory.md` for the authoritative tool-by-tool inventory,
including role, status and transition decisions.

Core stack:

- GitHub: authoritative source control / target single source of truth
- Databricks Apps + Streamlit: investigator-facing application
- Databricks Lakeflow Jobs: automated processing orchestration
- Unity Catalog + Delta Lake: governed source/evidence/provenance persistence
- Neo4j AuraDB: property-graph projection, traversal and review metadata
- streamlit-cytoscape: interactive graph visualisation
- Databricks model services: LLM-assisted analytical extraction and resolution

## Status

Current status: **Class D dual-model PoC implemented; GPT-OSS 20B and Llama 3.3 70B PoC model services are connected through Databricks Unity Gateway; 13 validation tests have been executed; and integration of the validated dual-model layer with MAIRA-derived evidence passages/provenance is the current implementation step.**

Immediate next steps:

1. extend the benchmark-results schema for reproducible real-case validation;
2. run the first locked investigation-passage benchmark through GPT-OSS 20B and Llama 3.3 70B independently;
3. configure the Class D dual-model Lakeflow Job and App resources;
4. generalise human review to model-run graphs;
5. execute the validation framework in `docs/18_model_validation_and_feedback.md`.


## Data protection and confidentiality

The project may process investigation material subject to legal,
organisational and personal-data protections.

The authoritative project policy is:

`docs/15_data_protection_confidentiality.md`

Key rule: technical capability is not equivalent to authorisation. Raw
confidential investigation evidence must not be introduced into a component
until the permitted processing path, access controls, data location, retention,
logging and vendor/processor implications have been confirmed.

For the current PoC, published/non-sensitive investigation material is the
preferred validation dataset.


## Privacy-by-design mission

A core mission of the Investigation Knowledge Graph is not merely to document
legal/confidentiality obligations, but to **actively reduce unnecessary
exposure of protected investigation and personal information throughout the
analysis lifecycle**.

The product follows these default principles:

- keep raw evidence in governed storage;
- expose only the minimum evidence needed to each processing step;
- prefer passage-level processing over whole-corpus disclosure;
- preserve original evidence separately from analytical output;
- de-identify analytical outputs by default;
- represent people by functional role rather than personal name where possible;
- omit emails, telephone numbers, addresses, personal IDs, dates of birth,
  medical details and other unnecessary identifying data from summaries,
  findings and graph labels;
- avoid re-identification through combinations of otherwise innocuous details;
- retain explicit provenance so an authorised investigator can trace an
  analytical statement back to the protected source without reproducing that
  source broadly;
- require explicit authorisation before a workflow deliberately retains a
  personal identity in an analytical output.

This is a product-design objective as well as a compliance safeguard.


## Information-class routing

All four classes remain supported:

- A — public/technical → Meta Llama 3.3 70B Instruct
- B — published/non-sensitive investigation material → Meta Llama 3.3 70B Instruct
- C — internal/restricted, non-Article-9 → GPT-OSS 120B
- D — protected/Article 9 → dedicated GPT-OSS 20B, Llama 3.3 70B, or both

**Class D is an additional protected-data route. It does not replace A/B/C.**
Only D adds dual-model comparison, the Llama daily quota and the stricter
protected-evidence handling rules.

See `docs/19_current_poc_functional_specification.md` for the authoritative
functional description and `docs/15_data_protection_confidentiality.md` for
the confidentiality control mapping.

## Unified analysis entry modes

The App supports two source-ingress methods:

- Documents — select 1–5 indexed source documents;
- Direct text — write/paste source text and construct a knowledge graph from it.

Both routes use the same evidence-grounded pipeline and privacy controls.

Model routing is determined by information class:

- A/B → `system.ai.meta-llama-3-3-70b-instruct`
- C → `system.ai.gpt-oss-120b`
- D → dedicated IKG GPT-OSS 20B and/or Llama 3.3 70B model services through Databricks Unity Gateway; fail closed if a requested model service is unavailable

See `docs/16_unified_input_and_model_routing.md`.

Lovable is not part of the IKG architecture.


## LLM disclosure and Article 9 suitability

The App must disclose every model route used by the PoC.

| Information class | Model | Serving route | Confidentiality position | Article 9 / Class D position |
|---|---|---|---|---|
| A | OpenAI GPT-5.6 Sol | Databricks `system.ai.meta-llama-3-3-70b-instruct` | Public / non-sensitive | Not approved for protected Class D evidence |
| B | OpenAI GPT-5.6 Sol | Databricks `system.ai.meta-llama-3-3-70b-instruct` | Published / non-sensitive | Not approved for protected Class D evidence |
| C | OpenAI GPT-OSS 120B | Databricks-hosted `system.ai.gpt-oss-120b` | Internal / restricted | Not automatically approved for Article 9 evidence |
| D | OpenAI GPT-OSS 20B | Dedicated Databricks endpoint | Protected / confidential | Conditionally suitable only after endpoint approval |
| D | Meta Llama 3.3 70B Instruct | Dedicated Databricks endpoint | Protected / confidential | Conditionally suitable only after endpoint approval |

The Article 9 column is an internal processing-governance classification, not a
legal certification.

For Class D, the system must fail closed until the selected endpoint's
networking, access control, logging, retention, data flow and organisational /
legal / security approval have been validated.

See:

- `docs/15_data_protection_confidentiality.md`
- `docs/19_current_poc_functional_specification.md`


## Retention and repository cleanliness

The PoC uses a minimised retention model:

- raw direct-text temporary payload → purge after successful extraction;
- raw Class D source ingress → maximum 24 hours;
- derived/digested analytical artefacts → 72 hours by default;
- validation/benchmark cases → retained only by explicit decision.

An hourly cleanup Job purges expired Delta/Neo4j analytical artefacts.

GitHub is code/documentation only. Investigation evidence, model outputs,
temporary exports and generated case artefacts are not repository content.
