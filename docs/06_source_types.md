# Source Types

The long-term project is not limited to accident investigation reports.

## Supported conceptual source families

### Formal investigation documents
- final reports;
- interim reports;
- annexes;
- recommendations;
- actions taken.

### Interview material
- interview transcripts;
- witness interviews;
- investigator notes;
- recorded-statement transcripts.

Important transcript metadata:

- speaker;
- interviewer;
- timestamp;
- utterance ID;
- question;
- answer.

### Operational evidence
- VDR transcripts;
- bridge communications;
- alarm logs;
- event logs;
- maintenance records;
- checklists.

### Organisational material
- procedures;
- manuals;
- safety management documentation;
- internal correspondence;
- emails.

### Technical material
- inspection notes;
- laboratory findings;
- equipment reports;
- technical diagrams and supporting reports.

## Cross-source objective

A single graph statement may be supported, contradicted or qualified by several sources.

Future analysis should therefore support:

- corroboration;
- contradiction;
- source comparison;
- chronology reconstruction;
- claim attribution;
- confidence / evidence sufficiency.


## Operational source ownership in the current PoC

The current App does not treat all indexed documents as one undifferentiated
selection list. Document visibility follows the real source ownership model.

### Class B — published investigation material

Published investigation reports and their associated investigation documents
are sourced from **MAIRA**.

MAIRA is the canonical repository for:
- investigation reports;
- annexes;
- appendices;
- other published investigation-package documents registered in MAIRA.

The App catalogue exposes MAIRA registry metadata, but the source files remain
owned by MAIRA and stored in the MAIRA Unity Catalog volume.

### Class A — public / technical material

Technical and other non-investigation public documents are sourced from the
**IKF-managed document library**.

This includes technical/reference material stored for IKF use that is not part
of the MAIRA investigation-report corpus.

### Classes C and D

Internal/restricted and protected/confidential document inputs are also limited
to the **IKF-controlled document path**. MAIRA's published investigation
repository is not used as a Class-C/Class-D source store.

Direct text remains a separate ingress and follows the selected information
class/model-routing controls rather than the document-catalogue filter.

Operational selector rule:

```text
Class A → IKF documents
Class B → MAIRA investigation documents
Class C → IKF documents
Class D → IKF documents
```

This routing is a catalogue/source-ownership rule. It does not change the
separate model-routing policy for A/B/C/D.
