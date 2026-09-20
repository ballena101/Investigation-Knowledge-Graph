# Tooling inventory

This document is the authoritative inventory of the tools and platforms used by
the Investigation Knowledge Graph project.

It should be updated whenever a tool is added, removed, replaced or changes
role.

## Data protection and confidentiality reference

Every tool listed here must also be read together with:

`docs/15_data_protection_confidentiality.md`

That document defines the project's rules for personal data, protected
investigation material, Article 9 confidentiality, least privilege, data
minimisation, logging, model prompts, retention, data movement and tool
admission.

A tool being technically available does **not** mean that confidential
investigation data are authorised to be processed by it.

## 1. GitHub

**Tool:** GitHub  
**Repository:** `ballena101/Investigation-Knowledge-Graph`  
**Role:** source control and project source of truth  
**Status:** active; target authoritative source

**Confidentiality position:** code/documentation repository only. Raw
investigation evidence, personal data, witness material, VDR/VTS material,
credentials and model prompts containing protected evidence must not be stored
in GitHub.

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

**Confidentiality position:** preferred governed execution environment. Whether
a specific confidential dataset may be processed still depends on access,
classification, contractual, retention and organisational approval.

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

**Confidentiality position:** preferred primary store for approved protected
source material because access is governed through Unity Catalog. Broad
inherited grants must be reviewed before loading confidential investigation
records.

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

**Confidentiality position:** may contain protected extracted evidence and
analytical derivatives. Table/schema permissions, retention and minimisation
must reflect the sensitivity of the source.

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

**Confidentiality position:** graph projection layer, not the default raw
evidence repository. Store references and authorised analytical derivatives in
preference to full witness statements, VDR/VTS transcripts, health data or
other protected source content.

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

**Confidentiality position:** presentation layer only. It must display only
authorised content and must not expose protected text in logs, URLs or
client-visible state unnecessarily.

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

**Confidentiality position:** visualisation library only. Graph labels and
tooltips should avoid unnecessary personal or protected evidence text.

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

**Confidentiality position:** no protected/Class D investigation material
should be sent to a model service until the specific service/model has been
approved for that data classification, including contractual, processor /
subprocessor, data-location, retention/logging and model-use considerations.

Current model routes are:

- `system.ai.gpt-5-6-sol` — Classes A/B
- `system.ai.gpt-oss-120b` — Class C
- dedicated GPT-OSS 20B endpoint — Class D option
- dedicated Meta Llama 3.3 70B endpoint — Class D option

### Exact default model and applicable policy

For Classes A/B the default analytical model is:

`system.ai.gpt-5-6-sol`

Class C uses:

`system.ai.gpt-oss-120b`

Class D is comparison-capable and uses dedicated endpoints for GPT-OSS 20B
and/or Meta Llama 3.3 70B.

**Data-flow caveat:** this is not classified by the IKG as a zero-retention or
zero-provider-exposure path. Databricks Foundation Model API retention rules
and partner-provider safety retention conditions may apply. It is therefore
appropriate for published/non-sensitive PoC material, but not automatically
approved for Article 9/Class D evidence.

This is a Databricks Unity Catalog `system.ai` model service for OpenAI
GPT-5.6 Sol.

Its use is subject to the organisation's Databricks agreement, Databricks Model
Serving / Foundation Model API data-protection and retention terms, and the
applicable model terms listed by Databricks. Databricks currently identifies
OpenAI Usage Policy and OpenAI high-risk use-case mitigation requirements as
applicable terms for GPT-5.6 Sol.

The exact model selected is stored and displayed per analysis. A change to the
model changes the applicable provider/model terms and must be reflected in the
App disclosure and this inventory.

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

**Confidentiality position:** local processing dependency inside Databricks;
extracted text inherits the confidentiality classification of the source and
must remain in governed storage.

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

| Tool / platform | Primary responsibility | Confidentiality position | Current status |
|---|---|---|---|
| GitHub | Source control and authoritative project source | Code/docs only; no raw protected evidence or secrets | Active / target source of truth |
| Databricks Apps | Investigator-facing application | Authorised presentation/orchestration only; minimise direct raw evidence access | Active |
| Streamlit | App UI framework | Active |
| Lakeflow Jobs | Automated extraction/analysis orchestration | Run under least-privilege identity; no protected text in routine logs | Being connected |
| Unity Catalog | Governed file/data access | Preferred governed store for approved confidential data | Active |
| UC Volume | Source-document library | May contain approved protected evidence; strict grants required | Active |
| Delta Lake | Evidence/provenance/analytical persistence | May contain protected evidence/derivatives; governed access and retention required | Active |
| Neo4j AuraDB | Graph projection, traversal, review metadata | Prefer references/derivatives; raw protected evidence only if explicitly approved | Active |
| streamlit-cytoscape | Interactive graph rendering | Avoid exposing unnecessary protected text in graph UI | Active |
| Databricks model services | LLM-assisted analytical extraction/resolution | Confidential data requires explicit model/service approval | Implemented; runtime validation required |
| PyMuPDF | PDF text extraction | Local processing; output inherits source classification | Active |
| python-docx | DOCX text extraction | Local processing; output inherits source classification | Active |
| langdetect | Language detection | Local processing; no external SaaS transfer in current design | Active PoC |
| neo4j Python driver | Neo4j connectivity | Encrypted/authenticated connection; credentials from secrets only | Active |
| Databricks SDK | Job orchestration / Databricks API access | Least-privilege service identity; no hard-coded credentials | Active |
| EMCIP reference tables | Controlled taxonomy mapping | Classification layer; must not expose protected evidence | Active |
| MAIRA | Reusable document-processing components/reference | Reuse of code does not imply reuse of datasets/permissions | Separate / optional reuse |
| Old workspace App folder | Current deployment source | Transitional code copy only; do not use as evidence store | Transitional |

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


