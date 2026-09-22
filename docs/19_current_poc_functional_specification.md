# Safety Investigation Knowledge & AI Support — Authoritative PoC specification

## 0. Product identity and purpose

**Working product name:** Safety Investigation Knowledge & AI Support

The PoC evaluates supporting artificial-intelligence and structured-knowledge
tools for safety investigation. Its purpose is to help investigators analyse
evidence, structure knowledge, compare model outputs, preserve provenance and
review machine-generated candidates.

The knowledge graph is an internal representation, not the product identity.

The PoC does not replace the investigator, establish blame or liability, or
convert model output directly into a formal investigation finding.

The product mission includes confidentiality-by-design: route information
according to its classification, minimise model exposure, de-identify
analytical derivatives by default, preserve original evidence separately and
fail closed when a protected-data model route is not approved.

## 1. Product scope

The Investigation Knowledge Graph (IKG) PoC is a generic investigation-analysis
application. It is not a Commodore Clipper application.

The application PoC supports **all information classes A–D**. The current
experimental comparison/validation focus is the **additional Class D
dual-model workflow** for protected or confidential investigation material.
Class D does not replace or supersede the normal A/B/C routes.

Commodore Clipper is retained only as:

- a controlled methodology reference;
- a first candidate benchmark case;
- an example of human-reviewed evidence-grounded graph structure.

## 2. Supported information classes

The application continues to support **all four information classes**. The
Class D dual-model logic is an additional protected-data route; it does not
replace A/B/C.

| Class | Typical content | Default model route | Extra Class-D controls? |
|---|---|---|---|
| A | Public / technical material | `system.ai.meta-llama-3-3-70b-instruct` | No |
| B | Published / non-sensitive investigation material | `system.ai.meta-llama-3-3-70b-instruct` | No |
| C | Internal / restricted analytical material that is not Article 9 protected evidence | `system.ai.gpt-oss-120b` | No |
| D | Article 9 / protected confidential investigation material | Dedicated GPT-OSS 20B and/or Llama 3.3 70B endpoints | Yes |

For A/B/C, the user chooses documents or direct text, enters the question /
objective, and the App uses the class-default model automatically.

For D only, the user additionally chooses:

- GPT-OSS 20B;
- Llama 3.3 70B Instruct;
- both models.

The Llama quota and side-by-side comparison logic apply **only to Class D**.

## 2A. A/B/C remain first-class supported routes

The GUI must always display A, B, C and D. It must not present Class D as the
only supported analysis type.

Normal routing is:

```text
A → Meta Llama 3.3 70B Instruct
B → Meta Llama 3.3 70B Instruct
C → GPT-OSS 120B
D → GPT-OSS 20B / Llama 3.3 70B / Both
```

The model is selected by information-class policy rather than by arbitrary
user choice, except for the Class D comparison choice.

## 2B. Investigator workflow

For Class D, the investigator:

1. chooses the source mode:
   - 1–5 governed documents; or
   - direct text;
2. writes the investigation question/objective;
3. chooses the model execution:
   - GPT-OSS 20B;
   - Llama 3.3 70B Instruct;
   - both;
4. submits the analysis;
5. follows visible processing status;
6. reviews the resulting summary and graph;
7. when both models are selected, compares independent outputs side by side;
8. validates/rejects/amends graph relationships.

The two models must receive the same evidence passages and the same question.
Neither model sees the other model's output before the comparison is shown.

## 3. Why the second model is called Llama, not Ollama

**Ollama is a model runtime/serving tool, not the model itself.**

The larger open-weight model selected for the PoC comparison is:

**Meta Llama 3.3 70B Instruct**

It is commonly usable through Ollama in local environments. In this IKG
Databricks architecture, however, the Class D comparison should use an approved
dedicated Databricks serving route rather than introducing an Ollama server as
another data-processing boundary.

This distinction must remain explicit in the GUI and documentation:

- model: Llama 3.3 70B Instruct;
- runtime/serving for IKG: approved Databricks endpoint;
- Ollama: not an IKG production dependency.

## 4. Class D model routes

Environment identifiers:

- `CLASS_D_GPT20_ENDPOINT`
- `CLASS_D_LLAMA70_ENDPOINT`

Requested endpoints fail closed. There is no fallback to Class A/B/C models.

The exact endpoint/model identifier is persisted with every ModelRun.

Databricks currently documents both GPT-OSS 20B and Meta Llama 3.3 70B
Instruct among supported foundation/open-weight model families, subject to
workspace/region availability.

## 5. Side-by-side comparison

If **Both models** is selected:

```text
same evidence passages + same question
             │
      ┌──────┴──────┐
      ↓             ↓
 GPT-OSS 20B   Llama 3.3 70B
      ↓             ↓
 independent    independent
 summary/graph  summary/graph
      └──────┬──────┘
             ↓
 side-by-side investigator view
```

Each side must show:

- model/endpoint;
- run status;
- summary;
- findings;
- uncertainties;
- source conflicts;
- privacy-validation status;
- graph node/relationship counts;
- interactive graph;
- evidence provenance.

No automatic merged "winner" is produced.

## 6. Llama question quota

The larger Llama route has a PoC resource-control quota.

Default:

**5 Llama questions per user per calendar day**

Timezone:

`Europe/Lisbon`

Rules:

- Llama-only run = 1 Llama question;
- Both-model run = 1 Llama question;
- GPT-OSS 20B-only run = 0 Llama questions;
- at the limit, Llama and Both are blocked until the next day;
- the remaining count is visible before submission;
- only an identity listed in `IKG_ADMIN_USERS` may reset a counter;
- an administrator may reset today's counter for a specified user;
- resets are auditable with reset timestamp and admin identity.

Configuration:

`LLAMA_DAILY_QUESTION_LIMIT=5`

The value can later be changed to 10 without changing application code.

This is a PoC compute/cost control, not a model-safety rule.

## 7. Class D direct text

Direct text is encrypted in the App before temporary persistence.

```text
raw text
  ↓
Fernet encryption
  ↓
temporary encrypted DirectTextSource
  ↓
backend decryption
  ↓
governed Delta passages
  ↓
encrypted temporary payload purged
```

The encryption key is supplied through the approved secret:

`DIRECT_TEXT_ENCRYPTION_KEY`

Raw text must not be passed as a Lakeflow Job parameter.

## 7A. Class D source-document handling and Neo4j boundary

For Class D, the raw evidence store and the graph store have different roles.

### Raw Class D documents

Raw Class D documents must remain in the approved governed Databricks /
Unity Catalog source location. They must **not** be copied into Neo4j merely
to make graph processing convenient.

Neo4j may receive only the minimum necessary metadata and analytical
derivatives, such as:

- analysis ID;
- source-document ID;
- content hash;
- controlled source reference / governed path reference where authorised;
- passage IDs rather than complete protected passage text where possible;
- model-run metadata;
- de-identified node labels/descriptions;
- evidence-reference IDs;
- graph relationships;
- human-review records;
- privacy-validation metadata.

Neo4j must not be used by default to persist:

- whole Class D source documents;
- full witness statements;
- identities of persons giving evidence;
- health or other particularly sensitive personal information;
- investigators' notes, drafts or opinions;
- draft investigation reports;
- full ship-operation communications;
- full VTS recordings/transcripts;
- VDR/S-VDR recordings or transcripts;
- secrets/credentials.

This implements the project's minimisation rule and supports Article 9(3),
which requires disclosure of only data that are strictly necessary.

### VDR / S-VDR

Article 9(2) receives separate treatment. VDR and S-VDR recordings must not be
made available or used outside the safety-investigation / ship-safety purposes
except under the conditions laid down in the Directive, including anonymisation
or secure procedures.

For the IKG, VDR/S-VDR raw material is therefore never a normal Neo4j payload.

### Direct text classified D

Direct text classified D is a special ingress problem because the App does not
currently have direct governed-volume write access.

The PoC currently encrypts direct text before temporary persistence and purges
the encrypted payload after governed passages are created. This is **not**
treated as blanket production approval for Article 9 material in Neo4j.

Before operational Class D direct-text use, one of the following must be
approved:

1. secure direct-to-governed-Databricks ingress; or
2. an explicit organisational/security approval for the encrypted transient
   Neo4j ingress, including region, access, backup/snapshot, retention and
   deletion behaviour.

Until that approval exists, Class D direct text is a controlled PoC capability,
not an authorised production evidence-ingress mechanism.

## 8. Evidence and graph pipeline

```text
source documents / direct text
        ↓
deterministic evidence passages + provenance
        ↓
same question + same evidence
        ↓
independent model extraction
        ↓
candidate nodes / relationships
        ↓
cross-passage resolution
        ↓
privacy validation
        ↓
model-specific knowledge graph
        ↓
human review
```

Relationship semantics remain controlled:

- FOLLOWED_BY;
- RESULTED_IN;
- CONTRIBUTED_TO;
- AFFECTED;
- SUPPORTS;
- structural relationships where applicable.

Chronology must never be promoted to causality without evidence.

