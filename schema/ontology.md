# Ontology overview

Companion to [`ontology.ttl`](ontology.ttl).

## Namespace

`@prefix dd: <https://w3id.org/dd-mockdata#>`

Reused W3C vocabularies: `org:` (W3C Organization), `foaf:` (FOAF),
`prov:` (PROV-O), `schema:` (schema.org), `xsd:` (XML Schema).

## Class hierarchy

```
owl:Thing
├── dd:Company        (subclass of org:FormalOrganization)
│   ├── dd:Holding
│   ├── dd:Subsidiary
│   └── dd:Counterparty
├── dd:Person         (subclass of foaf:Person)
├── dd:Position       (subclass of org:Membership) ── a role someone holds at an org for a time period
├── dd:Role           (subclass of org:Role)
├── dd:Contract       (subclass of schema:Contract)
│   ├── dd:EmploymentContract
│   ├── dd:SupplyContract
│   ├── dd:LoanFacility
│   ├── dd:LicenseContract
│   ├── dd:LeaseContract
│   ├── dd:ServiceContract
│   └── dd:NDA
├── dd:Patent
├── dd:Product
├── dd:Covenant
├── dd:CovenantObservation
├── dd:ICTransaction
├── dd:PensionPlan
├── dd:Acquisition
├── dd:WorksCouncil
└── dd:DocumentReference (subclass of prov:Entity) ── provenance anchor
```

## Key design choices

**Time-anchored positions.** A person's role at an org is reified as
`dd:Position` (W3C ORG-style) so we can record `appointedOn` /
`resignedOn` dates and ausschuss memberships. A single `dd:Person` can
hold many positions over time.

**Provenance via PROV-O.** Every triple emitted by the extractor carries
an implicit `prov:wasDerivedFrom` link from the subject URI to a
`dd:DocumentReference` URI of the form `dd:doc/{relative-path}`. The
canonical extractor uses the source `enhance_lib.py` path; document-level
extractors will use the actual `.docx` / `.xlsx` path (and optionally a
paragraph index).

**Confidence on every triple.** All triples carry a `dd:confidence`
property (0..1). The canonical extractor always emits 1.0. Document-level
and LLM extractors emit lower confidences; the eval suites can filter on
this for precision/recall tuning.

**Counterparties are first-class.** Even though they're real-world
organisations (BMW, KPMG, ...), we model them as `dd:Counterparty`
nodes with a `dd:counterpartyKind` literal ("customer" / "supplier" /
"oem" / "advisor" / "bank" / "investor" / "clinic" / "distributor") so
queries can filter without leaving the KG.

**Subsidiaries link to their parent.** `dd:parentCompany` (subsidiary
→ holding) gives a clean traversal from any operational document up to
the consolidating entity.

**Covenants & observations.** A `dd:Covenant` is the rule
("Net-Debt/EBITDA ≤ 3.0x"); a `dd:CovenantObservation` is a point-in-time
fact ("Q3/2023 = 0.32x"). This separation lets the contradiction suite
verify that no observation violates its covenant without re-parsing prose.

## Example fragment

```turtle
@prefix dd:     <https://w3id.org/dd-mockdata#> .
@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
@prefix schema: <https://schema.org/> .
@prefix prov:   <http://www.w3.org/ns/prov#> .

dd:org/rea  a dd:Company ;
    rdfs:label "Brennhagen Elektronik AG" ;
    dd:hrb "HRB 726451, Amtsgericht Stuttgart" ;
    dd:wkn "RHGRP1" ;
    dd:isin "DE000RHGRP12" ;
    dd:revenueEur 612000000 ;
    schema:address "Vaihinger Straße 120, 70567 Stuttgart" ;
    prov:wasDerivedFrom dd:doc/roehrig_large/enhance_lib.py .

dd:org/reg  a dd:Subsidiary ;
    rdfs:label "Brennhagen Elektronik GmbH" ;
    dd:parentCompany dd:org/rea ;
    dd:countryCode "DE" ;
    dd:employees 820 .

dd:person/anna-mueller  a dd:Person ;
    rdfs:label "Anna Müller" ;
    dd:holdsPosition dd:position/anna-mueller--ceo-vorstandsvorsitzende--rea .

dd:position/anna-mueller--ceo-vorstandsvorsitzende--rea  a dd:Position ;
    dd:positionAt dd:org/rea ;
    dd:positionRole dd:role/ceo-vorstandsvorsitzende .
```

## SHACL shapes

A first set of shapes lives in [`shapes.ttl`](shapes.ttl) and enforces:

- Every `dd:Person` has at least one `dd:holdsPosition`.
- Every `dd:Subsidiary` has exactly one `dd:parentCompany`.
- `dd:appointedOn` (if present) must precede `dd:resignedOn`.
- `dd:Covenant` requires `dd:covenantName`, `dd:covenantOperator`,
  `dd:covenantThreshold`.

Run with: `pyshacl -s schema/shapes.ttl -e schema/ontology.ttl -d kg/gold.ttl`
