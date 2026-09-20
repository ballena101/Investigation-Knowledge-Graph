# Data protection, confidentiality and information handling

## Purpose

This document defines the privacy, confidentiality and information-handling
principles for the Investigation Knowledge Graph (IKG) project.

It complements the technical architecture and tooling inventory. It does not
replace EMSA information-security rules, records-management rules, legal advice,
a data-protection impact assessment (DPIA), contractual review, or formal
authorisation to process a particular category of investigation material.

The project must apply the stricter rule whenever project convenience conflicts
with legal, contractual or organisational confidentiality requirements.

---

## 1. Legal and investigation confidentiality context

The IKG may process material originating from marine safety investigations.

Under Article 9 of the consolidated Directive 2009/18/EC, certain investigation
records are subject to specific confidentiality protection and are not to be
made available for purposes other than the safety investigation unless the
competent authority determines that the applicable public-interest test for
disclosure is met.

Protected categories include, among others:

- statements taken from persons by the safety investigation authority;
- records revealing the identity of persons who have given evidence;
- particularly sensitive or personal information, including health
  information;
- investigators' notes, drafts and opinions produced during the investigation;
- information/evidence supplied by investigators from other States where
  confidentiality is requested;
- draft interim, concise or final reports;
- communications between persons involved in operation of the ship;
- written/electronic VTS recordings and transcripts;
- VDR / S-VDR recordings, which are subject to additional restrictions.

The Directive expressly operates without prejudice to Regulation (EU) 2016/679
(GDPR).

Accordingly, the IKG must be designed on the assumption that source material can
contain:

- confidential investigation records;
- personal data;
- special-category personal data;
- commercially sensitive information;
- operationally sensitive information;
- information provided under restrictions from another authority or third
  country.

No source should be treated as safe for broad reuse merely because it is useful
to the analytical process.

---

## 2. Core data-protection principles

The system should implement the following principles as design constraints.

### 2.1 Purpose limitation

Investigation information must be processed only for an authorised analytical
or safety-investigation purpose.

The IKG must not silently repurpose confidential evidence for unrelated
research, demonstrations, training, model fine-tuning, publication or external
sharing.

### 2.2 Data minimisation

Only the information needed for the analytical purpose should be transferred
between system components.

Examples:

- GitHub should hold code/documentation, not investigation evidence;
- Neo4j should normally hold graph concepts, metadata and evidence references,
  not full raw witness/VDR material;
- the App should display only what the authorised user needs;
- LLM prompts should contain the minimum evidence passages required for the
  specific analytical task.

### 2.3 Least privilege

Every user, service principal, App resource and Job should have only the minimum
permissions required.

This applies separately to:

- source volumes;
- Delta tables;
- model services;
- Neo4j;
- Lakeflow Jobs;
- GitHub;
- App resources.

### 2.4 Integrity and traceability

Original evidence must not be overwritten by model output.

The project preserves:

```text
analysis
  → source document
      → page / source location
          → passage
              → candidate concept / relationship
                  → graph element
                      → human review
```

Original-language source text remains authoritative.

### 2.5 Confidentiality by default

A new source type or integration must be treated as confidential until its
information classification and permitted processing are known.

### 2.6 Security appropriate to risk

Where personal data are processed, technical and organisational measures must
be appropriate to the nature, scope, context, purpose and risk of processing.

---

## 3. Information classes for the PoC

The following operational classes should be used until superseded by an
official EMSA classification scheme.

### Class A — Code / public technical documentation

Examples:

- Python code;
- architecture diagrams;
- generic schemas;
- test instructions with no case data.

Permitted locations:

- GitHub;
- Databricks workspace;
- normal development tooling.

### Class B — Non-sensitive published investigation material

Examples:

- publicly released final investigation reports;
- published safety recommendations.

May be used in the PoC subject to normal access controls and copyright /
licensing requirements.

### Class C — Internal analytical derivatives

Examples:

