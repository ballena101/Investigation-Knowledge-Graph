# IKF Timeline V0.3 — default chronology architecture

Date: 24 September 2026
Status: implemented in `main`

## Decision

Timeline is a first-class projection of the same evidence-derived Event nodes and chronological relationships used by the Investigation Knowledge Graph. It is not a second independent extraction pipeline and it does not require a separate LLM call.

The Knowledge Graph remains the semantic representation. Timeline is the ordered investigation representation.

## Default behaviour

For every completed analysis, Timeline appears automatically from the available analysed evidence. The investigator does not have to create the chronology manually.

Ordering priority is:

1. evidence-derived `FOLLOWED_BY` relationships already present in the KG;
2. reviewed audio-relative timestamps where available;
3. source passage/page order as a display-only fallback when no supported temporal relation exists;
4. stable unresolved ordering only where the above are unavailable.

`SOURCE_ORDER` is deliberately not persisted as a factual `FOLLOWED_BY` relationship. It only provides a useful default display order and is labelled as such.

Events remain visible even when no absolute clock time is known.

## Investigator review layer

The automatic chronology remains visible while the investigator may:

- validate an existing default event;
- amend its summary, phase, event type, time basis or precision;
- add a supported absolute date/time;
- retain an event as order-only;
- use reviewed audio-relative timestamps;
- add a manual event supported by evidence.

A human decision is persisted as `TimelineEvent` and may link back to the corresponding KG `Event` through `REPRESENTS`.

The reviewed layer does not delete or overwrite the original evidence-derived KG event.

## V0.2 capabilities integrated

The previously planned V0.2 scope is integrated in V0.3:

- automatic chronology from already analysed evidence;
- reuse of KG Event nodes;
- reuse of evidence-derived `FOLLOWED_BY` relationships;
- reviewed audio timestamp integration;
- investigator validation/refinement;
- no additional model inference for Timeline rendering.

## V0.3 capabilities integrated

The previously planned V0.3 scope is integrated as follows.

### Cross-source reconciliation

The same cross-document resolution already used by notebook 16 provides the event concepts used by Timeline. Source conflicts and uncertainties already produced by the analysis are surfaced directly in the Timeline view.

### Chronology conflict detection

A cycle in evidence-derived `FOLLOWED_BY` relationships is never silently resolved. IKF flags the affected events and falls back to source order for display so the investigator can review the chronology.

Timeline also supports a graph property for explicit-time conflicts when available.

### Relative/absolute audio alignment

Reviewed audio evidence remains relative to recording start by default. If an investigator has evidence for the recording's absolute start time, that anchor can be stored on the `AnalysisGroup`. IKF then displays aligned absolute times alongside the original reviewed audio offsets.

The anchor requires an evidence/source note and reviewer identity. No absolute time is invented automatically.

### Investigator comparison

The default chronology remains visible beside the investigator-reviewed layer. The default register indicates which projected KG events already have a human-reviewed TimelineEvent.

## Evidence-based conclusion

Timeline does not call another model to generate a separate conclusion.

The Timeline page reuses the evidence-grounded analysis outputs already produced when the selected documents were read:

- `analysis_summary`;
- `key_findings`;
- `uncertainties`;
- `source_conflicts`.

This avoids divergent summaries and additional inference cost. The conclusion must be interpreted together with any displayed uncertainty or source conflict.

## Governance

- Chronology is not causality.
- `FOLLOWED_BY` is not converted to `RESULTED_IN` or `CONTRIBUTED_TO`.
- Source/passages and reviewed audio remain the evidence basis.
- Source order is a fallback display order, not a factual temporal assertion.
- Human review can refine Timeline without mutating original source evidence.
- Class-D audio provenance remains governed under the existing Class-D controls.

## Implementation

Core deterministic functions:

- `src/ikf/timeline.py`
  - `project_default_timeline()`
  - `audio_bounds_from_locations()`
  - `align_audio_offset()`
- `src/ikf/app_timeline_adoption.py`
  - default KG chronology projection
  - conflict/reconciliation view
  - reviewed audio alignment
  - investigator timeline overlay
  - evidence-based conclusion

Materialized deployment contract:

- `IKF_APP_TIMELINE_ADOPTION_V0.3`
- `IKF_TIMELINE_V0.3`
- `IKF_TIMELINE_PROJECTION_V0.3`

## Cost behaviour

Opening or refreshing Timeline performs read-only Neo4j operations and deterministic Python ordering. It does not call an LLM, Whisper, a Lakeflow Job or a SQL warehouse.