## 13. External assurance and organisational approval

The tool inventory records technical capability and project intent. It does not
constitute legal approval for processing confidential safety-investigation
material.

Before protected investigation data are introduced, the responsible
organisation should confirm, as applicable:

- information classification;
- GDPR role/lawful basis and DPIA need;
- Article 9 Directive 2009/18/EC confidentiality constraints;
- approved hosting/data region;
- vendor/controller/processor/subprocessor terms;
- model-service eligibility for the data class;
- access-control design;
- logging and monitoring;
- retention/deletion;
- backup handling;
- cross-border transfer implications;
- incident-response obligations.

Unknown items are treated as blockers for confidential-data use, not as
assumptions of acceptability.


## 14. Information-class model routing

The GUI does not expose arbitrary model choice to the normal investigator.
The information class selects the permitted model path:

| Class | Model / endpoint | Serving pattern |
|---|---|---|
| A | `system.ai.gpt-5-6-sol` | Databricks system.ai |
| B | `system.ai.gpt-5-6-sol` | Databricks system.ai |
| C | `system.ai.gpt-oss-120b` | Databricks-hosted open-weight |
| D | dedicated GPT-OSS 20B endpoint | custom/dedicated Databricks Model Serving |

Class D is fail-closed until `CLASS_D_MODEL_ENDPOINT` is configured and
approved. No fallback is permitted.

## 15. Explicitly excluded tool

**Lovable is not used by IKG.**

It is not part of:

- application runtime;
- source ingestion;
- evidence storage;
- model inference;
- graph persistence;
- deployment.

This avoids adding an unnecessary SaaS/data-processing boundary to the IKG
architecture.


## 16. Class D model resources

Required App/runtime resources:

- `class_d_analysis_job` — Lakeflow Job resource;
- `class_d_gpt20_endpoint` — dedicated GPT-OSS 20B serving endpoint;
- `class_d_llama70_endpoint` — dedicated Llama 3.3 70B serving endpoint;
- `direct_text_encryption_key` — encryption secret;
- `ikg_admin_users` — administrator identity list.

Runtime environment variables:

- `CLASS_D_ANALYSIS_JOB_ID`
- `CLASS_D_GPT20_ENDPOINT`
- `CLASS_D_LLAMA70_ENDPOINT`
- `DIRECT_TEXT_ENCRYPTION_KEY`
- `IKG_ADMIN_USERS`

Llama 3.3 70B is limited to five questions per user per day in the PoC.
The limit is persisted in Neo4j and only configured administrators can reset it.

See `docs/17_class_d_dual_model_poc.md`.


## 16. Product name and model-governance disclosure

**Working product name:** Safety Investigation Knowledge & AI Support

The knowledge graph is one internal analytical representation. It is not the
product identity.

The App must always disclose every LLM route currently available:

| Class | Model | Serving route | Confidentiality level | Article 9 processing suitability |
|---|---|---|---|---|
| A | OpenAI GPT-5.6 Sol | Databricks `system.ai.gpt-5-6-sol` | Public / non-sensitive | Not permitted for protected Class D evidence |
| B | OpenAI GPT-5.6 Sol | Databricks `system.ai.gpt-5-6-sol` | Published / non-sensitive | Not permitted for protected Class D evidence |
| C | OpenAI GPT-OSS 120B | Databricks-hosted `system.ai.gpt-oss-120b` | Internal / restricted | Not automatically approved for Article 9 evidence |
| D | OpenAI GPT-OSS 20B | Dedicated Databricks endpoint | Protected / confidential | Conditionally suitable after endpoint/governance approval |
| D | Meta Llama 3.3 70B Instruct | Dedicated Databricks endpoint | Protected / confidential | Conditionally suitable after endpoint/governance approval |

The Article 9 status is an internal processing-control classification, not a
legal certification of compliance.

For Class D, suitability requires confirmation of:

- authorised safety-investigation purpose;
- dedicated endpoint;
- access control;
- networking/data path;
- logging;
- retention;
- data location;
- organisational/legal/security approval;
- de-identification/privacy validation.

The system must fail closed when these conditions are not satisfied.
