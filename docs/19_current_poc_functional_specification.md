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

## 6. Class D model question quotas

The PoC uses separate per-user, per-calendar-day cost-control counters for
Class D GPT-OSS 20B and Llama 3.3 70B. Both invoke paid cloud endpoints;
these application limits are not provider-imposed limits or model-safety rules.

| Selection | GPT-OSS 20B counter | Llama 3.3 70B counter |
| --- | ---: | ---: |
| GPT-OSS 20B | 1 | 0 |
| Llama 3.3 70B | 0 | 1 |
| Both | 1 | 1 |

The default limits are **30 GPT-OSS 20B** and **10 Llama 3.3 70B**
questions per user per calendar day, in `Europe/Lisbon`.
The App displays remaining counts, blocks a selection if either selected
counter is exhausted, and reserves Both counters in one Neo4j transaction.
Only identities listed in `IKG_ADMIN_USERS` can reset the current day's
counter for a selected user and model; reset timestamp and admin identity
remain auditable.

Configuration: `GPT20_DAILY_QUESTION_LIMIT=30` and
`LLAMA_DAILY_QUESTION_LIMIT=10`. The Databricks App `app.yaml`
sets both explicitly. A Class D analysis and a Class D Ask/graph question
each reserve quota when queued; retrying a failed job may require an
administrator review/reset of the reservation. Counters do not meter tokens,
audio GPU processing, or other cloud costs.

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
- separate configurable Class D model quotas, GPT-OSS 30 and Llama 10;
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


## 2D. Separate document analysis from investigator questions

The App separates evidence preparation/analysis from later investigator
questions.

### Analyse Documents

Purpose:
- choose information classification;
- select the governed source documents or direct text;
- create the evidence passages;
- extract question-independent concepts/relationships;
- build the candidate knowledge structure and graph.

The document-analysis stage must **not** be optimised around one user question.

New analyses therefore use:
- analysis title;
- optional analysis description;
- no analysis-time question/objective.

The description is metadata only and must not steer evidence extraction.

### Ask / Compare LLMs

Questions belong to a separate capability after an evidence set has been
processed.

Target question scopes:
1. whole case / analysis;
2. one source document;
3. selected source documents.

The investigator enters free text, for example:

`What factors contributed to the contact with the quay?`

The answer must:
- be grounded only in the selected evidence scope;
- show report/document references;
- show page or page-range references;
- preserve passage IDs for technical provenance;
- allow direct inspection of the cited source page;
- state when the selected evidence does not support an answer.

Normal single-model questioning is the default interaction. Model comparison is
optional and uses the same question and same evidence scope for each compared
model.

This design prevents the initial question from shaping the case graph and lets
investigators ask multiple questions against the same processed evidence
without rebuilding the case.

Implementation status:
- analysis-time question removed from the new-analysis UI;
- analysis backend made question-independent;
- Compare LLMs renamed to Ask / Compare LLMs;
- scoped free-text question execution backend remains the next implementation
  slice.


## 2E. Scoped Ask execution

Ask / Compare LLMs is now implemented in source as a separate interaction over
already processed evidence.

### Scope

An investigator can ask against:

1. the entire processed case / AnalysisGroup;
2. one source document;
3. a selected group of source documents.

A QuestionRun preserves:
- AnalysisGroup ID;
- information class;
- scope mode;
- selected document IDs;
- question SHA-256;
- model plan;
- processing status;
- retrieval mode;
- creation identity/timestamp.

The question does not modify the analysis graph.

### Model policy

- A/B → class-approved Meta Llama 3.3 70B system.ai route;
- C → class-approved GPT-OSS 120B route;
- D → dedicated GPT-OSS 20B, dedicated Llama 3.3 70B, or Both.

For Class D, the question itself is encrypted before persistence. No downgrade
to A/B/C model routes is allowed.

### Answer contract

Each QuestionModelRun returns:
- evidence-grounded answer;
- supporting passage IDs;
- report/document + page/page-range references;
- machine-readable document/page locations;
- insufficient-evidence flag;
- limitations;
- model/version/service metadata;
- duration and token metadata.

The App can render the cited PDF page directly when the current investigator has
Unity Catalog access.

### Current retrieval behaviour

For ordinary free-text questions, the first operational path uses all passages
inside the selected evidence scope, subject to a strict controlled size limit.
If the scope exceeds that limit, the run fails with
`GOVERNED_RETRIEVAL_REQUIRED` rather than silently truncating evidence.

For Class-B questions that exactly match the normalised `user_query` of one
persisted MAIRA governed query specification:
- the QuestionRun records the MAIRA query/spec identifiers;
- IKF uses the MAIRA-governed relationship runner;
- current supported deterministic relationships are `FOLLOWED_BY` and
  `CONTRIBUTED_TO`;