- extracted passages from approved sources;
- candidate nodes;
- candidate relationships;
- internal mappings;
- model-generated summaries;
- human-review decisions.

Treat as internal unless explicitly approved for broader release.

### Class D — Confidential / protected investigation material

Examples:

- witness statements;
- identities of persons giving evidence;
- health or other sensitive personal information;
- investigators' notes/opinions;
- draft reports;
- operational communications;
- VTS recordings/transcripts;
- VDR / S-VDR material;
- restricted information supplied by another authority.

Class D material must not be introduced into the PoC merely because a technical
component is capable of processing it.

Its processing requires confirmation of:

- lawful/authorised purpose;
- permitted platform/location;
- access-control requirements;
- retention requirements;
- model-service eligibility;
- external-processor/subprocessor implications;
- transfer/data-residency requirements;
- deletion requirements;
- audit requirements.

---

## 4. Tool-by-tool confidentiality rules

### 4.1 GitHub

**Permitted role:** source code, configuration templates and documentation.

**Default rule:** do not store investigation evidence in GitHub.

Do not commit:

- source reports solely because they are convenient test fixtures;
- witness statements;
- VDR/VTS transcripts;
- personal data;
- confidential case material;
- passwords, tokens, connection strings or API keys;
- production database exports;
- raw model prompts/responses containing protected evidence.

Even a private repository is not a substitute for an authorised evidence store.

Repository visibility must be controlled. If confidential organisational code
is involved, the repository should be private/internal according to the
applicable organisational GitHub arrangement. A change to public visibility
must never be used as an informal publication mechanism.

Secrets must use an approved secret-management mechanism rather than source
files. If a credential is accidentally committed, removal from the latest file
is insufficient because Git history can retain it; the credential must be
revoked/rotated and repository history handled appropriately.

**IKG policy:** GitHub is the source of truth for code and documentation, not
the source of truth for investigation evidence.

---

### 4.2 Databricks Unity Catalog and UC Volumes

**Permitted role:** primary governed location for source documents and
analytical data.

Unity Catalog provides securable objects and fine-grained privileges for
catalogues, schemas, tables, volumes and model services.

For confidential material:

- access must be granted to named users/groups/service principals only where
  required;
- broad inherited access must be reviewed before loading protected material;
- source volumes and Delta tables must be treated independently from code
  access;
- least-privilege grants should be used;
- access should be auditable through the organisation's Databricks governance
  and audit facilities.

**Preferred IKG design:** raw evidence stays in governed Databricks storage.
Other components receive only the minimum necessary derivatives/references.

---

### 4.3 Delta Lake

**Permitted role:** governed persistence for evidence passages, provenance,
candidate analysis and reviewed analytical records.

Delta tables may contain confidential data depending on their content.

Requirements:

- preserve source provenance;
- do not overwrite original evidence with model-generated text;
- separate raw evidence, candidates and reviewed results;
- apply table/schema privileges according to sensitivity;
- avoid copying protected text into unnecessary tables;
- define retention/deletion rules before production use.

---

### 4.4 Databricks Apps

**Permitted role:** authorised investigator-facing interface.

The App must not become an uncontrolled distribution channel.

Requirements:

- authenticate users through the approved Databricks identity model;
- keep App/service-principal permissions minimal;
- avoid granting the App direct raw-volume access where not necessary;
- show only analysis content the current authorised workflow requires;
- do not place sensitive evidence in URLs, query strings or client-side state;
- avoid printing credentials or protected evidence to App logs;
- ensure error messages do not expose source content unnecessarily.

**Preferred architecture:** the App triggers a controlled Job and reads
authorised metadata/results; it does not independently browse the whole source
volume.

---

### 4.5 Databricks Lakeflow Jobs

**Permitted role:** controlled backend execution of extraction and analysis.

A Job runs using its configured identity and therefore its permissions are a
security boundary.

Requirements:

