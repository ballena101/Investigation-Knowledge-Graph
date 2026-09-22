# Generic EMCIP mapping proposal and human-review workflow

## Purpose

This workflow replaces the Commodore Clipper-only EMCIP mapping demonstrator
with a generic AnalysisGroup/ModelRun mapping capability.

The central governance rule remains:

> The LLM may propose an EMCIP mapping, but only a human review can validate,
> reject or amend that proposal.

## Source of taxonomy truth

IKF does not maintain a second EMCIP taxonomy.

All proposal candidates come from the MAIRA operational registry:

`bdw_analysis_prod.maira.emcip_operational_registry`

Proposal provenance preserves:
- taxonomy source document IDs;
- registry-rule version(s);
- EMCIP entity/path;
- attribute name/id;
- controlled value;
- controlled-value idCode.

## Proposal generation

Notebook:

`40_propose_generic_emcip_mappings.py`

Job setup:

`41_create_emcip_mapping_proposal_job.py`

App resource key:

`emcip_mapping_job`

The proposal workflow is on demand. It is deliberately not part of every normal
document-analysis run so it does not create unnecessary model cost.

For one completed AnalysisGroup/ModelRun:

1. load the model graph;
2. build a deterministic bounded EMCIP shortlist from the MAIRA registry;
3. rank candidates using lexical overlap plus graph-node/taxonomy structural
   context;
4. send only that shortlist to the class-approved model;
5. require the model to return one candidate ID from the shortlist or
   `NO_MAPPING`;
6. reject any model output that selects a code outside the shortlist;
7. persist an `EMCIPMappingProposal` separate from the KGNode.

The LLM therefore cannot invent an EMCIP idCode or free-form taxonomy path.

## Human review

The Review & Validate page exposes the proposal with:
- graph concept;
- concept type;
- assistant status;
- proposed EMCIP path/value/idCode;
- assistant rationale;
- complete governed shortlist;
- taxonomy-registry version;
- source report/page references;
- cited source PDF page.

Human decisions:

- `VALIDATED`
- `REJECTED`
- `AMENDED`

An amendment must select another candidate from the same governed shortlist.
Free-text replacement taxonomy values are not accepted.

Review records are append-only `EMCIPMappingReview` nodes linked to:
- the AnalysisGroup;
- the mapping proposal;
- the reviewed KGNode.

The assistant proposal and KGNode are not overwritten.

## Model provenance

Mapping proposals are scoped to a specific `model_run_id`.

This is essential for Class D dual-model analyses: GPT-OSS and Llama graphs are
reviewed independently and cannot be mixed silently.

## Validation

Read-only validation notebook:

`42_validate_generic_emcip_review.py`

It verifies:
- proposal → analysis/model/node consistency;
- proposed codes exist in MAIRA;
- assistant-selected codes were in the deterministic shortlist;
- `NO_MAPPING` proposals carry no selected code;
- human reviews remain linked to the proposal/node;
- AMENDED codes were present in the same governed shortlist and MAIRA registry.

Required success marker:

`PASS — GENERIC EMCIP PROPOSALS AND REVIEWS REMAIN GOVERNED`

## Runtime status

Implementation is complete in source but has not yet been deployed/run.

Before the next App deployment:
1. run notebook 41;
2. attach the created Job to the App with resource key
   `emcip_mapping_job` and `Can manage run`;
3. deploy once with the other accumulated changes;
4. generate proposals for a completed test analysis;
5. save at least one human decision;
6. run notebook 42.
