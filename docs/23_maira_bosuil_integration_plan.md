# MAIRA–IKF–Bosuil integration plan

Status: authoritative integration plan  
Date: 2026-09-21

## 1. Architecture decision

IKF must not duplicate the reusable evidence-processing capabilities that
already exist and have been validated in MAIRA.

The target separation of responsibilities is:

```text
SOURCE DOCUMENTS / DIRECT TEXT
        |
        +--> investigation documents already handled by MAIRA
        |       |
        |       v
        |   MAIRA canonical document + passage layer
        |       |
        |       +--> provenance / hashes / page bounds
        |       +--> governed EMCIP registry
        |       +--> governed query specifications
        |       +--> validated terminology normalisations
        |       +--> deterministic retrieval
        |       +--> deterministic relationship assessment
        |       +--> frozen retrieval snapshots / benchmark artefacts
        |
        +--> IKF-only direct text ingress
                |
                v
        encrypted transient ingress
                |
                v
        reusable deterministic passage component
        (to converge on MAIRA passage rules)

                     ↓

                IKF orchestration
                     |
                     +--> information-class routing A/B/C/D
                     +--> Class-D fail-closed controls
                     +--> identical evidence to compared models
                     +--> candidate concepts / relationships
                     +--> privacy validation
                     +--> human VALIDATE / AMEND / REJECT
                     +--> validated knowledge graph
                     +--> EMCIP mapping review
                     +--> SHIELD only after validated contributing factor
```

The repositories remain separate:

- **MAIRA** determines and preserves what the investigation sources say and
  provides governed retrieval/taxonomy primitives.
- **IKF** controls analysis orchestration, model exposure, model comparison,
  human review, graph promotion and application workflow.
- **Bosuil** remains an external design reference only. It is not a runtime
  dependency or parallel architecture.

## 2. MAIRA capabilities to reuse directly

### 2.1 Canonical investigation passages and provenance

Use MAIRA's canonical passage contract:

`MAIRA_IKF_PASSAGE_V0.1`

Authoritative source fields include:

- report_package_id;
- document_id;
- passage_id;
- passage_number;
- start_page / end_page;
- exact passage_text;
- passage_text_sha256;
- chunking_method / chunking_version.

IKF must preserve MAIRA passage identity and wording unchanged for documents
already processed by MAIRA.

Document matching between projects is by full source-document SHA-256, not by
filename and not by project-local document IDs.

Already validated:

```text
Controlled analysis: ikf_maira_test_001
Documents validated: 1
Passages validated: 6
PASS — MAIRA_IKF_PASSAGE_V0.1
```

### 2.2 Governed EMCIP taxonomy

MAIRA owns the authoritative operational EMCIP registry used for analytical
matching.

Relevant governed tables include:

- `bdw_analysis_prod.maira.emcip_attributes`;
- `bdw_analysis_prod.maira.emcip_codes`.

The registry preserves:

- taxonomy/version;
- source provenance;
- entity/attribute hierarchy;
- controlled values;
- CF coding hierarchy;
- code-list coverage status;
- review status.

Important boundary: missing controlled values must remain explicitly missing;
IKF must not ask an LLM to invent substitutes.

### 2.3 Governed query specifications

Reuse:

- `maira.query_specifications`;
- `maira.query_spec_concepts`.

A natural-language question should be converted into a governed query
specification before relationship assertions are treated as evidence-backed
knowledge.

The query specification must preserve:

- query_id;
- query_spec_id;
- component roles;
- governed EMCIP code identifiers;
- requested relationship;
- version/provenance.

### 2.4 Terminology normalisation

Reuse MAIRA's review-gated terminology layer.

Operational normalisations must be human validated before they affect
retrieval or relationship detection.

Current rule:

```text
HUMAN_VALIDATED → operational
PROPOSED        → retained but not operational
REJECTED        → retained for audit only
```

IKF must not silently broaden source terminology using unreviewed synonyms.

### 2.5 Deterministic retrieval

Reuse `maira.retrieval.lexical.retrieve_candidates` as the deterministic
baseline.

The baseline preserves the distinction between:

- passage-level term matches;
- all-role same-passage candidates;
- package-level candidates.

Candidate retrieval does not itself assert a relationship.