## 9. Model validation — what is and is not validated

### Already validated

The Commodore Clipper reference work validates parts of the **methodology**:

- evidence-linked graph representation;
- relationship semantics;
- separation of chronology and causality;
- reviewed relationship decisions;
- reviewed EMCIP mappings;
- review provenance.

It does **not** validate GPT-OSS 20B or Llama 3.3 70B performance.

### Model validation still to execute

Both models must be tested on the same locked benchmark items.

Core metrics:

1. **Evidence grounding**
   - evidence-supported relationship rate;
   - unsupported relationship rate;
   - provenance/citation accuracy.

2. **Relationship correctness**
   - human VALIDATED / REJECTED / AMENDED;
   - precision by relationship type.

3. **Causal overreach**
   - unsupported RESULTED_IN / CONTRIBUTED_TO false-positive rate.
   - target principle: zero unsupported causal promotion.

4. **Graph completeness**
   - node precision/recall;
   - relationship precision/recall;
   - missed concepts;
   - duplicate-resolution errors.

5. **Privacy**
   - identifier leakage;
   - sensitive-information leakage;
   - automatic-redaction count;
   - human privacy-review failures.

6. **Stability**
   - repeated-run graph consistency;
   - relationship consistency;
   - evidence-reference consistency.

7. **Human effort**
   - amendments/rejections required;
   - review time where measurable.

8. **Dual-model disagreement**
   - common concepts/relationships;
   - model-unique outputs;
   - conflicting outputs.

Model validation must record model/version, endpoint, prompt/pipeline version,
question, evidence version, privacy mode, benchmark version and review version.

## 10. Can validated graph review improve the model?

Yes. Human validation is valuable model feedback, but it must be used in a
controlled way.

### A. Evaluation ground truth — first priority

Validated/rejected/amended graph relationships become expected benchmark
outputs.

This measures the model without changing it.

### B. Retrieval context

Validated knowledge can be retrieved at inference time to provide:

- relationship definitions;
- reviewed examples;
- taxonomy mappings;
- previously validated investigation patterns.

Important: prior graph knowledge is **context**, not evidence that the same
relationship exists in the current investigation.

### C. Few-shot examples

Reviewed graph examples can teach the model:

- correct causal/contributory distinctions;
- evidence-grounding format;
- rejected causal-overreach examples;
- de-identification expectations.

### D. Versioned feedback dataset

Every human review can become a structured feedback example:

```text
question + evidence
      ↓
model candidate
      ↓
VALIDATED / REJECTED / AMENDED
      ↓
versioned feedback record
```

This can support evaluation, retrieval and later adaptation.

### E. Fine-tuning — later, optional

Fine-tuning should not be the first feedback mechanism.

It requires enough representative approved examples, train/test separation,
confidentiality/legal review, model-licence review and reproducible versioning.

## 11. Avoid circular validation

A reviewed case cannot simultaneously be:

- a prompt/training example; and
- an independent test case

for the same model/version evaluation.

Maintain explicit:

- training/example set;
- development set;
- locked validation/test set.

If Commodore Clipper is used as a few-shot teaching example, it must be removed
from the locked test set for that evaluation.

## 12. Persistence of human feedback

Human review must remain append-only and preserve:

- analysis_id;
- model_run_id;
- model/version;
- node/edge ID;
- original model output;
- decision;
- amended value when applicable;
- reviewer;
- timestamp;
- comment;
- evidence passage IDs;
- prompt/pipeline version.

The original model output is not overwritten.

## 13. Current implementation status

Implemented in repository:

- documents/direct-text Class D inputs;
- required investigation question;
- GPT-OSS 20B / Llama 3.3 70B / Both selection;
- encrypted direct-text ingress;
- independent model-run namespaces;
- side-by-side rendering;
- configurable Llama daily quota, default 5;
- administrator-only quota reset;
- privacy validation;
- evidence-grounded graph pipeline;
- human-review methodology;
- model-validation specification.

Still requiring environment execution:

- deploy/approve both Class D endpoints;
- attach/configure the Class D Lakeflow Job;
- configure secrets/App resources;
- validate networking/logging/retention;
- execute the locked benchmark;
- generalise the existing human-review UI from the reference graph to every
  model-run graph;
- persist model-run feedback as the formal benchmark/learning dataset.

## 14. Documentation hierarchy

For the current PoC, read in this order:

1. **This document** — authoritative functional specification.
2. `docs/18_model_validation_and_feedback.md` — validation and learning loop.
3. `docs/15_data_protection_confidentiality.md` — privacy/confidentiality.
4. `docs/13_automated_analysis_orchestration.md` — processing orchestration.
5. `docs/02_methodology.md` — graph/evidence semantics.
6. `docs/09_commodore_clipper_case.md` — reference case only.

