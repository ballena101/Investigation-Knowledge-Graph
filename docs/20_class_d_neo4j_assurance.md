# Class D Neo4j assurance assessment

## Status

**Current status: CONDITIONALLY SUITABLE ARCHITECTURE — NOT YET APPROVED FOR RAW
CLASS D EVIDENCE.**

The project must not claim that Neo4j AuraDB, by itself, makes the IKG compliant
with Article 9 of Directive 2009/18/EC.

Article 9 is fundamentally a confidentiality and purpose-limitation obligation.
It requires protected investigation records not to be made available for
purposes other than the safety investigation unless the competent authority
applies the required overriding-public-interest test.

Database encryption is necessary but not sufficient.

## 1. IKG Class D storage rule

### Raw protected evidence

Raw Class D evidence must remain in the governed Databricks evidence layer,
including where applicable:

- witness statements;
- identities of persons giving evidence;
- health/sensitive personal information;
- investigators' notes/opinions;
- draft reports;
- operational communications;
- VTS recordings/transcripts;
- VDR/S-VDR material.

Neo4j is **not** the default raw-evidence repository for Class D.

### Neo4j Class D graph projection

Neo4j may receive only the minimum graph representation necessary for
investigation analysis, preferably:

- opaque analysis IDs;
- opaque source-document IDs;
- opaque passage IDs;
- de-identified node labels;
- de-identified analytical descriptions;
- controlled relationship labels;
- model/review provenance;
- human-review decisions;
- evidence references rather than full source excerpts.

A graph derivative can itself remain confidential if its context can identify a
person or disclose protected investigation knowledge.

## 2. What Neo4j currently provides

Neo4j documents the following Aura controls:

- encryption in transit;
- encryption at rest;
- encrypted backups;
- backups retained in the same cloud provider and region as the instance;
- customer-selected hosting regions;
- RBAC and, on eligible tiers, more granular property-based access controls;
- private endpoints / private network access on eligible tiers;
- customer-managed encryption keys on eligible configurations;
- ISO 27001 and SOC 2 Type II security assurance;
- a Data Processing Addendum in which Neo4j acts as processor for personal
  data processed on behalf of the customer.

These controls support confidentiality but do not constitute Article 9
certification.

## 3. Matters that must be verified before Class D approval

The current Aura instance must be checked for:

1. **Contract / DPA**
   - applicable Neo4j Cloud Agreement;
   - executed/applicable Data Processing Addendum;
   - applicable Security Addendum;
   - authorised subprocessor arrangement.

2. **Region**
   - exact Aura cloud provider and region;
   - approved EEA/organisational residency requirement;
   - whether any support/processing exception could create an onward transfer.

3. **Network**
   - private endpoint / Private Link where required;
   - public traffic disabled for the Class D instance where technically
     supported;
   - otherwise documented compensating controls.

4. **Identity/access**
   - dedicated service principal for the App/backend;
   - least-privilege roles;
   - no shared administrator credentials;
   - review of Aura console/project access;
   - graph-level restrictions where needed.

5. **Data minimisation**
   - no full witness statements or VDR/VTS content;
   - no unnecessary names/health data;
   - graph stores passage IDs rather than full protected evidence whenever
     possible.

6. **Encryption**
   - TLS connection validation;
   - encryption at rest;
   - customer-managed keys if required by organisational policy.

7. **Backups and deletion**
   - snapshot cadence/retention for the selected Aura tier;
   - deletion behaviour;
   - contractual deletion period;
   - whether that period meets EMSA retention/deletion requirements.

8. **Logging**
   - queries/logs must not duplicate protected evidence unnecessarily;
   - diagnostic/log-forwarding destinations must be approved.

9. **Purpose limitation**
   - Neo4j graph access restricted to the authorised safety-investigation /
     IKG purpose;
   - no reuse for unrelated demonstrations, model training or publication
     without a separate lawful/authorised basis.

10. **Incident response and audit**
    - audit evidence available;
    - incident notification path;
    - access review and revocation process.

## 4. Important contractual observation

Neo4j's current DPA states that personal data are hosted in the customer-selected
location and that Neo4j acts as processor. It also provides transfer mechanisms
for restricted transfers.

The same DPA states that, following termination or written deletion request,
Neo4j will delete personal data as soon as reasonably practicable and within a
maximum of 180 days, unless law requires otherwise.

That maximum period must be checked against the retention/deletion requirements
accepted for Class D. It must not be assumed to be suitable.

## 5. Recommended Class D architecture

```text
RAW CLASS D EVIDENCE
Databricks Unity Catalog / governed Delta
             │
             │ opaque IDs + de-identified analytical derivative only
             ▼
       Neo4j Class D graph
             │
             │ authorised graph queries
             ▼
        Databricks App
```

The graph should resolve evidence through an authorised backend when an
investigator needs to inspect the original source.

The source text itself should not be replicated into Neo4j simply for
convenience.

## 6. Article 9 conformity position

The IKG may claim only:

**"Designed to support Article 9 confidentiality through purpose limitation,
data minimisation, controlled access, provenance and separation of protected
source evidence from analytical graph derivatives."**

It must not claim:

**"Neo4j is Article 9 compliant"** or **"use of Neo4j ensures compliance with
Directive 2009/18/EC."**

Final operational conformity depends on:

- the Member State / competent-authority legal framework;
- EMSA organisational approval;
- GDPR assessment;
- actual Aura contract/tier/region/configuration;
- access and purpose controls;
- the data actually stored.

## 7. Go/no-go gate

Class D graph persistence in Aura is approved only after all required items are
recorded as PASS:

| Control | Required result |
|---|---|
| Raw Class D evidence excluded from Neo4j | PASS |
| DPA / Security Addendum reviewed | PASS |
| Approved region confirmed | PASS |
| Private networking or approved compensating control | PASS |
| Least-privilege identity/RBAC | PASS |
| Backup/retention/deletion accepted | PASS |
| Logging destinations accepted | PASS |
| Subprocessors/transfers accepted | PASS |
| Security/DP/legal owner approval | PASS |
| End-to-end access test | PASS |

Until then, the implementation status is:

**Class D Neo4j use: conditional / validation environment only.**
