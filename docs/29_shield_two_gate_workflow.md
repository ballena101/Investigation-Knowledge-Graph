# SHIELD two-gate classification workflow

## Purpose

SHIELD is a governed classification resource for contributing factors.

It is **not**:
- occurrence SOURCE_EVIDENCE;
- legal/technical REFERENCE_CONTEXT;
- EMCIP CONTROLLED_TAXONOMY.

SHIELD classification is intentionally downstream of human validation of the
contributing factor.

## Source ownership

Existing persistent source folder:

`/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/SHIELD`

This folder is reserved and excluded from the generic SourceDocument catalogue
and transient input-document retention.

Notebook `14_index_volume_documents_to_neo4j.py`:
- skips `SHIELD/` during ordinary source discovery;
- migrates previously indexed SHIELD SourceDocument metadata to
  `RESERVED_TAXONOMY`;
- clears transient source expiry;
- marks source management as `IKF_SHIELD`.

## Persistent SHIELD corpus

Notebook:

`45_index_shield_corpus.py`

Governed Delta tables:

- `bdw_analysis_prod.kg_poc.shield_document`;
- `bdw_analysis_prod.kg_poc.shield_passage`.

Compact `ShieldDocument` metadata is mirrored to Neo4j for App discovery and
source-page viewing. SHIELD passage text remains in Delta.

Each indexing run derives a deterministic corpus snapshot from the source-file
SHA-256 set:

`shield_snapshot_<hash>`

The implementation does not invent a taxonomy version from filenames.

## Gate 1 — validate the contributing factor first

A SHIELD proposal is eligible only when the **latest** append-only
`RelationshipReview` confirms:

```text
ContributingFactor — CONTRIBUTED_TO → target
```

Eligible decisions:

1. `VALIDATED` and the original relationship is `CONTRIBUTED_TO`; or
2. `AMENDED` and the amended relationship is `CONTRIBUTED_TO`.

Rejected relationships and amendments to another relationship are ineligible.

This makes the existing human relationship review the first human gate rather
than creating a redundant second validation of the same analytical assertion.

## Assistant proposal

Notebook:

`46_propose_shield_classifications.py`

For each Gate-1 eligible factor:

1. construct retrieval text from factor label, description and target;
2. use MAIRA's deterministic `retrieve_free_text` implementation over the
   persistent SHIELD passages;
3. send only the validated factor and retrieved SHIELD passages to the model;
4. require JSON containing proposed label/code/path and supporting SHIELD
   passage IDs;
5. verify returned passage IDs are inside the deterministic retrieval result;
6. require the proposed SHIELD label, and code if supplied, to occur in the
   retrieved SHIELD source text.

If grounding fails, persist:

`NO_GROUNDED_PROPOSAL`

rather than accepting an invented classification.

A successful candidate is stored as:

`ShieldProposal`

with:
- analysis/model provenance;
- contributing-factor node;
- target node;
- Gate-1 relationship-review ID;
- model service;
- proposal version;
- SHIELD corpus snapshot;
- deterministic retrieval method;
- SHIELD passage IDs/report-page references/locations;
- assistant rationale.

The proposal is linked to:
- its AnalysisGroup;
- the factor KGNode;
- the Gate-1 RelationshipReview.

It does not mutate the KGNode.

## Stale Gate-1 protection

A SHIELD proposal is valid for Gate 2 only while its Gate-1 review remains the
latest human review for that relationship.

If the relationship receives a newer human review, the previous ShieldProposal
is marked stale in the App and cannot be validated. It must be regenerated.

## Proposal Job

Notebook:

`47_create_shield_proposal_job.py`

Job:

`Investigation KG - SHIELD Proposals`

App resource:

`shield_proposal_job`

Environment variable:

`SHIELD_PROPOSAL_JOB_ID`

Permission:

`Can manage run`

## Gate 2 — human SHIELD review

The App exposes SHIELD classification in Review & Validate.

For each grounded, current assistant proposal the investigator may:

- `VALIDATED`;
- `REJECTED`;
- `AMENDED`.

Every action creates a separate append-only `ShieldReview`.

The review stores:
- proposal ID;
- factor node and analysis/model provenance;
- Gate-1 review ID;
- original assistant SHIELD label/code/path;
- SHIELD corpus snapshot;
- human decision/status;
- amended label/code/path when applicable;
- reviewer identity/time/comment.

The proposal and graph are never overwritten.

## Authoritative value

The assistant ShieldProposal is never authoritative.

An authoritative reviewed SHIELD classification exists only when the latest
valid Gate-2 human review is:

- `HUMAN_VALIDATED`; or
- `HUMAN_AMENDED`.

`HUMAN_REJECTED` means no authoritative SHIELD classification is accepted
from that proposal.

## Source-page inspection

The App displays:
- validated contributing factor;
- target event/concept;
- Gate-1 review ID;
- assistant SHIELD proposal;
- corpus snapshot;
- assistant rationale;
- cited SHIELD taxonomy pages.

The source PDF page is rendered through the existing user-authorised Databricks
Files API viewer. The SHIELD folder remains under the already authorised IKF
source root.

## Retention

SHIELD source documents/passages are persistent governed resources.

When an analysis expires, notebook 23 scrubs transient assistant proposal
content:
- rationale;
- SHIELD passage IDs;
- SHIELD references;
- SHIELD page locations.

Compact proposal/governance metadata and human ShieldReview records may remain
under the project's review/audit retention policy.

## Validation

Notebook:

`48_validate_shield_two_gate_workflow.py`

It verifies:
- factor is a ContributingFactor;
- proposal is linked to AnalysisGroup, factor and Gate-1 RelationshipReview;
- Gate 1 actually confirms CONTRIBUTED_TO;
- Gate 1 is still current;
- assistant label/code are grounded in cited SHIELD passages;
- cited passages belong to the recorded SHIELD snapshot;
- NO_GROUNDED_PROPOSAL contains no classification value;
- every ShieldReview links to proposal, factor and Gate-1 review;
- Gate-2 decision/status pairs are valid;
- amended decisions contain an amended label.

Required success marker:

`PASS — SHIELD PROPOSALS REQUIRE GATE 1 AND AUTHORITATIVE CLASSIFICATION REQUIRES GATE 2`

## Runtime status

Implemented in source; runtime validation is deferred to the next consolidated
Databricks session.
