"""SPARQL queries used by the evaluation suites.

Each entry pairs a human-readable description with a SPARQL query and a
threshold (min / max row count) for pass/fail. Keep these short — additions
welcome via PR.
"""

_PFX = """
PREFIX dd:     <https://w3id.org/dd-mockdata#>
PREFIX rdfs:   <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <https://schema.org/>
"""

# URIs are written out in <...> form (rdflib's SPARQL parser doesn't accept
# slashes inside prefixed names).
_REA = "<https://w3id.org/dd-mockdata#org/rea>"
_BTP = "<https://w3id.org/dd-mockdata#org/btp>"

IE_QUERIES = [
    # ── canonical seed (company / org structure) ─────────────────────────
    {
        "name": "all three companies present",
        "sparql": _PFX + "SELECT ?c WHERE { ?c a dd:Company ; rdfs:label ?l }",
        "min": 3, "max": 200,
    },
    {
        "name": "Brennhagen has 6-8 subsidiaries",
        "sparql": _PFX + f"SELECT ?s WHERE {{ ?s a dd:Subsidiary ; dd:parentCompany {_REA} }}",
        "min": 6, "max": 8,
    },
    {
        "name": "Brennhagen has a full operative workforce (positions @ REA)",
        "sparql": _PFX + f"SELECT ?p WHERE {{ ?pos dd:positionAt {_REA} . ?p dd:holdsPosition ?pos }}",
        "min": 50, "max": 5000,
    },
    {
        "name": "Müller has top-5 customers",
        "sparql": _PFX + "SELECT ?c WHERE { ?c a dd:Counterparty ; dd:counterpartyKind 'customer' }",
        "min": 5, "max": 30,
    },
    {
        "name": "Brennhagen has Automotive OEM counterparties",
        "sparql": _PFX + "SELECT ?o WHERE { ?o a dd:Counterparty ; dd:counterpartyKind 'oem' }",
        "min": 6, "max": 15,
    },
    {
        "name": "BioTech has investors",
        "sparql": _PFX + f"SELECT ?inv WHERE {{ {_BTP} dd:investorShare ?inv }}",
        "min": 3, "max": 10,
    },
    {
        "name": "every Person holds at least one Position",
        "sparql": _PFX + "SELECT ?p WHERE { ?p a dd:Person . FILTER NOT EXISTS { ?p dd:holdsPosition ?x } }",
        "min": 0, "max": 0,
    },
    # ── document index (filename extractor) ──────────────────────────────
    {
        "name": "corpus document index is populated",
        "sparql": _PFX + "SELECT ?d WHERE { ?d a dd:DocumentReference }",
        "min": 5000, "max": 10000,
    },
    {
        "name": "every DocumentReference has a docType",
        "sparql": _PFX + "SELECT ?d WHERE { ?d a dd:DocumentReference . FILTER NOT EXISTS { ?d dd:docType ?t } }",
        "min": 0, "max": 0,
    },
    {
        "name": "every DocumentReference has a filePath",
        "sparql": _PFX + "SELECT ?d WHERE { ?d a dd:DocumentReference . FILTER NOT EXISTS { ?d dd:filePath ?t } }",
        "min": 0, "max": 0,
    },
    # ── employment contracts ─────────────────────────────────────────────
    {
        "name": "≥200 employment contracts extracted",
        "sparql": _PFX + "SELECT ?c WHERE { ?c a dd:EmploymentContract }",
        "min": 200, "max": 4000,
    },
    {
        "name": "every EmploymentContract names an employer (counterpartyOf)",
        "sparql": _PFX + "SELECT ?c WHERE { ?c a dd:EmploymentContract . FILTER NOT EXISTS { ?c dd:counterpartyOf ?o } }",
        "min": 0, "max": 0,
    },
    # ── patents ──────────────────────────────────────────────────────────
    {
        "name": "≥30 patents extracted",
        "sparql": _PFX + "SELECT ?p WHERE { ?p a dd:Patent }",
        "min": 30, "max": 200,
    },
    {
        "name": "every Patent has a jurisdiction",
        "sparql": _PFX + "SELECT ?p WHERE { ?p a dd:Patent . FILTER NOT EXISTS { ?p dd:jurisdiction ?j } }",
        "min": 0, "max": 0,
    },
    {
        "name": "every Patent has an assignee",
        "sparql": _PFX + "SELECT ?p WHERE { ?p a dd:Patent . FILTER NOT EXISTS { ?p dd:assignee ?a } }",
        "min": 0, "max": 0,
    },
    {
        "name": "Brennhagen Patentschriften carry a filing number",
        "sparql": _PFX + "SELECT ?p WHERE { ?p a dd:Patent ; dd:filingNumber ?f }",
        "min": 15, "max": 100,
    },
    {
        "name": "patents list named inventors",
        "sparql": _PFX + "SELECT ?p ?i WHERE { ?p dd:inventedBy ?i }",
        "min": 10, "max": 500,
    },
    {
        "name": "every inventor resolves to a known dd:Person",
        "sparql": _PFX + "SELECT ?i WHERE { ?p dd:inventedBy ?i . FILTER NOT EXISTS { ?i a dd:Person } }",
        "min": 0, "max": 0,
    },
    # ── covenants ────────────────────────────────────────────────────────
    {
        "name": "exactly the 3 loan covenants",
        "sparql": _PFX + "SELECT ?c WHERE { ?c a dd:Covenant }",
        "min": 3, "max": 3,
    },
    {
        "name": "every Covenant uses an allowed operator",
        "sparql": _PFX + 'SELECT ?c WHERE { ?c a dd:Covenant ; dd:covenantOperator ?o . '
                         'FILTER(?o NOT IN ("<=", ">=", "<", ">", "=")) }',
        "min": 0, "max": 0,
    },
    {
        "name": "every Covenant is SHACL-complete (name+operator+threshold)",
        "sparql": _PFX + "SELECT ?c WHERE { ?c a dd:Covenant . FILTER("
                         "NOT EXISTS { ?c dd:covenantName ?n } || "
                         "NOT EXISTS { ?c dd:covenantOperator ?o } || "
                         "NOT EXISTS { ?c dd:covenantThreshold ?t }) }",
        "min": 0, "max": 0,
    },
    {
        "name": "≥16 covenant observations (4 quarters × years)",
        "sparql": _PFX + "SELECT ?o WHERE { ?o a dd:CovenantObservation }",
        "min": 16, "max": 64,
    },
    {
        "name": "every observation carries a numeric value",
        "sparql": _PFX + "SELECT ?o WHERE { ?o a dd:CovenantObservation . FILTER NOT EXISTS { ?o dd:observedValue ?v } }",
        "min": 0, "max": 0,
    },
    # ── contracts (dates / volumes / counterparties) ─────────────────────
    {
        "name": "supply contracts carry a contract volume",
        "sparql": _PFX + "SELECT ?c WHERE { ?c a dd:SupplyContract ; dd:volumeEur ?v }",
        "min": 10, "max": 200,
    },
    {
        "name": "contracts resolve a counterparty",
        "sparql": _PFX + "SELECT ?c ?o WHERE { ?c dd:counterpartyOf ?o }",
        "min": 100, "max": 5000,
    },
    {
        "name": "no effectiveDate falls after its expiryDate",
        "sparql": _PFX + "SELECT ?c WHERE { ?c dd:effectiveDate ?e ; dd:expiryDate ?x . FILTER(?e > ?x) }",
        "min": 0, "max": 0,
    },
    # ── governance events ────────────────────────────────────────────────
    {
        "name": "Brennhagen Hauptversammlung minutes (3 years)",
        "sparql": _PFX + "SELECT ?e WHERE { ?e a dd:ShareholderMeeting }",
        "min": 3, "max": 10,
    },
    {
        "name": "Aufsichtsrat meetings carry a meeting date",
        "sparql": _PFX + "SELECT ?e WHERE { ?e a dd:BoardMeeting ; dd:eventDate ?d }",
        "min": 8, "max": 40,
    },
]

