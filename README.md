# Safety Investigation Knowledge & AI Support

Proof of Concept for AI-assisted safety-investigation analysis, evidence-grounded knowledge structuring and investigator review.

## Product identity

**Working product name:** Safety Investigation Knowledge & AI Support / IKF.

The product is not defined by a knowledge graph alone. The graph is one analytical representation inside a wider investigation-support environment.

IKF evaluates how AI and structured-knowledge tools can support investigators while preserving:

- evidence provenance;
- confidentiality and data minimisation;
- clear separation between source evidence and machine-generated analysis;
- human-review authority;
- reviewable and reproducible analytical outputs.

## Purpose

IKF is the investigator-facing **orchestration, analysis, review and validated-knowledge layer**.

Its long-term objective is to support one document, multiple documents or an entire investigation evidence corpus, including material such as:

- accident investigation reports;
- interview transcripts;
- witness statements;
- VDR or communications transcripts;
- technical inspection notes;
- procedures and manuals;
- correspondence and emails;
- recommendations and actions taken;
- other documentary evidence.

The intended knowledge flow is:

```text
source material
        ↓
evidence units / passages / utterances
        ↓
AI-assisted analytical extraction
        ↓
candidate entities / events / factors / findings
        ↓
candidate relationships
        ↓
evidence grounding
        ↓
human review where required
        ↓
validated case knowledge
        ↓
cross-case retrieval / comparison / pattern discovery
```

## Core principle

> **Evidence first. Analysis is reviewable. Graph relationships are not accepted solely because they are plausible.**

Chronology, causality, contribution and effect are distinct concepts and must not be conflated.

## Relationship to MAIRA

IKF and MAIRA have distinct roles.

**MAIRA** is the canonical investigation-evidence layer for published investigation material, including:

- source documents;
- canonical passages;
- page/provenance metadata;
- governed terminology;
- governed retrieval.

**IKF** consumes those capabilities and adds:

- investigator-facing orchestration;
- structured analytical extraction;
- QuestionRun / Ask workflows;
- evidence-grounded graph and findings views;
- human relationship review;
- EMCIP mapping review;
- SHIELD two-gate classification;
- cross-case and similar-case use of validated knowledge.

IKF must not build parallel substitutes for canonical MAIRA document/passages/terminology functionality.

## Current App capabilities

The current operational application is organised by user intent:

1. **Analyse Documents** — question-independent structured analysis and processing status.
2. **Findings & Evidence** — item-level analytical content, supporting evidence and cited source pages.
3. **Knowledge Graph** — graph exploration and evidence-scoped graph questions.
4. **Ask / Compare LLMs** — scoped questions over processed case evidence or governed reference documents.
5. **Review & Validate** — human relationship, EMCIP and SHIELD governance.
6. **News & Alerts** — external/unvalidated signals kept separate from validated investigation knowledge.

Machine-generated outputs remain candidate knowledge unless the relevant human-review workflow records a validating decision.

## Source ownership and controlled knowledge

- Class B published investigation material → **MAIRA**.
- Class A public/technical material → governed **IKF** source route.
- Class C internal/restricted material → governed **IKF** source route.
- Class D protected/confidential material → governed **IKF** protected route.
- Legal / IMO / technical references → separate **REFERENCE_CONTEXT** corpus.
- SHIELD taxonomy → separate persistent **SHIELD** corpus.
- EMCIP controlled vocabulary → MAIRA-governed vocabulary consumed by IKF.

## Human-governance sequence

A core design rule is:

```text
AI candidate
   ↓
evidence-grounded review
   ↓
human decision
   ↓
validated knowledge
   ↓
controlled downstream classification/use
```

For SHIELD specifically:

1. Gate 1 — the contributing factor must first be human validated;
2. Gate 2 — the LLM may propose a SHIELD mapping, but the SHIELD mapping itself requires a separate human decision.

## Cost-efficient validation strategy

Databricks is a cloud execution environment with direct cost. IKF therefore does **not** use Databricks as the routine development/debugging environment.

The default validation hierarchy is:

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

A validator notebook does not imply a fresh analysis or a fresh LLM call.

Persisted analyses, QuestionRuns, retrieval snapshots, model outputs, graphs and review artefacts should be reused whenever the behaviour being tested is downstream or deterministic.

Databricks is reserved for checks that genuinely require the deployed environment, for example:

- Unity Catalog permissions;
- Files API access with user authorisation;
- Lakeflow Job/resource wiring;
- deployed model endpoint connectivity;
- cloud Neo4j connectivity;
- deployed Streamlit compatibility;
- real governed source-page rendering;
- representative end-to-end integration proof.

See `docs/30_cost_efficient_validation_strategy.md`.

## Current milestone

The project is now in **IKF baseline consolidation** rather than broad feature expansion.

Priority order:

1. consolidate current architecture/documentation;
2. move stable business logic progressively out of the large Streamlit file and Databricks-only notebooks into reusable `src/ikf/` modules;
3. expand automated regression tests;
4. replay frozen benchmark/model artefacts for downstream validation;
5. freeze a release candidate;
6. perform one economical Databricks integration session using shared persisted artefacts;
7. record capability maturity and address failures locally wherever possible;
8. resume major capability expansion only after the baseline is stable.

## Validation maturity states

Important capabilities should use the same maturity terminology:

1. **Designed**
2. **Code complete**
3. **Local validated**
4. **Runtime validated**
5. **Benchmark validated** — where model behaviour is relevant
6. **Production ready**

This avoids treating `code complete` as equivalent to deployed proof while also avoiding unnecessary Databricks execution for deterministic logic.

## Benchmark and model-quality objectives

IKF is moving from proving that a pipeline runs to measuring whether model behaviour is acceptable.

Important evaluation dimensions include:

- semantic precision and recall;
- evidence grounding;
- extraction / graph completeness and coverage;
- unsupported inference;
- causal overreach;
- human amendment/rejection/acceptance rate;
- model stability/repeatability;
- privacy leakage;
- citation/provenance correctness.

The Commodore Clipper reference case and the controlled MAIRA/IKF benchmark assets remain useful for regression and methodology testing, but they are not the product scope.

## Repository structure

```text
app/       Databricks/Streamlit investigator-facing application
config/    governed configuration and reference-source definitions
docs/      architecture, governance, validation and roadmap documentation
notebooks/ Databricks setup, jobs, processing and integration validators
sql/       persistence/review schema assets
src/ikf/   reusable IKF Python logic
tests/     local automated regression tests
```

The repository intentionally does **not** store investigation evidence, model-output dumps or temporary case artefacts.

## Documentation

Start with `docs/README.md`.

The authoritative current baseline is the combination of:

- `docs/08_roadmap.md`
- `docs/25_implementation_status_and_roadmap.md`
- `docs/28_app_information_architecture.md`
- `docs/30_cost_efficient_validation_strategy.md`

Key supporting documents include:

- `docs/15_data_protection_confidentiality.md`
- `docs/18_model_validation_and_feedback.md`
- `docs/22_maira_passage_integration.md`
- `docs/23_maira_bosuil_integration_plan.md`
- `docs/27_reference_context_retrieval.md`
- `docs/29_shield_two_gate_workflow.md`

Earlier documents may retain historical PoC decisions and reference-case material. They should not override the current baseline documents above.

## Current technology

Core stack:

- GitHub — authoritative code/documentation source of truth;
- Databricks Apps + Streamlit — investigator-facing deployed application;
- Databricks Lakeflow Jobs — cloud orchestration where required;
- Unity Catalog + Delta Lake — governed evidence/provenance persistence;
- Neo4j AuraDB — graph projection, traversal and review metadata;
- streamlit-cytoscape — interactive graph visualisation;
- Databricks model services — governed LLM execution routes.

## Privacy-by-design mission

The project actively aims to reduce unnecessary exposure of protected investigation and personal information.

Default principles include:

- keep raw evidence in governed storage;
- expose only the minimum evidence needed to each processing step;
- prefer passage-level processing over whole-corpus disclosure;
- preserve original evidence separately from analytical output;
- de-identify analytical output by default;
- retain explicit provenance without unnecessarily reproducing protected source material;
- require explicit authorisation before deliberately retaining personal identity in analytical output.

Technical capability is not equivalent to processing authorisation.

## Retention and repository cleanliness

The PoC follows a minimised-retention approach for transient analytical material. The authoritative confidentiality and retention requirements are documented in `docs/15_data_protection_confidentiality.md`.

GitHub remains code/documentation only. Investigation evidence, generated case artefacts, temporary exports and raw model-output dumps are not repository content.