- define a dedicated Run-as identity appropriate for the environment;
- give the Job only the data/model permissions it needs;
- do not print full confidential source passages to notebook/job logs;
- logs should use identifiers/counters rather than protected text whenever
  possible;
- failures should report technical diagnostics without unnecessarily exposing
  source evidence;
- job parameters should carry identifiers such as `analysis_id`, not raw
  confidential documents or text.

---

### 4.6 Databricks model services / LLMs

**Permitted role:** evidence-grounded analytical assistance.

This is the component requiring the most explicit information-governance
decision before confidential investigation material is used.

Current generic pipeline uses governed model services exposed through
Databricks `system.ai`.

Before sending Class D material to any model service, the project must verify:

- that the specific service/model is approved for the data classification;
- applicable Databricks/model-provider contractual terms;
- processor/subprocessor arrangements;
- data location / cross-border transfer implications;
- retention and logging behaviour;
- whether prompts/responses can be used for service improvement or model
  training;
- access controls on the model service;
- whether sensitive identifiers should be removed/pseudonymised first.

A technical ability to call a model is **not** authorisation to send protected
investigation data to it.

**PoC safeguard:** use published/non-sensitive reports for model-pipeline
validation until the confidentiality assessment for protected material has
been completed.

The LLM must receive only the passages needed for the task, rather than an
entire evidence corpus where unnecessary.

Model output is analytical data, not evidence, and remains reviewable.

---

### 4.7 Neo4j AuraDB

**Permitted role:** graph projection, traversal and review metadata.

Neo4j Aura encrypts connections and data at rest, but encryption alone does not
determine whether a particular investigation dataset is authorised for storage
there.

**IKG default:** Neo4j should store:

- graph nodes;
- graph relationships;
- analysis IDs;
- source-document identifiers;
- evidence passage IDs/references;
- concise analytical descriptions where authorised;
- review decisions.

It should not automatically store:

- whole confidential reports;
- full witness statements;
- full VDR/VTS transcripts;
- unnecessary personal identifiers;
- special-category data.

Before Class D data or identifiable personal data are persisted in Aura,
confirm:

- contractual/processor status;
- hosting region and applicable data-residency requirement;
- approved account/tenant;
- user/service access;
- backup/retention/deletion behaviour;
- organisational approval.

---

### 4.8 Streamlit and streamlit-cytoscape

These are presentation/runtime libraries used inside the Databricks App.

They are not intended as separate evidence repositories.

Controls:

- do not embed secrets in UI elements;
- do not render protected evidence unless the user is authorised to see it;
- avoid exposing full evidence in graph labels/tooltips when a reference is
  sufficient;
- assume displayed data may be copied/screenshot by authorised users and apply
  the same disclosure rules as any other investigator interface.

---

### 4.9 PyMuPDF, python-docx and langdetect

These libraries execute as part of the controlled Databricks processing
environment.

They are used for:

- PDF extraction;
- DOCX extraction;
- language detection.

They do not require sending document content to a separate SaaS service in the
current design.

Nevertheless:

- extracted text inherits the confidentiality level of the source;
- temporary/intermediate data must be governed;
- extracted passages must not be written to uncontrolled local or external
  locations.

---

### 4.10 Databricks SDK and Neo4j Python driver

These are connectivity/orchestration libraries.

They must:

- obtain credentials from approved secret/resource mechanisms;
- never hard-code credentials;
- never log credentials;
- use encrypted connections;
- operate under least-privilege identities.

---

### 4.11 EMCIP reference tables

EMCIP taxonomy/reference data are used as a classification layer.

They must remain logically separate from source evidence.

An EMCIP mapping produced by the IKG:

- is an analytical mapping;
- is not proof that the source investigation authority assigned that code;
- must not reveal protected evidence merely to justify a classification where a
  controlled evidence reference is sufficient.

---

### 4.12 MAIRA

MAIRA is a separate project and possible source of reusable ingestion /
passaging components.

Reusing code does not automatically authorise reusing MAIRA datasets,
credentials, storage locations or access rights.