Semantic/hybrid retrieval may be evaluated later, but only against frozen
snapshots and with the same provenance controls.

### 2.6 Deterministic relationship assessment

Reuse the MAIRA relationship modules where the requested relationship is
covered by a validated deterministic rule.

Current reusable modules include:

- `maira.relationships.followed_by.detect_followed_by`;
- `maira.relationships.contributed_to.detect_contributed_to`.

Principles:

- explicit source language is required for positive support;
- co-occurrence is not causality;
- chronology is not causality;
- prevention/avoidance is represented as a negative outcome where applicable;
- exact evidence sentences and governed terms are retained.

The operational assessment store is:

`bdw_analysis_prod.maira.query_relationship_assessments`

It preserves query, passage, page, governed concept IDs, relationship,
assessment result, evidence class, cue, direction, matched context, exact
evidence text/hash and deterministic assessment ID.

### 2.7 Frozen retrieval snapshots and benchmark methodology

The validated MAIRA→IKF path already includes:

1. passage bridge validation;
2. governed retrieval validation;
3. deterministic retrieval snapshot identity;
4. identical prompt/evidence to both models;
5. model-run provenance;
6. persisted benchmark outputs;
7. independent metric reproduction;
8. canonical semantic gold matching.

Verified retrieval checkpoint:

```text
snapshot_742f8e0adbccbbf8bf3610015e824415
PASS — MAIRA RETRIEVAL CHECKPOINT
```

This benchmark design must remain the standard for model validation in IKF.

## 3. What remains IKF responsibility

IKF owns:

- information-class declaration A/B/C/D;
- automatic Class-D warning/pre-screen once implemented;
- fail-closed protected-data routing;
- encryption and retention for direct text;
- model-service policy;
- dual-model execution;
- model-run separation;
- privacy validation;
- candidate graph construction;
- human relationship review;
- human EMCIP mapping review;
- promotion of only validated knowledge to authoritative graph knowledge;
- Neo4j projection and investigator visualisation;
- LLM-suggested SHIELD classification only after a contributing factor is human validated, followed by separate human validation of the SHIELD suggestion;
- feedback/evaluation datasets derived from human review.

Human review must remain append-only and distinguish model/assistant output from
human authority.

## 4. EMCIP integration in the generic IKF workflow

The generic IKF pipeline must consume MAIRA's governed EMCIP registry rather
than maintain a second taxonomy implementation.

Target flow:

```text
source evidence
    ↓
MAIRA canonical passages
    ↓
candidate concepts / relationships
    ↓
human relationship/concept validation
    ↓
EMCIP candidate mapping from MAIRA governed registry
    ↓
human EMCIP mapping review
    ↓
validated graph knowledge
```

The EMCIP taxonomy is a controlled vocabulary, not accident evidence.

A model may propose a mapping only against values present in the governed
registry. Missing or ambiguous values remain unresolved.

## 5. Directive / IMO reference framework

The following are methodological/legal reference sources, not evidence about a
particular occurrence:

- Directive 2009/18/EC, as amended by Directive (EU) 2024/3017;
- IMO Casualty Investigation Code, MSC.255(84), applicable consolidated/current
  version;
- IMO Guidelines A.1075(28);
- EMCIP taxonomy and controlled values.

They should support:

- safety-investigation purpose;
- evidence/provenance discipline;
- distinction between sequence, contribution and causation;
- confidentiality/data-minimisation rules;
- investigation terminology and method.

They must not be concatenated into occurrence evidence or used to manufacture a
finding.

Implementation target:

- register them as versioned governed reference material;
- retrieve only the relevant reference fragments for the current analytical
  task;
- tag every retrieved fragment as REFERENCE_CONTEXT rather than SOURCE_EVIDENCE;
- keep reference provenance/version in the model-run record;
- never cite a reference document as proof that an accident fact occurred.

## 6. Bosuil — selective design reference

External reference:

`Fenre1/Bosuil`

Useful ideas to evaluate inside MAIRA/IKF:

### 6.1 Structure-aware deterministic chunking

Bosuil preserves headings, paragraphs, tables and source locations and uses
deterministic structure-aware chunking.

IKF should not import Bosuil's chunker directly. Instead, MAIRA may benchmark
equivalent improvements against its validated passage baseline.