CONTRADICTION_QUERIES = [
    {
        "name": "no person with conflicting types",
        "sparql": _PFX + """
            SELECT ?p WHERE {
              ?p a dd:Person ; a dd:Company .
            }""",
    },
    {
        "name": "no subsidiary that is also a counterparty",
        "sparql": _PFX + """
            SELECT ?s WHERE {
              ?s a dd:Subsidiary ; a dd:Counterparty .
            }""",
    },
    {
        "name": "no entity with two distinct labels (modulo language)",
        "sparql": _PFX + """
            SELECT ?e ?l1 ?l2 WHERE {
              ?e rdfs:label ?l1 . ?e rdfs:label ?l2 .
              FILTER(STR(?l1) != STR(?l2))
            } LIMIT 50""",
    },
    {
        "name": "no contract effective after it expires",
        "sparql": _PFX + """
            SELECT ?c WHERE {
              ?c dd:effectiveDate ?e ; dd:expiryDate ?x . FILTER(?e > ?x)
            }""",
    },
    {
        "name": "no position appointed after it resigned",
        "sparql": _PFX + """
            SELECT ?p WHERE {
              ?p dd:appointedOn ?a ; dd:resignedOn ?r . FILTER(?a > ?r)
            }""",
    },
    {
        "name": "no patent with two distinct filing numbers",
        "sparql": _PFX + """
            SELECT ?p WHERE {
              ?p dd:filingNumber ?f1 . ?p dd:filingNumber ?f2 .
              FILTER(STR(?f1) != STR(?f2))
            }""",
    },
    {
        "name": "no covenant with two distinct thresholds",
        "sparql": _PFX + """
            SELECT ?c WHERE {
              ?c dd:covenantThreshold ?t1 . ?c dd:covenantThreshold ?t2 .
              FILTER(?t1 != ?t2)
            }""",
    },
]

RAG_QUESTIONS_DE = [
    {
        "question": "Wer ist Vorstandsvorsitzende der Brennhagen Elektronik AG?",
        "sparql": _PFX + f"SELECT ?p WHERE {{ ?pos dd:positionAt {_REA} . ?p dd:holdsPosition ?pos }}",
        "min_answers": 1,
    },
    {
        "question": "Welche Tochtergesellschaften hat die Brennhagen Elektronik AG und in welchen Ländern?",
        "sparql": _PFX + f"SELECT ?s ?c WHERE {{ ?s a dd:Subsidiary ; dd:parentCompany {_REA} ; dd:countryCode ?c }}",
        "min_answers": 6,
    },
    {
        "question": "Welche Produkte stellt die Brennhagen-Gruppe her?",
        "sparql": _PFX + f"SELECT ?prod WHERE {{ ?prod a dd:Product ; dd:manufacturedBy {_REA} }}",
        "min_answers": 3,
    },
    {
        "question": "Wer sind die Investoren der Sentavia Precision GmbH?",
        "sparql": _PFX + f"SELECT ?i WHERE {{ {_BTP} dd:investorShare ?i }}",
        "min_answers": 3,
    },
    {
        "question": "Welche Notified Body zertifiziert die BioTech-Produkte?",
        "sparql": _PFX + f"SELECT ?p ?cls WHERE {{ ?p a dd:Product ; dd:manufacturedBy {_BTP} ; dd:regulatoryClass ?cls }}",
        "min_answers": 3,
    },
]