Data movement between MAIRA and IKG must be explicitly designed and governed.

---

## 5. Data movement map

The preferred confidentiality-preserving architecture is:

```text
SOURCE DOCUMENT
  governed UC Volume
        │
        │ authorised backend Job
        ▼
EXTRACTED EVIDENCE
  Delta / governed tables
        │
        ├──────────────► LLM model service
        │                only minimum required passages
        │                only if data classification permits
        │
        ▼
ANALYTICAL CANDIDATES
  Delta
        │
        ▼
GRAPH PROJECTION
  Neo4j
  references + authorised derivatives
        │
        ▼
DATABRICKS APP
  authorised user view / review
```

GitHub sits outside the evidence flow:

```text
GitHub
  code + documentation only
  NO raw investigation evidence
```

---

## 6. Personal data and sensitive personal data

The IKG may encounter names, contact details, employment information, voice or
communications data, health data and other information relating to identifiable
persons.

Where personal data are processed:

- identify the authorised purpose and lawful basis through the responsible
  organisation;
- minimise identifiers;
- pseudonymise/anonymise where compatible with the investigation purpose;
- restrict access;
- define retention;
- support correction/deletion/restriction obligations where applicable and
  compatible with the legal investigation framework;
- apply security appropriate to risk.

Health information and other special categories require heightened protection.

---

## 7. Logging and observability

Logs are a common accidental confidentiality channel.

The IKG must not routinely log:

- full passages;
- full prompts;
- witness identities;
- health information;
- VDR/VTS text;
- credentials;
- full source documents.

Preferred logs contain:

- analysis ID;
- document ID;
- passage ID;
- stage;
- counts;
- timing;
- model/version;
- success/failure;
- non-sensitive error codes.

Debug logging that includes source text must be disabled for normal operation
and separately authorised where ever required.

---

## 8. Model prompts and outputs

Prompts and model responses must be treated as data processing, not ephemeral
developer text.

For each analysis the system should be able to identify:

- model/service used;
- analysis version;
- source passage IDs submitted;
- output candidate IDs;
- processing timestamp;
- subsequent human review status.

Do not include unrelated passages merely to improve context.

Do not treat a model-generated statement as source evidence.

---

## 9. Retention and deletion

Before production use, retention rules must be agreed for:

- source documents;
- extracted text;
- passages;
- candidate results;
- model outputs;
- graph projections;
- human-review records;
- job/application logs;
- backups.

Deleting a graph node does not mean the source evidence or derivative copies
have been deleted from all systems.

Deletion must therefore be considered across the complete data lifecycle.

---

## 10. Environment separation

Production/confidential investigations should not be mixed casually with
development/demo material.

Target state should distinguish at least:

- development/test;
- controlled validation;
- production/operational.

Synthetic or published data should be preferred for development.

---

## 11. Tool admission rule

A new tool or external service must not be added to the IKG processing path
until the following are documented:

1. purpose;
2. data it receives;
3. data it stores;
4. hosting/location;
5. identity/access model;
6. encryption;
7. logging;
8. retention/deletion;
9. subprocessors/external providers where relevant;
10. whether personal/confidential investigation data are permitted;
11. responsible approval/owner.

If these are unknown, the tool is not approved for confidential data.

---

## 12. Current PoC confidentiality position

The present PoC should be treated as suitable for development and validation
using approved published/non-sensitive investigation material.

The technical architecture contains useful security controls, but it should not
be interpreted as blanket authorisation for confidential witness statements,
VDR/VTS material, health information, draft investigation material or other
Article 9-protected records.

Before such material is introduced, the relevant organisational/legal/security
assessment must confirm the permitted processing path for:

- Databricks storage;
- Databricks model services;
- Neo4j AuraDB;
- application access;
- retention;
- data residency/transfers;
- vendor/subprocessor arrangements.



## 13. In-App compliance and AI disclosure

The Databricks App must display a visible disclosure covering legal alignment,
information classification and AI/model use.