### 6.2 Evidence text separate from retrieval/embedding context

Bosuil keeps the stored source passage distinct from metadata/heading/overlap
context used for embeddings.

This is strongly compatible with the MAIRA/IKF evidence contract:

- exact passage text remains immutable evidence;
- richer retrieval context may be added separately;
- model citations must point back to exact evidence text.

### 6.3 Hybrid retrieval

Bosuil supports keyword, semantic and hybrid retrieval.

MAIRA's deterministic lexical retrieval remains the control baseline.
Semantic/hybrid retrieval may be tested only as an additional candidate
retrieval strategy with:

- frozen snapshots;
- passage hashes;
- query-spec versioning;
- retrieval metrics;
- no silent replacement of the deterministic baseline.

### 6.4 Document-wide fact/evidence ledger

Bosuil's fact ledger is useful as a design pattern for a neutral
question-independent evidence inventory.

A MAIRA/IKF version should:

- scan all canonical passages;
- preserve source passage IDs;
- store factual statements separately from causal interpretation;
- retain raw model output for audit;
- support deduplication without losing contributing source references;
- remain non-authoritative until human reviewed.

This can become a useful precursor to free-form investigation analysis.

### 6.5 Source preview and traceability

Bosuil's source-linked preview reinforces a principle already present in MAIRA:
an investigator should be able to move from an analytical statement to the
exact source passage/page.

A future IKF UI should expose that traceability without copying unnecessary
protected text into Neo4j.

### Explicit Bosuil exclusions

Do not adopt as IKF architecture:

- Bosuil GUI/application shell;
- SQLite as the authoritative store;
- LanceDB as the project vector store;
- Ollama as the general IKF runtime;
- Bosuil's entity/co-occurrence graph as the authoritative causal graph;
- a second independent chunking/retrieval pipeline parallel to MAIRA.

## 7. Class-D detection and routing

Current state: information class is explicitly selected by the investigator.

Target safeguard:

1. retain explicit investigator classification;
2. run a pre-flight classifier/rule layer before any LLM call;
3. detect strong protected-data indicators such as witness statements,
   identities, medical/sensitive personal data, investigator notes/drafts,
   VDR/VTS material and confidentiality markings;
4. if A/B/C was selected and Class-D indicators are found, fail closed;
5. require explicit reclassification/authorised handling;
6. record the pre-flight reason and rule/version;
7. do not treat the detector as a legal determination.

For Class D, raw protected material remains in approved governed storage and
only minimum necessary de-identified analytical derivatives are projected to
Neo4j.

## 8. Human-review layers

Two review layers must remain separate.

### Relationship review

Question:

`Does the source evidence support source —RELATIONSHIP→ target?`

Decision:

- VALIDATED;
- REJECTED;
- AMENDED.

### EMCIP mapping review

Question:

`Is this validated concept correctly mapped to this EMCIP controlled value?`

Decision:

- VALIDATED;
- REJECTED;
- AMENDED.

A relationship may be valid while its EMCIP mapping is amended, or vice versa.

The current App review tabs are still tied to the Commodore Clipper reference
graph. They must be generalised to the selected generated analysis/model run.

## 9. Graph visualisation

Neo4j stores the graph; Streamlit/Cytoscape renders it.

The visual layer should use stable, accessible styling:

- node colour by concept type;
- node shape by concept type;
- edge colour/style by relationship type;
- separate styling for machine candidate vs human validated vs rejected/amended;
- legend always visible;
- provenance/evidence details on selection.

Colour is a UI aid only; semantic type/status remains stored as explicit graph
properties.

## 10. Ordered implementation plan

### Phase A — finish the currently running generic A/B/C path

1. Validate one fresh end-to-end A/B analysis using the workspace-available
   Llama 3.3 70B system model.
2. Confirm summary, candidate graph, privacy validation and Neo4j publication.
3. Fix any remaining runtime defects before adding more analytical layers.

### Phase B — converge document ingestion on MAIRA

4. Replace the document branch of IKF notebook 15 with the canonical MAIRA
   passage bridge for documents already processed in MAIRA.
5. Keep direct text as IKF ingress temporarily.
6. Move direct-text deterministic chunking into a reusable MAIRA passage
   component before retiring duplicate chunking.
