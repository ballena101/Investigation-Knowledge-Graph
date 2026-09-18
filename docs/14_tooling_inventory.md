# Tooling inventory

This document is the authoritative inventory of the tools and platforms used by
the Investigation Knowledge Graph project.

It should be updated whenever a tool is added, removed, replaced or changes
role.

## 1. GitHub

**Tool:** GitHub  
**Repository:** `ballena101/Investigation-Knowledge-Graph`  
**Role:** source control and project source of truth  
**Status:** active; target authoritative source

GitHub stores:

- application code;
- Databricks processing notebooks;
- SQL / schema scripts;
- technical documentation;
- architecture decisions;
- implementation history through commits.

Target deployment principle:

```text
GitHub
   ↓
Databricks App / Lakeflow processing
```

The existing manually maintained Databricks workspace source folder is
transitional and should be retired only after Git-based deployment is fully
validated.

---

## 2. Databricks

**Tool:** Databricks  
**Role:** governed execution, analytical processing, storage integration and App
hosting  
**Status:** active

Databricks provides several separate capabilities used by the project.

### 2.1 Databricks Apps

**Tool:** Databricks Apps  
**Framework:** Streamlit  
**Role:** investigator-facing application  
**Status:** active

The App provides:

- source-document selection;
- creation of an AnalysisGroup from 1–5 documents;
- automatic processing trigger;
- end-to-end pipeline status;
- analytical summary;
- key findings;
- uncertainties;
- source conflicts;
- generic knowledge graph visualisation;
- relationship review;
- EMCIP mapping review.

The normal investigator workflow should remain inside the App. Processing
notebooks are implementation/debugging surfaces, not normal user steps.

### 2.2 Lakeflow Jobs

**Tool:** Databricks Lakeflow Jobs  
**Role:** automated processing orchestration  
**Status:** being connected to the App

The reusable analysis Job runs sequentially:

1. evidence extraction;
2. cross-document analysis and graph construction.

The App triggers the Job with one parameter:

- `analysis_id`

The intended App resource configuration is:

- resource type: Job;
- resource key: `analysis_job`;
- permission: `Can manage run`.

### 2.3 Unity Catalog

**Tool:** Databricks Unity Catalog  
**Role:** governed data and file access  
**Status:** active

Used for:

- controlled source-document storage;
- Delta tables;
- governed schemas;
- access control.

Current source-document volume:

```text
/Volumes/bdw_analysis_prod/kg_poc/investigation_sources
```

The user manages document upload to this governed volume. The App itself does
not require direct raw-file access in the preferred architecture.

### 2.4 Delta Lake / Delta tables

**Tool:** Delta Lake on Databricks  
**Role:** authoritative analytical persistence and provenance  
**Status:** active

Used for:

- analysis metadata where applicable;
- extracted evidence passages;
- candidate concepts;
- candidate relationships;
- summaries;
- future reviewed analytical records.

Key generic-analysis tables include:

- `bdw_analysis_prod.kg_poc.analysis_group`
- `bdw_analysis_prod.kg_poc.analysis_document`
- `bdw_analysis_prod.kg_poc.analysis_passage`
- `bdw_analysis_prod.kg_poc.analysis_run`
- `bdw_analysis_prod.kg_poc.analysis_candidate`
- `bdw_analysis_prod.kg_poc.analysis_candidate_relationship`
- `bdw_analysis_prod.kg_poc.analysis_summary`

Delta is the preferred governed persistence layer for evidence, provenance and
analytical records.

### 2.5 Databricks Secrets / App resources

**Tools:** Databricks secret scopes and App resources  
**Role:** secure runtime configuration  
**Status:** active

Neo4j connection configuration currently uses:

- `neo4j_uri`
- `neo4j_username`
- `neo4j_password`

The automated workflow uses the App resource key:

- `analysis_job`

Secrets and resource identifiers must not be hard-coded in application source.

---

## 3. Neo4j AuraDB

**Tool:** Neo4j AuraDB  
**Role:** property-graph projection, traversal, exploration and current PoC
review metadata  
**Status:** active

Neo4j stores / projects:

- SourceDocument catalogue metadata;
- AnalysisGroup metadata and processing status;
- generic KGNode nodes;
- graph relationships;
- evidence passage references;
- relationship-review records;
- EMCIP mapping-review records.

Neo4j is used because graph traversal and neighbourhood exploration are natural
operations for the Investigation Knowledge Graph.

Long-term principle:

- Delta / Unity Catalog = governed analytical persistence;
- Neo4j = graph projection, traversal and interactive exploration.

Neo4j must not replace source evidence or provenance.

---

## 4. Streamlit

**Tool:** Streamlit  
**Role:** application UI framework inside Databricks Apps  
**Status:** active

Used to implement:

- forms;
- analysis creation;
- status displays;
- metrics;
- progress indicators;
- review workflows;
- result presentation.

---

## 5. streamlit-cytoscape

**Tool:** `streamlit-cytoscape`  
**Role:** interactive knowledge-graph visualisation  
**Status:** active

Used for:

- reference Commodore Clipper graph;
- generic analysis graph;
- node / relationship visual exploration.

---

## 6. Databricks model services / LLM layer

