# Investigator workflow simplification — 24 September 2026

## Decision

The investigator-facing App is simplified around evidence analysis, free-text LLM questions, human relationship validation, SHIELD classification and a reviewed Knowledge Graph. EMCIP mapping is removed from the operational App workflow.

`IKF` remains the internal project/code identifier for continuity, where it means **Investigation Knowledge Framework**. The operational product surface is deliberately name-neutral and uses **Safety Investigation Knowledge & AI Support**. No broad technical rename is justified until a final product name is selected, because changing resource keys, jobs, environment variables, paths and historical documentation would add migration risk without improving investigator use.

## Analysis description

`analysis_description` is not merely display metadata. Notebook 16 supplies it to the LLM during both candidate extraction and cross-document resolution. It therefore provides contextual orientation for the analysis.

It is **not evidence**. The extraction and resolution prompts remain evidence-grounded: occurrence facts and relationships must be supported by supplied passages/candidates, and the description must not be treated as a source for new facts. The App wording now explains this distinction.

## Findings & Evidence

The page starts with a short analysis overview from the persisted analysis result before the detailed content index and evidence sheet. This applies regardless of whether the analysed source originated as investigation documents, reviewed audio transcription or governed direct text.

## Review & Validate evidence

The relationship-review evidence area no longer presents the same provenance three times.

The operational view is now:

1. select the relationship;
2. select an **Evidence passage** from one dropdown;
3. select the **Evidence page** / source reference when available;
4. inspect the embedded source excerpt;
5. record the human decision.

The previous separate `Supporting evidence` list, `Technical evidence IDs` expander and `Evidence anchor` display are removed. Passage IDs remain governed provenance but are presented through the single passage selector rather than as a separate evidence type. Model-run provenance remains available in the collapsed technical-provenance section.

This is a presentation change only. It does not alter stored evidence, relationship review semantics, append-only review records or source authority.

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

The persisted original AI graph is retained for provenance. At display time the application applies the latest `RelationshipReview` records to create the reviewed projection:

- `VALIDATED` — relationship remains visible;
- `AMENDED` — relationship remains visible using the investigator-amended relationship type;
- `REJECTED` — relationship is hidden from the displayed graph;
- no human review yet — relationship remains visible as an AI candidate so that work-in-progress is not silently discarded.

This projection requires only Neo4j reads; it does not rerun the analysis model.

At this stage the review projection operates on relationships. Nodes are not automatically deleted merely because one of their relationships is rejected, because the same node may still be supported by other evidence or relationships. Orphan-node pruning can be added later if investigator testing shows it is useful.

## Audio transcription and confidentiality disclosure

The current App transcription route uses `faster-whisper==1.2.1` and offers Whisper `large-v3-turbo` or `large-v3`. The UI now states this explicitly beside the transcription workflow and in the confidentiality notice.

The operational disclosure also states that:

- audio/transcripts are Class D protected material;
- the original recording remains authoritative;
- machine transcripts remain unverified until a person listens, corrects and accepts them;
- accepted transcripts enter the normal Class D document-analysis workflow;
- AI findings and relationships remain proposals until human validation.

The confidentiality notice uses Article 9-aligned wording and does not claim legal certification of compliance.

Third-party software, model weights, repositories and services remain subject to their own licences, terms, security commitments and availability. The notice explains that the application developer cannot control or guarantee those independent services or outputs, while retaining responsibility for the configuration, integration and controls implemented in this application. This avoids an over-broad liability disclaimer.

## Product naming

`IKF` originally meant **Investigation Knowledge Framework**. That name reflected the earlier knowledge-graph/framework focus. The current application is broader: it covers source preparation, document/audio analysis, evidence review, LLM Q&A, timeline reconstruction, knowledge graph review and SHIELD classification.

Decision for now:

- retain `IKF` internally as the project/code namespace to avoid unnecessary migration churn;
- do not make `IKF` part of the main investigator-facing product identity;
- keep the current neutral title **Safety Investigation Knowledge & AI Support** while a final product name is considered;
- use name-neutral operational wording so a later rename can be made without another UI/governance rewrite.

## EMCIP

Removed from the operational App:

- EMCIP mapping UI;
- EMCIP mapping App resource binding;
- EMCIP mapping Job requirement in the consolidated release preflight;
- EMCIP operational registry requirement in the release preflight.

Historical EMCIP notebooks/governance code are not destructively deleted in this change. They remain repository history/reference material and can be removed separately after the simplified App is runtime-validated.

## Deployment contract

The generated `databricks_app/` bundle uses `IKF_DATABRICKS_APP_BUNDLE_V0.8`, UI adoption `IKF_APP_UI_ADOPTION_V0.3` and simplification adoption `IKF_APP_SIMPLIFICATION_ADOPTION_V0.4`.

The current materialized workflow includes:

- corrected Analysis description explanation;
- Ask LLM history before new question;
- brief Findings & Evidence summary;
- EMCIP UI removal;
- SHIELD factor-to-taxonomy mapping view;
- reviewed Knowledge Graph projection;
- graph question removal;
- single Evidence passage selector in relationship review;
- compact Article 9 / confidentiality / external-tools disclosure;
- explicit `faster-whisper 1.2.1` disclosure;
- supporting legacy wording cleanup.

## Validation, cost and performance

Static GitHub materialization/compilation and local regression validation do not use Databricks compute or invoke an LLM.

The evidence/disclosure cleanup removes duplicate widgets and unnecessary presentation work, but it is not expected to produce a large runtime speed-up.

The highest-value remaining App performance improvement is **lazy capability rendering**. The current top-level Streamlit tab structure can still execute hidden-tab code during reruns. This should be addressed separately after the current UI is runtime-validated, rather than mixed into the low-risk evidence/governance cleanup.

## Status

### Done

- Simplified workflow source transformation added.
- Lean Databricks App bundle materialized.
- EMCIP App/preflight dependency removed.
- SHIELD factor mapping view implemented.
- Reviewed graph projection implemented.
- Graph-scoped questions removed.
- Findings summary and Ask-history ordering implemented.
- Review & Validate evidence reduced to one passage selector plus source/page selector.
- Article 9, Class D audio, Whisper version and external-tool disclosure consolidated.
- User-facing wording made substantially independent of the internal `IKF` project name.
- Local regression, bundle build and undefined-name validation green.

### Pending

- Pull `main` into the Databricks workspace.
- Deploy the existing `databricks_app/` source once.
- Visually confirm Review & Validate passage/page selection using a persisted analysis.
- Visually confirm the audio disclosure/model selector without triggering a new transcription.
- Confirm a known rejected/amended relationship renders correctly in the reviewed graph.
- After runtime validation, implement lazy capability rendering as a separate performance change.
- Select a final product name before considering any internal namespace/resource migration.
- Only after runtime validation, decide whether dormant historical EMCIP/legacy transcription implementation files should be deleted from the repository.