7. Preserve MAIRA passage_id/text/hash unchanged throughout IKF.

### Phase C — integrate governed retrieval and deterministic relationship logic

8. Make IKF App questions resolve to persisted MAIRA query specifications where
   the question is representable through the governed query layer.
9. Use MAIRA terminology-normalisation review gates.
10. Use MAIRA deterministic lexical retrieval as baseline.
11. Use deterministic FOLLOWED_BY / CONTRIBUTED_TO assessment where applicable.
12. Persist/retain query_relationship_assessments and exact provenance.

### Phase D — generic human validation

13. Generalise Relationship review to the selected generated analysis/model run.
14. Generalise EMCIP mapping review to the selected generated analysis.
15. Store append-only review provenance.
16. Promote only human-validated graph knowledge to the validated graph layer.

### Phase E — generic EMCIP mapping

17. Generate mapping candidates only against MAIRA's governed EMCIP registry.
18. Preserve unresolved/missing-code cases explicitly.
19. Add human mapping review.
20. Make validated mappings visible in the graph and evidence panel.

### Phase F — Directive/IMO governed reference context

21. Register/version the Directive, IMO Code and A.1075(28) as governed
    REFERENCE_CONTEXT.
22. Implement targeted retrieval of reference fragments by analytical task.
23. Persist reference version/provenance with each model run.
24. Keep REFERENCE_CONTEXT rigorously separate from SOURCE_EVIDENCE.

### Phase G — Bosuil-derived experiments

25. Benchmark structure-aware passage construction against MAIRA's current
    validated passage baseline.
26. Add separate retrieval-context/embedding-context fields without changing
    exact evidence text.
27. Benchmark semantic/hybrid retrieval against the lexical baseline.
28. Prototype a question-independent fact/evidence ledger with passage
    provenance and human-review boundary.
29. Evaluate source-preview improvements in the IKF App.

### Phase H — Class D and SHIELD

30. Add Class-D pre-flight detection/fail-closed routing.
31. Complete dedicated Class-D endpoint/job/security/retention validation.
32. Generalise dual-model human review and benchmarking.
33. For each human-validated contributing factor, let the LLM propose one or more SHIELD mappings with rationale/provenance.
34. Require a separate human VALIDATE / AMEND / REJECT decision on every SHIELD proposal before promotion to validated knowledge.

### Phase I — validation and production-readiness

35. Continue locked benchmark evaluation with canonical semantic gold matching.
36. Measure evidence grounding, relationship precision/recall, causal
    overreach, privacy leakage, graph completeness, stability and human effort.
37. Add regression tests for passage contract, query specs, relationship
    detectors, taxonomy mappings, model routing and review promotion.
38. Update the App to expose model/reference/provenance versions for every
    generated result.

## 11. Non-negotiable governance rules

- Evidence first.
- Exact source wording remains traceable.
- MAIRA passage identity is canonical for MAIRA-processed documents.
- Taxonomy/reference material is not occurrence evidence.
- Co-occurrence is not causality.
- Chronology is not causality.
- Unreviewed terminology must not silently become operational.
- LLM candidates are not validated knowledge.
- Only human-validated knowledge is promoted to the authoritative IKF graph.
- SHIELD follows contributing-factor validation: the LLM may suggest the taxonomy mapping, but human validation is mandatory before promotion.
- Benchmark/evaluation data must remain versioned and reproducible.


## 12. News & Alerts dashboard integration checkpoint — 2026-09-22

The existing Databricks AI/BI country-news dashboard is integrated into the IKF
application as a separate `News & Alerts` capability.

Implementation rule:

- the dashboard remains owned and maintained as a Databricks dashboard;
- IKF embeds the published dashboard rather than recreating its visualisations;
- the App reads the embed URL from `NEWS_DASHBOARD_EMBED_URL`;
- dashboard viewing remains separate from validated investigation knowledge;
- access continues to follow Databricks dashboard sharing and underlying data
  permissions;
- governed LLM access to the underlying news tables is a later capability and
  is deliberately not coupled to the first visual-integration milestone.

This preserves the previously agreed product separation: news/alerts are an
IKF capability, while MAIRA remains the investigation-evidence layer.
