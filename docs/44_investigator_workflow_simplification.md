# Investigator workflow simplification — 24 September 2026

## Decision

The IKF investigator-facing App is simplified around evidence analysis, free-text LLM questions, human relationship validation, SHIELD classification and a reviewed Knowledge Graph. EMCIP mapping is removed from the operational App workflow.

## Analysis description

`analysis_description` is not merely display metadata. Notebook 16 supplies it to the LLM during both candidate extraction and cross-document resolution. It therefore provides contextual orientation for the analysis.

It is **not evidence**. The extraction and resolution prompts remain evidence-grounded: occurrence facts and relationships must be supported by supplied passages/candidates, and the description must not be treated as a source for new facts. The App wording now explains this distinction.

## Findings & Evidence

The page now starts with a short analysis overview from the persisted analysis result before the detailed content index and evidence sheet. This applies regardless of whether the analysed source originated as investigation documents, reviewed audio transcription or governed direct text.

## Ask LLMs

For case / analysed evidence, existing question runs and question history are shown before the new-question input. The question workflow remains separate from initial evidence analysis.

## SHIELD

SHIELD is presented as a classification beside contributing factors rather than as a separate taxonomy-review workflow.

The operational sequence is:

1. the LLM analysis identifies candidate contributing factors and relationships;
2. the investigator validates/amends/rejects the relevant relationship;
3. a contributing factor whose effective relationship is `CONTRIBUTED_TO` becomes eligible for SHIELD classification;
4. the LLM proposes a SHIELD label/code/path using only the indexed governed SHIELD corpus;
5. the App displays the contributing factor, what it contributes to, and the LLM SHIELD match when one is grounded.

SHIELD generation remains an explicit action so that model inference is not triggered silently and unnecessary Databricks/model cost is avoided.

## Knowledge Graph after validation

The Knowledge Graph is a display/exploration surface, not a Q&A surface. Graph-scoped questions are removed.

The persisted original AI graph is retained for provenance. At display time IKF applies the latest `RelationshipReview` records to create the reviewed projection:

- `VALIDATED` — relationship remains visible;
- `AMENDED` — relationship remains visible using the investigator-amended relationship type;
- `REJECTED` — relationship is hidden from the displayed graph;
- no human review yet — relationship remains visible as an AI candidate so that work-in-progress is not silently discarded.

This projection requires only Neo4j reads; it does not rerun the analysis model.

At this stage the review projection operates on relationships. Nodes are not automatically deleted merely because one of their relationships is rejected, because the same node may still be supported by other evidence or relationships. Orphan-node pruning can be added later if investigator testing shows it is useful.

## EMCIP

Removed from the operational App:

- EMCIP mapping UI;
- EMCIP mapping App resource binding;
- EMCIP mapping Job requirement in the consolidated release preflight;
- EMCIP operational registry requirement in the release preflight.

Historical EMCIP notebooks/governance code are not destructively deleted in this change. They remain repository history/reference material and can be removed separately after the simplified App is runtime-validated.

## Deployment contract

The generated `databricks_app/` bundle uses `IKF_DATABRICKS_APP_BUNDLE_V0.7` and `IKF_APP_WORKFLOW_ADOPTION_V0.1`.

The workflow adoption includes:

- corrected Analysis description explanation;
- Ask LLM history before new question;
- brief Findings & Evidence summary;
- EMCIP UI removal;
- SHIELD factor-to-taxonomy mapping view;
- reviewed Knowledge Graph projection;
- graph question removal;
- supporting wording cleanup.

## Validation and cost

Static GitHub materialization/compilation and local regression validation do not use Databricks compute or invoke an LLM. Runtime visual validation remains the next deployment check.

## Status

### Done

- Simplified workflow source transformation added.
- Lean Databricks App bundle materialized.
- EMCIP App/preflight dependency removed.
- SHIELD factor mapping view implemented.
- Reviewed graph projection implemented.
- Graph-scoped questions removed.
- Findings summary and Ask-history ordering implemented.
- Local regression green after contract updates.

### Pending

- Pull `main` into the Databricks workspace.
- Deploy the existing `databricks_app/` source once.
- Visually confirm the simplified pages using persisted analyses before triggering any new model inference.
- Confirm a known rejected/amended relationship renders correctly in the reviewed graph.
- Only after runtime validation, decide whether dormant historical EMCIP implementation files should be deleted from the repository.
