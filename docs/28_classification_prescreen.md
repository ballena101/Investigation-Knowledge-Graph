# Deterministic information-class pre-screen

## Purpose

IKF now applies a deterministic fail-closed pre-screen to reduce the risk that
raw protected investigation material is accidentally processed through a
non-Class-D route.

This is a routing safeguard, not a legal classification engine and not a
certification that content is safe.

The investigator remains responsible for selecting the appropriate information
class.

## Two enforcement points

### App preflight

Before a non-D analysis is created/queued, the App checks:

- direct text for strong protected-record indicators;
- filenames/titles/paths of selected IKF documents for strong protected-record
  labels.

If a strong indicator is found, the App tells the investigator that the input
requires Class D or review before continuing.

The App check is an early-warning UX control only.

### Backend content preflight

Notebook `15_extract_analysis_evidence.py` repeats the authoritative content
check after deterministic extraction and before:
- passages are persisted for the analysis;
- any LLM receives the content;
- graph analysis starts.

Bypassing the UI therefore does not bypass the routing safeguard.

## Current strong indicators

Method:

`IKF_CLASSIFICATION_PRESCREEN_V0.1`

Current strong record-type rules include:

- passport/national-ID style records;
- witness statements/interview/testimony records;
- raw VDR audio/recording/transcript/conversation;
- raw VTS audio/recording/transcript/conversation;
- investigator notes/draft working records;
- medical/health/patient records.

Metadata equivalents are applied to filenames/titles for selected IKF
documents.

A generic public contact email does **not** force Class D by itself because this
would create unacceptable false positives in public technical material.

## Published MAIRA Class B

Published MAIRA investigation material is explicitly treated differently.

A published final report may discuss:
- VDR evidence;
- witness evidence;
- medical information;
- protected investigation records.

That discussion does not mean the published report itself is the raw protected
record.

Therefore:

`Class B + Documents + all sources managed by MAIRA`

is recorded as:

`PUBLISHED_MAIRA_CLASS_B_EXEMPT`

and is not escalated merely because protected evidence types are mentioned in
the published report.

Class-B direct text is not covered by this exemption and is screened normally.

## Fail-closed behaviour

For A/B/C raw/direct or IKF-managed screenable content:

```text
strong protected indicator
        ↓
REQUIRES_CLASS_D
        ↓
AnalysisGroup = FAILED
processing_stage = CLASSIFICATION_PRESCREEN_BLOCKED
        ↓
no analysis passages persisted
        ↓
no model call
```

For blocked direct text:
- the encrypted DirectTextSource payload is removed immediately;
- retention status becomes
  `ENCRYPTED_PAYLOAD_PURGED_AFTER_PRESCREEN`.

The audit record stores rule IDs/counts, not the matched protected text.

## Class D is never downgraded

If the investigator selected Class D, the pre-screen may record whether strong
indicators were detected, but it cannot downgrade the material.

Possible Class-D statuses:

- `DECLARED_D_WITH_STRONG_INDICATORS`
- `DECLARED_D_NO_STRONG_INDICATORS`
- `NO_SCREENABLE_RAW_CONTENT`

Absence of a deterministic indicator is not evidence that protected material is
non-sensitive.

## Source code

Canonical backend rules:

`src/ikf/classification_prescreen.py`

Synthetic tests:

`tests/test_classification_prescreen.py`

Backend enforcement:

`notebooks/15_extract_analysis_evidence.py`

App preflight:

`app/app.py`

## Validation

Read-only notebook:

`43_validate_classification_prescreen.py`

It verifies:
- published MAIRA Class-B exemptions use MAIRA sources;
- a `REQUIRES_CLASS_D` non-D run failed at the prescreen stage;
- blocked runs have no persisted analysis passages;
- blocked direct-text encrypted payloads were purged;
- blocked runs have no ModelRun;
- Class D was never downgraded.

Required success marker:

`PASS — INFORMATION-CLASS PRESCREEN FAILS CLOSED WITHOUT DOWNGRADING CLASS D`

## Runtime status

Implemented in source; runtime validation is deferred to the next consolidated
Databricks test session.


## App preflight audit

A blocked App submission may occur before an AnalysisGroup exists. To preserve
an audit trail without persisting protected content, the App creates a compact
`ClassificationPrescreenAttempt` node only when the early preflight blocks a
non-D submission.

Stored fields are limited to:

- event ID;
- App pre-screen rule version;
- layer = `APP_PREFLIGHT`;
- decision = `BLOCKED_REQUIRES_CLASS_D`;
- declared class and required class;
- input mode;
- triggered rule IDs;
- selected document IDs for document-mode input;
- SHA-256 only for blocked direct text;
- user identity and timestamp.

The audit node must not contain matched text, raw text, source passages or the
matched phrase.

Notebook 43 validates these privacy constraints in addition to the backend
routing invariants.

## App visibility

The App's Technical details section displays the authoritative backend
classification pre-screen status, rule version, triggered rule IDs and any
required processing class.

This visibility is diagnostic/audit information. It does not silently change
the investigator's declared classification.

## Rule/test consistency

The canonical V0.1 rules intentionally do not escalate a generic public email
address by itself because that would create excessive false positives in public
technical material. The synthetic test suite has been aligned to this governed
rule.
