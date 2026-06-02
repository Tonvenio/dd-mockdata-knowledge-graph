"""Evaluation harness: IE precision/recall, RAG, contradiction-detection.

Each `run_*` returns an exit code (0 = pass thresholds, non-zero = fail).
"""
from __future__ import annotations
from pathlib import Path

from .queries import IE_QUERIES, CONTRADICTION_QUERIES, RAG_QUESTIONS_DE


def run_suite(suite: str, kg_path: str, questions: str | None = None) -> int:
    if suite == "ie":
        return _run_ie(kg_path)
    if suite == "rag":
        return _run_rag(kg_path, questions)
    if suite == "contradiction":
        return _run_contradiction(kg_path)
    print(f"unknown suite: {suite}")
    return 2


def _run_ie(kg_path: str) -> int:
    """Compare extractor output vs. canonical ground-truth on each query."""
    g = _load(kg_path)
    print(f"IE suite — running {len(IE_QUERIES)} probes against {kg_path}")
    passed = 0
    for q in IE_QUERIES:
        rows = list(g.query(q["sparql"]))
        ok = q["min"] <= len(rows) <= q.get("max", 10_000)
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {q['name']:<40} → {len(rows):>4} rows (expected {q['min']}..{q.get('max','*')})")
        passed += int(ok)
    print(f"\n{passed}/{len(IE_QUERIES)} probes passed")
    return 0 if passed == len(IE_QUERIES) else 1


def _run_contradiction(kg_path: str) -> int:
    g = _load(kg_path)
    print(f"contradiction suite — {len(CONTRADICTION_QUERIES)} probes")
    fails = 0
    for q in CONTRADICTION_QUERIES:
        rows = list(g.query(q["sparql"]))
        if rows:
            print(f"  [FAIL] {q['name']:<40} → {len(rows)} contradictions:")
            for r in rows[:5]:
                print(f"          {r}")
            fails += 1
        else:
            print(f"  [PASS] {q['name']}")
    return 0 if fails == 0 else 1


def _run_rag(kg_path: str, _questions_path: str | None) -> int:
    g = _load(kg_path)
    print(f"RAG suite — {len(RAG_QUESTIONS_DE)} questions; this stub only checks "
          "that the KG can resolve the expected answer set via SPARQL.")
    passed = 0
    for q in RAG_QUESTIONS_DE:
        rows = list(g.query(q["sparql"]))
        ok = len(rows) >= q["min_answers"]
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {q['question'][:70]:<70} → {len(rows):>3}")
        passed += int(ok)
    print(f"\n{passed}/{len(RAG_QUESTIONS_DE)} passed")
    return 0 if passed == len(RAG_QUESTIONS_DE) else 1


def _load(kg_path: str):
    from rdflib import Graph
    g = Graph()
    g.parse(kg_path, format="turtle" if str(kg_path).endswith(".ttl") else None)
    return g