### 13.1 Directive conformity statement

The App must use the following status wording:

**PoC design-aligned / conditionally aligned — not a legal certification of
compliance.**

This wording is deliberate. The technical design implements safeguards intended
to support Article 9 of Directive 2009/18/EC, as amended by Directive (EU)
2024/3017, but legal conformity also depends on matters outside the software
itself, including:

- the legal purpose of each processing activity;
- the competent authority's disclosure/public-interest decisions;
- organisational information classification;
- user/service-principal permissions;
- approved storage and processing locations;
- model/service approval;
- processor/subprocessor and contractual terms;
- data retention/deletion;
- applicable GDPR obligations.

The App must therefore distinguish:

- **design alignment**: controls implemented in the software architecture;
- **conditional operational conformity**: possible only when the authorised
  organisational/legal processing path is confirmed;
- **legal certification**: not claimed by this PoC.

### 13.2 Article 9 safeguards reflected in the App

The App disclosure explains that the design supports Article 9 confidentiality
through:

- governed Databricks source storage;
- least-privilege access design;
- preservation of source provenance;
- separation of evidence from model-generated analysis;
- avoidance of direct raw-volume access by the App where not needed;
- graph references/authorised derivatives rather than unrestricted raw evidence
  replication;
- logging minimisation;
- prohibition on treating technical model access as permission to process
  protected investigation material.

### 13.3 Information classes shown to the user

The App displays four operational information classes:

- **Class A — Code / public technical documentation**
- **Class B — Published / non-sensitive investigation material**
- **Class C — Internal analytical derivatives**
- **Class D — Confidential / protected investigation material**

Class D includes, in particular, material corresponding to Article 9 protected
records such as witness statements, identities, sensitive/private information,
investigator notes/opinions, draft reports, operational communications, VTS
material and VDR/S-VDR material.

Class D is **not authorised for LLM processing by default**.

### 13.4 Exact model disclosure

The App must display the exact Databricks model-service identifier for every
analysis.

Current default:

`system.ai.gpt-5-6-sol`

The selected model service is:

1. selected/displayed in the App;
2. stored on the AnalysisGroup as `requested_model_service`;
3. passed as a Lakeflow Job parameter;
4. consumed by the analysis notebook;
5. recorded after execution as the effective `model_service`;
6. displayed again with the completed result.

This prevents a hidden model default from differing from what the investigator
believes was used.

### 13.5 Applicable AI/model policy

For the current default OpenAI GPT-5.6 Sol model service, the App states that
use is governed by:

1. the organisation's Databricks agreement;
2. Databricks Model Serving / Foundation Model API data-protection and
   retention terms;
3. Databricks' applicable model terms for OpenAI GPT-5.6 Sol;
4. OpenAI Usage Policy;
5. OpenAI high-risk use-case mitigation requirements.

Relevant Databricks references:

- https://docs.databricks.com/aws/en/machine-learning/model-serving
- https://docs.databricks.com/aws/en/machine-learning/foundation-model-apis/compliance
- https://docs.databricks.com/aws/en/machine-learning/model-serving/acceptable-use-models
- https://docs.databricks.com/aws/en/ai-gateway/model-services

Databricks documents that Model Serving requests are logically isolated,
authenticated and authorised, and encrypted in transit and at rest. For paid
accounts, Databricks states that inputs/outputs submitted to Model Serving are
not used to train models or improve Databricks services. Foundation Model APIs
may temporarily process/store inputs and outputs for abuse/security purposes,
subject to the documented retention conditions.

These platform assurances do **not** by themselves authorise Article 9
protected material for LLM processing. The Class D approval rule remains in
force.


## 14. Privacy-by-design analytical output policy

Privacy/confidentiality is a product mission, not only a disclaimer.

The IKG should actively reduce the exposure and propagation of protected
information throughout the analytical workflow.

### 14.1 Data exposure minimisation

The preferred processing pattern is:

```text
governed source evidence
        ↓
minimum necessary passage(s)
        ↓
authorised analytical processing
        ↓
de-identified analytical derivative
        ↓
graph / summary / review
```

The system should not send an entire report/evidence corpus to a model when a
smaller evidence set is sufficient.

### 14.2 De-identified output by default

Machine-generated analytical outputs should not reproduce personal identifiers
unless identity is strictly necessary for the authorised safety-analysis
purpose.

By default, summaries, findings, node labels, relationship descriptions and
other derivatives should omit or generalise:

- personal names;
- witness identities;
- email addresses;
- telephone numbers;
- home/private addresses;
- personal/national identifiers;
- dates of birth;
- medical/health details;
- other unnecessary personal or sensitive attributes.

People should normally be represented by functional role, for example:

- master;
- chief engineer;
- officer of the watch;
- crew member;
- passenger;
- witness;
- investigator;
- shore coordinator.

### 14.3 Re-identification risk

Removing a name alone is not sufficient.

Outputs should avoid unnecessarily combining details that could make a person
identifiable, such as a unique role, exact age, exact location, exact time and
sensitive circumstance.

### 14.4 Evidence remains unchanged

De-identification applies to analytical derivatives.

The authorised original evidence remains unchanged in governed storage and is
linked through provenance identifiers. This preserves evidential integrity while
reducing unnecessary propagation of protected content.

### 14.5 Current technical implementation

The generic LLM pipeline applies the mode:

`DE_IDENTIFIED_BY_DEFAULT`

Candidate extraction and cross-document resolution instructions explicitly
prohibit reproducing unnecessary personal names/identifiers and instruct the
model to use functional roles.

This is an important control but should not be treated as a complete automated
PII guarantee. Production use with protected records should add deterministic
or evaluated PII/identifier detection and output validation before publication
or wider access.

## 15. LLM provenance

The current default model chain is:

```text
OpenAI
  GPT-5.6 Sol
        ↓
Databricks
  system.ai.gpt-5-6-sol
  governed model service
        ↓
IKG Lakeflow analytical pipeline
        ↓
candidate extraction / resolution / synthesis
```

The underlying model provider is **OpenAI**.

The IKG does not call a personal ChatGPT session for analysis. The pipeline calls
the model through Databricks' governed model-service layer.

Databricks documents `system.ai.gpt-5-6-sol` as a ready-to-use model service
for OpenAI GPT-5.6 Sol.

Model availability through Databricks does not itself authorise confidential
Article 9 material for model processing. The Class D approval rule remains
applicable.


## 16. Model data-flow assurance levels

The IKG must distinguish model quality from model data-flow assurance.

### 16.1 Current GPT-5.6 Sol path

Current default:

`system.ai.gpt-5-6-sol`

On Azure Databricks, OpenAI models are exposed through **ADI Services** provided
by Databricks.

Databricks documents that:

- Model Serving requests are logically isolated, authenticated and authorised;
- data are encrypted in transit and at rest;
- paid-account inputs/outputs are not used to train models or improve
  Databricks services;
- Foundation Model API inputs/outputs may be temporarily processed/stored by
  Databricks for abuse/security purposes for up to 30 days in the same region;
- partner model providers may retain data for safety purposes in some cases;
- OpenAI-specific retention conditions may apply to certain customer/use
  categories and future models.

Therefore the IKG must **not** state that prompts or outputs are guaranteed to
remain exclusively inside Databricks or are guaranteed never to be available to
OpenAI/provider safety systems.

The correct project position is:

**The current GPT-5.6 Sol path is governed by Databricks and protected by
Databricks Model Serving controls, but it is not treated as a zero-retention /
zero-provider-exposure path.**

### 16.2 Recommended assurance tiers

#### Tier 1 — Published / non-sensitive material

Permitted model path:

- Databricks Foundation Model APIs / ADI model services such as GPT-5.6 Sol,
  subject to normal organisational approval.

Suitable for:

- Class B published reports;
- development;
- benchmarking;
- non-sensitive analytical experiments.