The Commodore Clipper document is deliberately subordinate to the generic PoC
specification.


## 15. Article 9 confidentiality checklist

The IKG design maps the amended Article 9 confidentiality rules to technical
controls as follows.

| Article 9 protected category / rule | IKG handling rule |
|---|---|
| Statements taken from persons | Keep in governed source storage; do not duplicate raw statements into graph storage |
| Identity of persons giving evidence | De-identify analytical outputs by default; role labels preferred |
| Particularly sensitive/personal information, including health | Minimise model exposure; do not propagate into graph/results unless strictly necessary and authorised |
| Investigator notes, drafts and opinions | Governed source only; distinguish source material from model synthesis |
| Evidence supplied by other States/third countries where confidentiality is requested | Preserve source restriction metadata; no broader reuse solely because technically accessible |
| Draft interim/concise/final reports | Treat as Class D unless formally released/authorised otherwise |
| Communications between persons involved in ship operation | Governed source; passage-level minimum exposure; avoid raw replication to Neo4j |
| VTS recordings/transcripts | Governed source; no default raw graph storage |
| VDR/S-VDR recordings | Special Article 9(2) rule; no normal Neo4j raw payload; anonymised/secure handling only where permitted |
| Article 9(3): only strictly necessary data disclosed | Data minimisation across LLM prompts, graph properties and UI |
| GDPR remains applicable | Separate personal-data governance, least privilege, retention and special-category safeguards |

The software does not itself make the legal determination that an overriding
public interest justifies disclosure. That remains a competent-authority
decision outside the model.

## 16. Final PoC privacy boundary

The PoC must fail closed where the required protected-data path is not
configured or approved.

In particular:

- D never falls back to A/B/C models;
- raw D documents remain only in governed **ephemeral** source storage and are
  deleted with their source-ingress storage within a maximum of 24 hours;
- Neo4j is a graph/metadata/review layer, not the authoritative D evidence
  repository;
- D outputs are de-identified by default;
- privacy validation runs before publication/display;
- exact model endpoint, pipeline version and evidence references are retained;
- user-visible output never silently replaces original evidence;
- human review does not cause the model to self-train automatically.


## 17. Class D source retention — 24-hour maximum

The Class D source-ingress layer is ephemeral.

Functional requirement:

**All raw Class D source documents and their dedicated source-ingress storage
must be deleted no later than 24 hours after ingestion.**

Required metadata:

- `ingested_at`;
- `expires_at`;
- `purge_status`;
- `purged_at`.

Required behaviour:

1. calculate expiry at ingestion;
2. expose retention/expiry status to the processing layer;
3. purge automatically before or at the 24-hour deadline;
4. do not extend retention because analysis/review is unfinished;
5. record purge success/failure;
6. alert/fail operationally if deletion cannot be confirmed.

The preferred implementation is analysis-specific ephemeral storage so that
deletion can be deterministic without affecting newer analyses.

This requirement applies to the **raw source-ingress layer**. Delta passages,
model outputs, Neo4j derivatives, review records, logs and backups require
separate retention rules and are not automatically erased by deleting the
source volume.

The Class D user disclosure must state this distinction explicitly.


## 18. Derived analytical retention — 72 hours

The PoC keeps derived/digested analytical artefacts for **72 hours by default**.

This covers:

- extracted passages;
- model candidates;
- candidate relationships;
- model summaries;
- uncertainties and source-conflict lists;
- generated graph nodes/relationships;
- other transient analytical derivatives.

The purpose of the 72-hour window is to allow:

- investigator inspection;
- side-by-side model comparison;
- short-term troubleshooting;
- human review initiation;

without accumulating unnecessary protected analytical material.

At analysis creation the App sets:

`retention_policy = TRANSIENT_72H`

and calculates:

`derived_expires_at = created_at + 72 hours`

The App displays the expiry.

### Validation exception

An analysis may be explicitly marked:

`retain_for_validation = true`

only when it is deliberately selected for the benchmark / model-validation
dataset.

Such cases are excluded from the automatic 72-hour purge.

Retention for validation must therefore be intentional rather than the default.

### Separation from raw source retention

The retention hierarchy is:

```text
raw direct-text buffer
→ purge immediately after successful extraction

raw Class D source ingress
→ maximum 24 hours

derived/digested analytical data
→ 72 hours

explicit benchmark / validated record
→ retained only by deliberate validation decision
```

