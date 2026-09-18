# Commodore Clipper PoC Case

## Case

Report on the investigation of the fire on the main vehicle deck of Commodore Clipper while on passage to Portsmouth, 16 June 2010.

## Current graph

17 nodes and 12 relationships.

### Main downstream chain

```text
Electrical cable overheating
    RESULTED_IN
Fire in refrigerated trailer
    RESULTED_IN
Fire damage to cables and pipework
    RESULTED_IN
System disruption
    AFFECTED
Manoeuvring capability affected

System disruption
    AFFECTED
Fire containment capability affected
```

### Stability chain

```text
Vehicle deck drains blocked
    RESULTED_IN
Fire-fighting water accumulated
    RESULTED_IN
Reduced vessel stability
```

### Contributing-factor convergence

```text
High cargo density
        \
         CONTRIBUTED_TO → Restricted access to fire and passengers
        /
Vessel design constraints
```

```text
Ineffective coordination
        \
         CONTRIBUTED_TO → Berthing significantly delayed
        /
Equipment defects
```

## EMCIP mapping disposition

The PoC preserves validated mappings and intentionally unresolved concepts.

Examples of validated mappings include:

- Electrical cable overheating → Accident Event / System / Electrical equipment
- Vehicle deck drains blocked → Accident Event / System / Bilge, drain
- Reduced vessel stability → Accident Event / System / Stability
- Reduced vessel stability → Accident Event / Failure type / Insufficient stability
- Manoeuvring capability affected → Accident Event / System / Manoeuvrability
- Vessel design constraints → Contributing Factor / CF coding / Design
- Ineffective coordination → Contributing Factor / CF coding / Lack of communication & coordination
- Berthing significantly delayed → Accident Event / Task / Berthing

Unresolved concepts are not forced into unsupported mappings.

## Current storage note

The workshop tables currently reside under existing `bdw_analysis_prod.maira.workshop_kg_cc_v02_*` tables because the PoC was developed in that environment.

This repository is nevertheless a separate project. A future migration should move authoritative graph/review tables into a dedicated schema.
