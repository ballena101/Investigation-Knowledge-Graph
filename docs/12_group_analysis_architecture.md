# Group Analysis Architecture

## Objective

Move the controlled Commodore Clipper demonstrator to a generic analysis model in which a user can upload a group of documents and obtain one evidence-grounded analysis for that group.

The unit of analysis is the **analysis group**, not the individual PDF.

```text
Analysis group
  ├─ Document 1
  ├─ Document 2
  ├─ Document 3
  └─ ...
       ↓
document extraction + evidence units
       ↓
cross-document entity / event resolution
       ↓
one evidence-grounded analysis graph
       ↓
EMCIP mapping + human review
```

## Core identifiers

### analysis_id

A unique identifier for one user-created analysis group.

All documents, passages, concepts, relationships, mappings and review records produced from the group must carry the same `analysis_id`.

### document_id

A deterministic identifier for one uploaded source document.

The document ID should be based on document bytes (SHA-256) so the same binary source can be recognised reliably.

### passage_id

A deterministic identifier for one extracted evidence unit within a document.

Passages preserve:

- document ID;
- page number or page range;
- passage order;
- extracted text;
- extraction version;
- source provenance.

## Analysis group

A new analysis should contain:

- `analysis_id`;
- analysis title;
- optional analysis objective / question;
- creator identity;
- creation timestamp;
- status;
- number of source documents;
- pipeline / graph version.

The user may upload multiple PDFs in a single action. All files uploaded in that action belong to the same analysis unless the user explicitly creates another analysis.

## Source handling

Raw documents must remain separate and traceable.

Recommended persistent storage:

- raw documents: Unity Catalog Volume;
- metadata / pages / passages: Delta / Unity Catalog;
- analytical graph projection: Neo4j;
- human review: append-only review records, initially in Neo4j for the PoC.

Databricks recommends Unity Catalog volumes for governed non-tabular data such as PDFs.

## Processing principle

Do not analyse each PDF independently and simply merge the resulting graphs.

Instead:

### Stage 1 — Source registration

For every document:

- calculate SHA-256;
- assign `document_id`;
- preserve original filename;
- preserve upload path;
- identify MIME type;
- record source provenance.

### Stage 2 — Extraction and passaging

Reuse the MAIRA extraction / passaging approach where practical.

For PDFs:

- extract page text;
- retain page boundaries;
- create manageable evidence passages;
- persist deterministic passage IDs.

No analytical inference is required at this stage.

### Stage 3 — Document-level candidate extraction

Extract candidate:

- vessels / actors / organisations;
- events;
- contributing factors;
- findings;
- safety issues;
- recommendations / actions;
- temporal references;
- claims.

Every candidate must link back to one or more evidence passages.

### Stage 4 — Group-level resolution

Resolve candidate concepts across all documents in the group.

Examples:

- two documents referring to the same fire should normally resolve to one event concept;
- a witness statement and final report may support the same claim;
- two sources may contradict each other and must remain distinguishable;
- source attribution must be preserved.

This is where the analysis becomes group-level rather than document-level.

### Stage 5 — Relationship synthesis

Create candidate graph relationships only when supported by evidence.

Relationship vocabulary remains controlled:

- `FOLLOWED_BY`
- `CONTRIBUTED_TO`
- `RESULTED_IN`
- `AFFECTED`
- deterministic structural relationships where appropriate.

Chronology must not be converted automatically into causality.

### Stage 6 — EMCIP analytical mapping

Apply EMCIP mapping only after the case concepts are resolved.

Maintain the existing separation:

```text
SOURCE EVIDENCE
    ↓
CASE / ANALYSIS GRAPH
    ↓
EMCIP ANALYTICAL MAPPING
```

Unresolved mappings remain explicitly unresolved.

### Stage 7 — Human review

Reuse the current review model:

- relationship review;
- EMCIP mapping review;
- `VALIDATED`, `REJECTED`, `AMENDED`;
- original assistant output is never silently overwritten;
- reviewer identity and timestamp are retained.

## Standard outputs for one analysis group

Each completed analysis should expose:

1. source inventory;
2. extracted evidence coverage;
3. resolved concepts;
4. chronology where supported;
5. causal / contributory relationships where supported;
6. findings and safety issues where present;
7. recommendations / actions where present;
8. corroborating or contradictory sources;
9. EMCIP analytical mappings;
10. interactive graph;
11. relationship review;
12. EMCIP mapping review.

## App workflow

Proposed user workflow:

```text
New analysis
    ↓
Name analysis
    ↓
Optional objective / question
    ↓
Upload multiple PDFs
    ↓
Create analysis
    ↓
Extract / analyse group
    ↓
Open analysis workspace
```

Analysis workspace:

```text
Sources
Graph
Relationships
EMCIP mappings
Review
Analysis summary
```

## Databricks authorization direction

For the generic App, prefer Databricks **user authorization** for Databricks-native resources.

Candidate scopes:

- `files` — upload/read documents in a Unity Catalog volume;
- `sql` — write/read analysis metadata and passages using the user's existing permissions;
- `model-serving` — invoke an approved model endpoint under the user's permissions.

This avoids repeating the earlier problem where the App service principal required the developer to grant permissions on resources they could use but could not manage.

The existing Neo4j secrets may continue to use App authorization.

## PoC implementation order

1. Create group-analysis metadata tables.
2. Create or select a writable UC Volume for uploaded source documents.
3. Add a **New analysis** upload page to the App.
4. Persist analysis + document metadata.
5. Reuse MAIRA PDF extraction / passaging.
6. Add model-assisted candidate extraction.
7. Resolve candidates across the group.
8. Publish one Neo4j graph using `analysis_id`.
9. Generalise current graph/review UI from fixed Commodore Clipper constants to selectable analyses.
10. Test with:
   - one PDF;
   - several PDFs for the same investigation;
   - heterogeneous evidence for one investigation.


## Raw document volume

Initial PoC volume:

`bdw_analysis_prod.kg_poc.investigation_sources`

Path:

`/Volumes/bdw_analysis_prod/kg_poc/investigation_sources/<analysis_id>/`

Each analysis receives its own directory. Source filenames are preserved in metadata, while the stored object name should include the deterministic document ID to avoid collisions.


## Multilingual analysis

Language is treated as metadata and presentation context, not as a transformation of source evidence.

The model separates:

- **source language handling** — one language, mixed documents, or automatic detection per document;
- **detected document language** — populated during extraction;
- **detected passage language** — available when a document itself contains mixed-language sections;
- **analysis output language** — the language used for summaries and analytical explanations.

Original source text is always preserved. Any future translation is derivative material and must retain a link to the original evidence passage.

This allows one analysis group to contain, for example, an English investigation report, a Spanish witness statement and a Portuguese technical note without collapsing their provenance.


## Preferred PoC ingestion route

Where the investigator can write to a Unity Catalog volume but cannot delegate
the parent catalog to a Databricks App service principal, the PoC uses a
user-driven volume-folder workflow.

```text
User creates folder in own accessible UC volume
        ↓
User uploads all documents for one analysis
        ↓
Notebook 13 registers folder as one analysis_id
        ↓
Extraction / passaging notebook
        ↓
Group-level analytical pipeline
        ↓
Neo4j graph + review App
```

This deliberately separates **source ingestion** from the review App. The source
files remain governed by Unity Catalog under the investigator's normal
permissions. The App does not need direct access to the source volume.

One folder represents one analysis group. A `manifest.json` is written into the
folder to preserve the analysis ID, document IDs, hashes, language settings and
source provenance.