### Cleanup implementation

- `23_purge_expired_analysis_artifacts.py`
- `24_create_retention_cleanup_job.py`

The cleanup Job runs hourly and removes expired derived content shortly after
the 72-hour boundary.

The cleanup preserves compact audit metadata but not substantive evidence or
model-generated analytical content.


## Workspace-validated model routing — 2026-09-21

Runtime validation in the active Azure Databricks workspace established that
`system.ai.meta-llama-3-3-70b-instruct`, `system.ai.gpt-oss-120b`, and
`system.ai.gpt-oss-20b` are reachable through the Unity Gateway model API,
while `system.ai.meta-llama-3-3-70b-instruct` is not available in this workspace.

For the current PoC:
- Classes A/B use `system.ai.meta-llama-3-3-70b-instruct`.
- Class C remains on `system.ai.gpt-oss-120b`.
- Class D retains the dedicated controlled model routes.
- `system.ai.*` services are invoked through the Unity Gateway OpenAI-compatible
  API; dedicated custom endpoints continue to use their endpoint-specific route.

This is a workspace-availability decision, not a quality ranking of models.


## 17. Reference-framework separation and remaining implementation

The generic analysis pipeline must keep three layers distinct:

1. **Occurrence evidence** — the documents/direct text being investigated.
2. **Methodological/legal reference context** — Directive 2009/18/EC as amended
   by Directive (EU) 2024/3017, the IMO Casualty Investigation Code
   (MSC.255(84), current applicable version) and IMO Guidelines A.1075(28).
3. **Controlled taxonomies** — EMCIP analytical taxonomy and, later, SHIELD for
   human-validated contributing factors.

Reference material must never be presented to the model as if it were evidence
about the occurrence.

Current implementation status:
- generic evidence/relationship extraction is implemented;
- privacy validation and graph publication are implemented;
- information class is user-declared; automatic Class-D pre-screening is not
  yet implemented;
- generic EMCIP mapping for newly generated graphs is not yet implemented;
- the current generic LLM prompt does not yet retrieve Directive/IMO/EMCIP
  reference context;
- relationship-review and EMCIP-mapping-review UIs are currently tied to the
  controlled Commodore Clipper reference graph and must be generalised to each
  generated analysis graph;
- SHIELD classification remains subsequent to human validation of a
  contributing factor. The LLM may then suggest a SHIELD mapping, which must
  receive its own human VALIDATE / AMEND / REJECT decision.

Recommended Class-D safeguard:
- retain explicit investigator classification;
- add an automatic pre-flight detector for obvious protected-data indicators;
- if A/B/C is selected but Class-D indicators are detected, fail closed and
  require explicit reclassification/authorised handling rather than silently
  sending the material through the less-protected route;
- the detector is a processing safeguard, not a legal determination.

App navigation order:
1. Home
2. New analysis
3. Analyses
4. Relationship review
5. EMCIP mapping review
6. Reference graph
7. Terms of reference

The reference graph is deliberately placed immediately before Terms of
reference because it is a methodology demonstrator rather than the primary
operational workflow.


## 18. Canonical upstream integration

For investigation documents, the generic PoC must converge on MAIRA as the
canonical evidence layer. The detailed integration contract and ordered
implementation plan are defined in:

`docs/23_maira_bosuil_integration_plan.md`

This supersedes any implication that IKF should maintain an independent
document chunking, EMCIP registry, governed query or deterministic relationship
assessment stack in parallel with MAIRA.

Bosuil is an external design reference only; it is not an IKF dependency.


## 2C. Classification-driven document catalogue

Document selection follows information classification and source ownership.

For document-based analyses:

| Information class | Document catalogue shown |
|---|---|
| A — Public / technical | IKF-managed document library |
| B — Published investigation material | MAIRA investigation-document catalogue only |
| C — Internal / restricted | IKF-managed document library |
| D — Protected / confidential | IKF-managed document library |

Rationale:

- MAIRA is the canonical repository for saved published investigation reports
  and associated investigation-package documents.
- IKF holds the remaining project documentation, including technical material,
  and is the controlled path for internal/protected inputs.
- The App must not present MAIRA's published investigation corpus as if it were
  the source repository for Class C or D.
- Direct text remains available independently of the document catalogue and is
  handled according to the selected information class.

The selector therefore changes its available document set immediately after the
user changes the information classification.

The App must also explain the active catalogue scope to the user, for example:

```text
Class B → MAIRA published investigation material
Class A/C/D → IKF document library
```

This routing is implemented in code but remains pending runtime/deployment
validation in the next scheduled App test.