- only supported relationship-evidence passages are sent to the LLM;
- if no explicit governed support exists, the system returns a deterministic
  insufficient-evidence outcome and does not ask the LLM to infer the
  relationship.

There is deliberately no fuzzy or LLM-generated mapping from arbitrary free text
to a governed query specification at this stage.


## 2F. Large-scope deterministic free-text retrieval

Arbitrary free-text questions no longer fail solely because the selected
evidence scope exceeds the temporary all-passages limit.

Retrieval decision:

```text
exact persisted governed MAIRA question
    → GOVERNED_RELATIONSHIP_EVIDENCE

ordinary small evidence scope
    → SCOPED_ALL_PASSAGES

ordinary large evidence scope
    → DETERMINISTIC_FREE_TEXT_LEXICAL_V0.1
```

The large-scope method is owned by MAIRA and exposed through:

`maira.retrieval.retrieve_free_text`

It:
- uses deterministic lexical ranking only;
- does not use an LLM for query rewriting;
- does not use embeddings;
- does not assign EMCIP concepts through fuzzy semantics;
- selects whole passages rather than silently truncating passage text.

For Class B, IKF may supply expansions only from:
- `terminology_normalisations.review_status = HUMAN_VALIDATED`;
- the corresponding governed EMCIP controlled value.

The expansion is bidirectional only for that explicitly validated mapping.
Classes A/C/D use the same deterministic retrieval algorithm over their already
processed IKF passages without EMCIP expansion.

Every model-answering QuestionRun now persists a retrieval snapshot containing:
- retrieval method/version;
- analysis ID;
- question SHA-256;
- evidence scope;
- governed query identifiers where applicable;
- exact selected passage IDs.

The snapshot ID is a deterministic SHA-256-derived identifier. This allows a
future benchmark to reproduce the exact evidence denominator supplied to the
model.

If deterministic lexical retrieval finds no matching passage, the system
returns a deterministic insufficient-evidence result and does not call the LLM.


## 2G. Generic EMCIP mapping proposal and review

EMCIP mapping is a separate on-demand capability after a model graph exists.

Workflow:

```text
AnalysisGroup + ModelRun graph
        ↓
MAIRA EMCIP operational registry
        ↓
deterministic shortlist
        ↓
LLM chooses shortlist candidate or NO_MAPPING
        ↓
EMCIPMappingProposal
        ↓
human VALIDATED / REJECTED / AMENDED
```

Controls:
- IKF does not duplicate the EMCIP registry.
- The model cannot emit a code outside the shortlist.
- Proposal generation is model-run scoped.
- Proposals are not written onto the KGNode as authoritative mappings.
- Human decisions are append-only.
- An AMENDED review must use another candidate from the same governed shortlist.
- The review UI exposes source report/page evidence and the cited PDF page.
- Class-D dual-model proposals remain separated by model_run_id.

Source:
- notebook 40 — proposal generation;
- notebook 41 — on-demand Job setup;
- notebook 42 — read-only proposal/review validation;
- App resource: `EMCIP_MAPPING_JOB_ID <- emcip_mapping_job`.


## 2H. Reference-context retrieval

Ask / Compare LLMs supports optional reference context without mixing it with
occurrence evidence.

Source layers are explicit:

- `SOURCE_EVIDENCE` — selected case evidence;
- `REFERENCE_CONTEXT` — dedicated governed IKF legal/IMO/technical corpus;
- `CONTROLLED_TAXONOMY` — MAIRA EMCIP vocabulary.

Only SOURCE_EVIDENCE may establish that a case fact occurred.

REFERENCE_CONTEXT is indexed independently from
`/Volumes/bdw_analysis_prod/kg_poc/reference_context` into
`reference_document` and `reference_passage`. It does not require creation of
a separate Class-A AnalysisGroup.

Reference context is independently retrieved with MAIRA's deterministic
free-text lexical method and has its own passage IDs and retrieval snapshot.

QuestionModelRun persists separate source-evidence and reference-context
passage IDs, report/page references and machine page locations.

The App displays the two citation classes separately and can render cited PDF
pages from either the case source or the reference corpus.

See `docs/27_reference_context_retrieval.md`.


## 2I. Two-gate SHIELD classification

SHIELD classification is downstream of human-validated contributing-factor
relationships.

```text
ContributingFactor — CONTRIBUTED_TO → target
        ↓ human Gate 1
deterministic SHIELD retrieval
        ↓
LLM grounded SHIELD proposal
        ↓ human Gate 2
VALIDATED / REJECTED / AMENDED
```

The persistent SHIELD corpus is indexed from the reserved `SHIELD/` volume
folder and is excluded from ordinary case-document retention.

