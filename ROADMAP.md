# Roadmap

## v0.1 — Scaffold (this release)

- ✅ Schema (`schema/ontology.ttl` + companion doc)
- ✅ Canonical extractor (`ddkg/extractors/canonical.py`) — ~1.5k seed triples
- ✅ RDF / JSON-LD / Cypher serializers
- ✅ CLI: `ddkg build`, `ddkg stats`, `ddkg eval`
- ✅ Evaluation suites: IE, RAG, contradiction (SPARQL-driven)
- ✅ Smoke tests against a checked-out `dd-mockdata`

## v0.2 — Document-level extractors (next)

- [ ] `extractors/filename.py` — parse entity references from filename
      patterns (`AV_NN_Name_Position`, `Patent_NN_*`, `8D_YYYY_NNN_*`, etc.)
- [ ] `extractors/contracts.py` — DOCX rule-based extraction of party,
      Effective Date, Volume, Termination, Governing Law from Verträge.
- [ ] `extractors/patents.py` — DOCX/XLSX extraction of patent number,
      jurisdiction, inventors, assignee.
- [ ] `extractors/covenants.py` — quarterly Covenant Compliance reports →
      `CovenantObservation` instances.
- [ ] `extractors/positions.py` — appointment / departure dates for Vorstand /
      Aufsichtsrat from HV-Protokolle and Bestellungsbeschlüsse.

Target: 25k+ triples, IE-suite precision ≥ 0.95, recall ≥ 0.85.

## v0.3 — LLM hybrid

- [ ] `extractors/llm_hybrid.py` — prompt-based extraction for hard cases
      (M&A targets, contract clauses, financial figures from Lageberichte).
      Gated behind `--llm anthropic|openai|local`; never run by default.
- [ ] Confidence calibration: predicted vs. realized precision per relation.
- [ ] Active-learning loop: low-confidence triples surface to a review queue
      backed by SHACL shape violations.

## v0.4 — RAG benchmark

- [ ] Standard German DD question set (300+ queries with gold answer
      sets derived from the KG).
- [ ] Reference RAG pipelines: BM25, dense (multilingual-e5-large), hybrid;
      generator gpt-4o-mini / claude-3.5-haiku / Llama-3.1-8B.
- [ ] Leaderboard format compatible with [BEIR](https://github.com/beir-cellar/beir).

## v0.5 — Neo4j / GraphDB tooling

- [ ] Dockerised Neo4j + GraphDB containers with auto-load.
- [ ] Browser-ready saved Cypher / SPARQL query collection.
- [ ] Optional: GraphRAG retriever using the KG for relation-aware retrieval.

## v1.0 — Stability

- [ ] Schema frozen, semantic-versioned.
- [ ] Gold KG ships as a GitHub Release asset.
- [ ] Reference paper (preprint).

## Contributing

The single most useful contribution at v0.2 is **a per-extractor PR**:
one file under `ddkg/extractors/`, one focused test under `tests/`,
new IE probes in `ddkg/eval/queries.py`. Keep each PR small.