#### Tier 2 — Internal analytical derivatives

Preferred model path:

- Databricks-hosted/open-weight model with no external-provider routing;
- provisioned throughput or custom Model Serving where operationally justified;
- request/response logging disabled unless explicitly required.

Suitable for:

- Class C internal analytical derivatives,
  subject to organisational approval.

#### Tier 3 — Confidential / Article 9 protected material

Preferred model path:

- a model deployed as a **custom or dedicated Databricks Model Serving
  endpoint** using an approved open-weight model;
- no external model-provider service;
- no web search/tools that send prompt-derived queries externally;
- Private Link / private networking where required;
- explicit logging/retention configuration;
- strict Unity Catalog access;
- deterministic privacy/output validation before wider display.

Class D should not use GPT-5.6 Sol or another partner-origin Foundation Model API
merely because the endpoint is available.

The final operational choice must be approved by the responsible EMSA
security/data-protection/legal governance function.

### 16.3 Candidate lower-provider-exposure models

Azure Databricks supports open-weight / Databricks-hosted model families such as:

- Meta Llama 3.3 70B Instruct;
- Meta Llama 4 Maverick;
- OpenAI GPT-OSS 120B / 20B;
- other approved custom Hugging Face/MLflow models.

For the highest confidentiality requirement, the preferred architecture is not
simply selecting another pay-per-token Foundation Model API. It is deploying an
approved open-weight model as a dedicated/custom Model Serving endpoint under
the organisation's Databricks controls.

### 16.4 Important distinction

A model can be:

- developed by OpenAI/Meta/etc.;
- hosted by Databricks;
- or called as an external provider.

These are different concepts.

**Model developer** does not by itself determine where inference data flows.

The IKG must document for every model:

1. model developer;
2. serving host;
3. whether an external provider is contacted at inference time;
4. retention policy;
5. safety-monitoring policy;
6. data residency;
7. logging;
8. approved information class.

If any of these are unknown, the model is not approved for Class D data.


## 17. Direct-text ingress

The App supports direct user-authored/pasted source text for Classes A, B and C.

Privacy behaviour:

1. raw text is temporarily stored as a `DirectTextSource`;
2. a SHA-256 hash is recorded;
3. the extraction Job converts it to governed Delta passages;
4. after successful persistence, the raw `text_content` property is removed
   from Neo4j;
5. only metadata/provenance remain.

This is a minimisation mechanism, not permission to paste protected evidence.

Class D direct-text input is blocked until a secure direct-to-governed-storage
ingress is implemented. Protected text must currently use the governed document
route.

## 18. Model policy enforcement

The App enforces model routing from the information class rather than relying
on the user to understand provider/security differences.

- A/B → GPT-5.6 Sol via Databricks;
- C → Databricks-hosted GPT-OSS 120B;
- D → dedicated GPT-OSS 20B endpoint.

Class D fails closed when the dedicated endpoint is not configured.

## 19. Privacy-validation gate

Before graph publication, analytical derivatives enter
`PRIVACY_VALIDATION`.

The current deterministic validator redacts:

- email-address patterns;
- telephone-number patterns;
- explicitly labelled personal-ID patterns.

The resulting analysis records the privacy mode, validation status and number of
automatic redactions.

This complements LLM de-identification instructions. It is not yet a complete
PII/NER guarantee; production hardening must evaluate and extend it.


## 20. Current Class D dual-model confidentiality policy

This section supersedes earlier single-model Class D descriptions.

The current Class D PoC supports:

- dedicated GPT-OSS 20B;
- dedicated Meta Llama 3.3 70B;
- either model independently;
- both models on the same evidence/question.

Both routes are intended to use dedicated/custom Databricks Model Serving
endpoints approved for Class D processing.

No fallback to GPT-5.6 Sol, GPT-OSS 120B or another provider route is allowed.

### Direct text

Class D direct text is encrypted in the App using a secret-managed Fernet key
before temporary storage.