The assistant can propose only from retrieved SHIELD source passages; an
ungrounded label/code is rejected as `NO_GROUNDED_PROPOSAL`.

A proposal becomes stale when its Gate-1 relationship receives a newer human
review.

Only the latest valid human Gate-2 review can represent an authoritative
reviewed SHIELD classification. The graph node and assistant proposal are never
silently overwritten.

See `docs/29_shield_two_gate_workflow.md`.


## 2F. Findings and Knowledge assistant

The Findings & Knowledge capability now reuses the governed QuestionRun / Ask
backend rather than introducing another LLM stack.

### Knowledge assistant

For one completed AnalysisGroup, the investigator can ask a whole-case
free-text question directly from Findings & Knowledge.

The QuestionRun records:

- `interaction_surface = KNOWLEDGE`;
- the same information-class/model policy as Ask / Compare;
- whole-case scope;
- optional governed REFERENCE_CONTEXT;
- the same passage/page citation and retrieval provenance.

The answer therefore uses the same evidence-bounded controls as Ask / Compare,
including MAIRA deterministic retrieval for large scopes and separate
SOURCE_EVIDENCE / REFERENCE_CONTEXT citations.

Detailed one-document / selected-document question scope remains in
Ask / Compare LLMs to keep Findings & Knowledge simple.

### Relationship correction proposals

The investigator can select one evidence-derived graph relationship and request
an LLM check.

Notebook `49_propose_relationship_correction.py`:

- reads only the selected relationship's cited analysis passages;
- never modifies the graph edge;
- may propose:
  - `KEEP`;
  - `CHANGE_RELATIONSHIP`;
  - `REJECT_RELATIONSHIP`;
  - `INSUFFICIENT_EVIDENCE`;
- limits replacement relationships to the governed IKF relationship vocabulary;
- preserves passage/page provenance;
- binds the proposal to the latest human RelationshipReview that existed when
  the proposal was generated.

Notebook `50_create_relationship_correction_job.py` defines the dedicated
one-task Lakeflow Job. The App resource is:

`RELATIONSHIP_CORRECTION_JOB_ID <- relationship_correction_job`

### Human authority

An assistant proposal never becomes authoritative automatically.

The user must explicitly choose:

- approve assistant proposal;
- dismiss assistant proposal;
- apply a different human outcome.

Approved/amended outcomes create a new append-only `RelationshipReview`.
The original graph relationship is not overwritten.

A proposal becomes stale when a newer RelationshipReview exists after its base
review and must then be regenerated.

Notebook `51_validate_relationship_correction_governance.py` validates that
the graph edge remains unchanged and that any authoritative semantic change
comes only through the append-only human RelationshipReview chain.

Transient assistant rationale/evidence is removed by the normal analysis
retention cleanup; compact human governance metadata remains.


## 2G. Similar MAIRA investigation cases

Findings & Knowledge now contains a deterministic similar-case capability over
the MAIRA investigation repository.

### Method

Notebook `52_find_similar_maira_cases.py`:

1. starts from one completed AnalysisGroup;
2. derives bounded focus labels from graph concepts:
   - Event;
   - ContributingFactor;
   - Finding;
   - SafetyIssue;
   - System;
3. explicitly excludes Vessel / Actor / Claim identity labels from similarity
   input;
4. searches only MAIRA `INVESTIGATION / MAIN_REPORT` passages;
5. excludes the current MAIRA report package(s);
6. reuses MAIRA `DETERMINISTIC_FREE_TEXT_LEXICAL_V0.1`;
7. aggregates matched passages deterministically by report package;
8. persists up to five package candidates with:
   - rank;
   - matched terms;
   - score metadata;
   - supporting passage IDs;
   - report/page references;
   - machine-readable page locations;
   - retrieval method and snapshot ID.

No LLM, embedding or vector similarity model is used.

The capability therefore explains *why* a candidate was retrieved instead of
presenting an opaque similarity percentage.

### App interaction

The investigator can run **Find similar MAIRA cases** from Findings & Knowledge.

Returned candidates show:
- report title / vessel where available;
- matched lexical terms;
- matched report/page references;
- direct cited-page PDF viewing subject to the investigator's Unity Catalog
  permissions.

The result is a retrieval candidate only. It does not assert that the two
casualties share the same causes, conclusions or safety lessons.

Notebook `53_create_similar_cases_job.py` creates the one-task Lakeflow Job.

App resource:
`SIMILAR_CASES_JOB_ID <- similar_cases_job`

Notebook `54_validate_similar_maira_cases.py` verifies current-package
exclusion, candidate ranks, MAIRA passage provenance and page-location
traceability.

Transient matched terms/passage/page details follow the normal analysis
retention cleanup.
