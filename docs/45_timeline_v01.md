# IKF Timeline V0.1

## Purpose

Timeline is a governed case chronology inside the IKF App. It complements, but
does not replace, Findings & Evidence or the Knowledge Graph.

- Findings & Evidence answers **what is supported and where**.
- Knowledge Graph answers **how concepts and relationships connect**.
- Timeline answers **when supported events occurred, or what supported order is
  known when no reliable clock time exists**.

Timeline V0.1 is deterministic and zero-inference. It does not call an LLM and
must never manufacture temporal precision.

## App surface

A new `Timeline` tab is materialized between `Findings & Evidence` and
`Knowledge Graph` in the lean `databricks_app/` bundle. The Home capability
page also exposes Timeline as an active PoC capability.

Timeline always follows the shared `Active analysis` selection.

## Governed event contract

Each persisted event has:

- `timeline_event_id`
- `analysis_id`
- `summary`
- `event_type`
- `phase`
- `time_basis`
- `time_precision`
- optional absolute start/end
- optional relative-audio start/end offsets
- optional linked KG Event node
- evidence references and evidence locations
- `review_status = HUMAN_VALIDATED`
- reviewer identity and creation timestamp
- `timeline_version = IKF_TIMELINE_V0.1`

### Time bases

`ABSOLUTE`
: The source supports a calendar date/time.

`RELATIVE_AUDIO`
: The source supports only an offset from the beginning of an audio recording.
  The UI displays the audio-relative chronology separately from absolute time.

`ORDER_ONLY`
: The evidence supports sequence/order but no defensible clock time.

These three bases are deliberately not silently converted into one another.

### Absolute precision

- `EXACT`
- `MINUTE`
- `APPROXIMATE`
- `RANGE`
- `DATE_ONLY`

### Relative-audio precision

- `RELATIVE_AUDIO`
- `APPROXIMATE`
- `RANGE`

A range end cannot precede its start. Relative offsets cannot be negative.
Order-only events do not receive fabricated start times.

## Investigation phases

V0.1 provides these non-mandatory phase bands:

- `PRE_ACCIDENT`
- `ACCIDENT_INITIATION`
- `ESCALATION`
- `EMERGENCY_RESPONSE`
- `ABANDONMENT_RESCUE`
- `POST_OCCURRENCE`
- `INVESTIGATION`
- `UNASSIGNED`

They are presentation/organisation metadata, not causal findings.

## Human validation gate

Timeline events are persisted only after the logged-in investigator explicitly
confirms that the time/order is supported by evidence and does not imply more
precision than the source.

Existing `KGNode(node_kind='Event')` nodes may be selected as candidate event
concepts. Selecting one copies its existing evidence references/locations into
the proposed timeline event. The KG candidate is **not** automatically promoted:
the investigator still supplies/checks the time basis and confirms the event.

Timeline summaries are passed through the existing protected-record pre-screen.
Derived timeline labels should be concise and de-identified; source evidence
remains separately governed.

## Persistence in V0.1

For immediate interactive App use, Timeline V0.1 persists `TimelineEvent` nodes
in the existing Neo4j transaction path:

```text
(AnalysisGroup)-[:HAS_TIMELINE_EVENT]->(TimelineEvent)
(TimelineEvent)-[:REPRESENTS]->(KGNode:Event)   # optional
```

This avoids adding a Databricks SQL warehouse resource merely to support App
writes, which would add configuration and potential compute cost to the PoC.

A Delta/Unity Catalog timeline table remains the intended analytical snapshot
layer for cross-case metrics and future AI/BI reporting. The schema is defined
by `notebooks/64_create_timeline_delta_schema.py` at:

`bdw_analysis_prod.kg_poc.ikf_timeline_event`

Notebook 64 is schema-only and idempotent; it performs no inference and does not
copy or mutate Neo4j data. A later sync step should materialize only the governed
`TimelineEvent` register into Delta without rerunning LLMs.

Direct Delta-backed App persistence can be reconsidered if/when an existing SQL
warehouse is attached to the App for other justified capabilities.

## Visualisation

The App uses Streamlit's built-in Vega-Lite renderer; no new Python charting
package is required.

- Absolute events: calendar-time timeline.
- Audio-relative events: separate seconds-from-audio-start timeline.
- Point events and duration/range events are visually distinct.
- Colour/lane grouping uses investigation phase.
- Hover data shows event, type, precision and supported time.

The event register below the charts preserves the review identity and evidence
count.

## Cost behaviour

Timeline V0.1 performs:

- no model inference;
- no Databricks Job run;
- no Whisper run;
- no SQL warehouse start;
- no document re-parsing.

It reuses the already persisted graph/evidence objects and Neo4j connection.

## Implementation status — 24 September 2026

### Done

- deterministic timeline event contract (`src/ikf/timeline.py`);
- Timeline App adoption (`src/ikf/app_timeline_adoption.py`);
- active-analysis Timeline tab between Findings & Evidence and Knowledge Graph;
- Home capability card;
- human-validation gate before persistence;
- optional linkage to existing `KGNode(node_kind='Event')` candidates;
- evidence-reference/location carry-over from linked KG Event candidates;
- absolute, relative-audio and order-only time bases;
- explicit precision handling and range validation;
- built-in Vega-Lite absolute and audio-relative chronology views;
- validated event register with reviewer identity;
- lean App bundle contract V0.4 and automatic materialisation;
- deterministic unit/regression coverage;
- Delta/UC analytical snapshot schema notebook 64;
- CI regression PASS on the Timeline materialisation state.

### Pending / planned sequence

1. **Runtime validation after App redeploy** — confirm tab rendering, event save,
   reload and active-analysis switching on persisted analyses.
2. **Evidence opening from Timeline** — open the cited PDF page or audio timestamp
   directly from a selected timeline event.
3. **Reviewed-audio ingestion** — propose timeline candidates from already
   human-reviewed transcript timestamps without another Whisper or LLM run.
4. **Delta snapshot sync** — copy only human-validated TimelineEvent records into
   `bdw_analysis_prod.kg_poc.ikf_timeline_event` for cross-case analytics.
5. **Chronology consistency checks** — flag conflicts between validated timeline
   order and reviewed `FOLLOWED_BY` KG relationships; do not auto-correct either.
6. **Cross-source reconciliation** — compare report, audio and news timestamps while
   keeping external/news context visually separate from investigation evidence.

## Follow-on versions

V0.2 should add deterministic ingestion of already validated audio timestamps
and reviewed temporal metadata from processed evidence, plus richer evidence
opening from the Timeline event itself.

V0.3 can add cross-source chronology reconciliation, conflicting-time detection,
absolute/relative alignment where an authoritative recording start time exists,
and controlled synchronisation checks against `FOLLOWED_BY` KG relationships.

Any automatic temporal extraction must remain a candidate-generation step and
must not become validated chronology without investigator review.