**Tool:** Databricks model services in `system.ai`  
**Role:** LLM-assisted analytical extraction and cross-document resolution  
**Status:** implemented in the generic analysis pipeline; requires runtime
validation in the target Databricks environment

Current configured model options include:

- `system.ai.gpt-5-6-sol`
- `system.ai.claude-sonnet-4-5`

The LLM is used for:

- candidate concept extraction;
- candidate relationship extraction;
- evidence-grounded normalisation;
- cross-document concept resolution;
- synthesis of summary / findings / uncertainties / source conflicts.

The LLM is **not** an authority.

Methodological controls include:

- no causality inferred from chronology alone;
- causal/contributory edges only when supported by evidence;
- provenance preserved through passage IDs;
- source conflicts kept explicit;
- machine-generated graph relationships remain candidates until review.

---

## 7. Python document-processing libraries

These libraries are implementation dependencies, not independent data stores.

### 7.1 PyMuPDF

**Python package:** `pymupdf` / `fitz`  
**Role:** deterministic PDF text extraction  
**Status:** active

Used with page boundaries preserved and sorted text extraction.

### 7.2 python-docx

**Python package:** `python-docx`  
**Role:** DOCX text extraction  
**Status:** active

### 7.3 langdetect

**Python package:** `langdetect`  
**Role:** lightweight source/passage language detection  
**Status:** active PoC implementation

Language detection does not replace the original text. Original-language
evidence is always preserved.

### 7.4 neo4j Python driver

**Python package:** `neo4j`  
**Role:** application and notebook connectivity to Neo4j AuraDB  
**Status:** active

Current pinned version:

- `neo4j==6.3.1`

### 7.5 Databricks SDK

**Python package:** `databricks-sdk`  
**Role:** trigger and monitor Lakeflow Jobs and interact with Databricks
services programmatically  
**Status:** active in the automated architecture

Current application/notebook pin:

- `databricks-sdk==0.139.0`

---

## 8. MAIRA reusable components

**Project:** MAIRA  
**Relationship:** separate project; reusable document-processing reference  
**Status:** optional reuse, not a runtime dependency of the IKG App

Relevant MAIRA capabilities that may be reused rather than rebuilt include:

- source acquisition;
- PDF extraction;
- page generation;
- passaging;
- document provenance;
- retrieval.

The Investigation Knowledge Graph remains an independent repository,
methodology and analytical layer.

---

## 9. EMCIP reference data

**Resource:** governed EMCIP taxonomy/reference tables  
**Role:** candidate mapping / classification reference  
**Status:** active reference layer

Current governed tables include:

- `bdw_analysis_prod.maira.emcip_attributes`
- `bdw_analysis_prod.maira.emcip_codes`

Important methodological rule:

EMCIP mapping is an analytical/classification layer. It is not evidence that a
source report formally assigned that classification.

---

## 10. Current transitional workspace folder

**Location:**

```text
/Workspace/Users/marta.espinos-palenque@emsa.europa.eu/
Workshop_AI4AI/investigation-kg-poc
```

**Role:** current Databricks App deployment source  
**Status:** transitional / to be retired

This folder currently exists because the Databricks App is still deployed from
a workspace source path.

Target state:

- GitHub becomes the only maintained code source;
- Databricks deploys from the Git-backed repository/project source;
- the old manually copied workspace folder is retired after successful
  end-to-end validation.

Do not delete the folder before validating:

1. Git-based App deployment;
2. App secrets/resources;
3. Lakeflow Job trigger;
4. end-to-end analysis;
5. result display;
6. rollback/redeployment path.

---

## 11. Tool responsibility summary

| Tool / platform | Primary responsibility | Current status |
|---|---|---|
| GitHub | Source control and authoritative project source | Active / target source of truth |
| Databricks Apps | Investigator-facing application | Active |
| Streamlit | App UI framework | Active |
| Lakeflow Jobs | Automated extraction/analysis orchestration | Being connected |
| Unity Catalog | Governed file/data access | Active |
| UC Volume | Source-document library | Active |
| Delta Lake | Evidence/provenance/analytical persistence | Active |
| Neo4j AuraDB | Graph projection, traversal, review metadata | Active |
| streamlit-cytoscape | Interactive graph rendering | Active |
| Databricks model services | LLM-assisted analytical extraction/resolution | Implemented; runtime validation required |
| PyMuPDF | PDF text extraction | Active |
| python-docx | DOCX text extraction | Active |
| langdetect | Language detection | Active PoC |
| neo4j Python driver | Neo4j connectivity | Active |
| Databricks SDK | Job orchestration / Databricks API access | Active |
| EMCIP reference tables | Controlled taxonomy mapping | Active |
| MAIRA | Reusable document-processing components/reference | Separate / optional reuse |
| Old workspace App folder | Current deployment source | Transitional |

## 12. Architectural principle

The toolchain should preserve a clean separation of responsibilities:

```text
GitHub
  source of truth for code and documentation
        ↓
Databricks
  governed execution + orchestration + storage
        ↓
Delta / Unity Catalog
  evidence + provenance + analytical persistence
        ↓
Neo4j
  graph projection + traversal + interactive graph state
        ↓
Databricks App
  investigator interaction + status + review + results
```

The LLM assists analytical extraction inside this architecture but does not
replace evidence, governance or human review.
