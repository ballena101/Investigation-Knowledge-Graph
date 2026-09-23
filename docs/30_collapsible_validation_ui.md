# Collapsible validation UX

_Last updated: 2026-09-23_

## Decision

Human-governance workflows remain available in the PoC, but they must not dominate the normal investigator experience.

The default presentation is therefore **result first, validation on demand**.

For Relationships, EMCIP and SHIELD, the analytical result/suggestion and its evidence remain visible. The corresponding human decision controls are placed inside a collapsed **Validation** expander that the investigator opens only when a governance decision is required.

## Relationships

Default visible content:

- relationship label and direction;
- supporting source evidence and page;
- current review state when one exists.

Collapsed **Validation** content:

- VALIDATE;
- REJECT;
- AMEND;
- optional evidence-bounded assistant relationship-quality/correction proposal;
- review comment and reviewer provenance.

The existing append-only `RelationshipReview` governance remains unchanged. Graph edges are not silently overwritten.

## EMCIP

Default visible content:

- extracted IKF concept;
- assistant-suggested EMCIP mapping or `NO_MAPPING`;
- governed shortlist when useful;
- source evidence/page;
- visible indication that the mapping is AI-suggested unless human-reviewed.

Collapsed **Validation** content:

- VALIDATED;
- REJECTED;
- AMENDED;
- amendment limited to governed EMCIP candidates;
- review comment and reviewer provenance.

The assistant mapping remains a proposal. Human review is optional in the normal user journey and becomes authoritative only when performed.

## SHIELD

Default visible content:

- eligible contributing factor;
- assistant-suggested SHIELD category or `NO_GROUNDED_PROPOSAL`;
- SHIELD source evidence/page;
- visible indication that the classification is AI-suggested unless human-reviewed.

Collapsed **Validation** content:

- Gate-2 VALIDATED;
- REJECTED;
- AMENDED;
- review comment and reviewer provenance.

Gate-1 relationship governance remains a prerequisite in the current governed design. The App should not force the investigator through Gate 2 during ordinary browsing.

## UX principle

> Show useful analytical information immediately; ask for a human governance decision only when the investigator chooses to review it.

This avoids duplicating the analytical content in a separate form-heavy workflow and keeps formal validation available without making it a mandatory navigation step.

## Target App structure

`Findings & Evidence` is the preferred evidence-centred location for relationship inspection and, eventually, relationship validation. EMCIP and SHIELD suggestions may also be shown alongside the relevant concept/factor where practical.

A separate `Review & Validate` page may remain as a compact governance queue/summary for advanced users, but it should not duplicate the full evidence presentation already available elsewhere.

## Implementation constraint

This change is presentation-only. It must reuse the existing append-only review records, proposal objects, taxonomy registries and human-governance rules. No data-model or model-pipeline change is required.

Status: **architecture decision documented; App-source refactor pending the next safe source-edit/deployment slice.**
