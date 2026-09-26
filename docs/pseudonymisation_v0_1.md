# IKF pseudonymisation v0.1

## Purpose

IKF pseudonymisation is a source-agnostic privacy transformation. It can operate on direct text, governed PDF/text/interview material and transcript text. The canonical source is never overwritten.

## Processing model

1. The source must already have an IKF information classification (A/B/C/D).
2. The investigator selects which entity categories should be pseudonymised.
3. Structured identifiers are detected deterministically in v0.1; contextual entities can be supplied/reviewed explicitly.
4. Replacement is deterministic and stable within the derivative (for example `PERSON_001`).
5. The investigator reviews the derived text before reuse.
6. The derived text can be downloaded as TXT or saved as a reusable governed IKF input.

## Reusable pseudonymised derivatives

A reviewed derivative is persisted as an encrypted `PseudonymisedDerivative` record. The reversible mapping is encrypted separately. The derivative stores its source class, approved processing class, pseudonymisation version and parent source identifiers/labels. Where the parent is a governed `SourceDocument`, a `DERIVED_FROM` relationship is also persisted.

Saved derivatives are shown in the Analyse Documents selector for their approved processing class with a label such as:

`[IKF · Pseudonymised · Class C] Interview 04.txt · derived from Interview 04.pdf`

The derivative is not a new information class. `PSEUDONYMISED_DERIVATIVE` is a privacy/source status. A/B/C/D remain the processing classes.

For Class D sources, pseudonymisation does not automatically permit downgrade. A reviewed derivative may be explicitly approved for Class C processing in the PoC; automatic D→A/B downgrades are not permitted.

The reusable derivative reuses the existing encrypted DirectTextSource analysis ingress. No second LLM analysis pipeline is created. V0.1 allows one saved derivative per analysis and does not mix a saved derivative with original documents in the same analysis.

## Translation boundary

English is the IKF analysis language. Translation is not a mandatory preprocessing layer.

Where the governing information class permits the selected LLM, a user may request an on-demand translation of an English analytical output, transcript, passage or document representation into another language (for example French) through the Ask/output interaction. Such a translation is a derived presentation output and does not replace the canonical source or the English analytical evidence.

EU eTranslation is therefore not a required dependency. It may be evaluated later as an optional translation provider/benchmark where its supported languages, access conditions, terminology quality and reliability provide a demonstrated benefit.

## Security and provenance

- Original sources are not overwritten.
- Reusable derivative text is encrypted at rest using the existing governed direct-text encryption mechanism.
- Reversible pseudonym mappings are stored encrypted and separately from user-facing pseudonymised text.
- Saved derivatives retain parent source IDs/labels and the pseudonymisation version.
- No derivative is treated as public solely because it has been pseudonymised.