The backend Job decrypts the payload, creates governed Delta passages and then
removes the encrypted payload from Neo4j.

Raw Class D text is not transported as a Job parameter.

### Llama resource control

Llama 3.3 70B is limited to five questions per user per day in the PoC.

This is a cost/resource-control mechanism, not a confidentiality control.

Only configured App administrators can reset a user's daily counter.

### Independent model outputs

When both models are used, outputs remain separate:

- independent summary;
- independent findings;
- independent graph;
- independent privacy-validation result;
- independent human review.

The models do not receive each other's outputs before comparison.


## 20. Directive 2009/18/EC Article 9 — final control mapping

This section is the definitive legal-design cross-reference for the current
PoC.

Directive (EU) 2024/3017 replaced Article 9 of Directive 2009/18/EC. The
current Article 9 protects the following from use/disclosure for purposes other
than the safety investigation unless the competent authority makes the required
overriding-public-interest determination:

1. statements taken from persons by the safety investigation authority;
2. records revealing the identity of persons who gave evidence;
3. particularly sensitive/personal information, including health information;
4. investigator-generated notes, drafts, opinions and opinions expressed in
   analysis;
5. information/evidence from other Member States or third countries where the
   supplying authority requests confidentiality;
6. draft interim, concise or final reports;
7. communications between persons involved in ship operation;
8. VTS written/electronic recordings and transcripts, including internal
   reports/results.

Article 9(2) separately restricts VDR/S-VDR recordings. Article 9(3) requires
that only strictly necessary data be disclosed. The Article operates without
prejudice to GDPR.

### Technical consequence for IKG

The IKG treats these categories as Class D unless a formally approved
classification says otherwise.

The default Class D data path is:

```text
authorised governed source storage
        ↓
minimum necessary evidence passage
        ↓
approved dedicated model endpoint
        ↓
de-identified analytical derivative
        ↓
privacy validation
        ↓
Neo4j graph references / authorised derivatives
        ↓
authorised App view + human review
```

### Neo4j rule for Class D

Neo4j is not the authoritative raw evidence store.

Default allowed Class D content in Neo4j:

- IDs;
- hashes;
- processing status;
- model-run metadata;
- evidence-reference IDs;
- de-identified graph concepts;
- graph relationships;
- review/audit metadata;
- privacy-validation metadata.

Default prohibited raw replication:

- complete protected documents;
- complete witness statements;
- raw witness identities;
- unnecessary health/sensitive personal data;
- investigator draft material;
- raw operational communications;
- raw/full VTS transcripts;
- raw/full VDR/S-VDR material.

Where an analytical description could itself reveal a protected person, use a
functional role and retain the evidence link separately.

### Aura-specific governance

Neo4j Aura documents encryption in transit and at rest and encrypted snapshots.
Backups/snapshots remain copies of the stored data. Consequently, putting raw
Class D evidence into Aura would also extend that evidence into Aura's snapshot
lifecycle. This is an additional reason for the IKG rule that raw Class D
documents and full protected evidence are not normal Neo4j graph payloads.

Any exception requires explicit organisational approval of:

- Aura tenant/tier;
- hosting region;
- identities and access;
- backup/snapshot lifecycle;
- retention/deletion;
- contractual processor/subprocessor status;
- incident handling.

## 21. A/B/C versus D

The confidentiality controls do not remove the A/B/C workflows.

- **A:** public/technical → default GPT-5.6 Sol.
- **B:** published/non-sensitive investigation material → default GPT-5.6 Sol.
- **C:** internal/restricted but not Article 9 protected → default
  Databricks-hosted GPT-OSS 120B.
- **D:** Article 9/protected → dedicated GPT-OSS 20B and/or Llama 3.3 70B,
  with the additional controls documented above.

Only D adds:

- dual-model choice;
- Llama quota;
- side-by-side comparison;
- stricter ingress/storage rules;
- dedicated endpoints;
- mandatory protected-data/privacy checks.
