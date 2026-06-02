"""End-to-end pipeline tests: full-corpus build, DoD thresholds, SHACL validity.

These exercise the whole extractor stack through the Deduper and validate the
emitted graph against schema/shapes.ttl with pyshacl — the same gate the v0.2
definition-of-done requires.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import pytest

from ddkg.corpus import Corpus
from ddkg.pipeline import build_triples
from ddkg.builders.rdf import to_rdf
from ddkg.model import NS

ROOT = Path(__file__).resolve().parent.parent
CORPUS_DEFAULT = ROOT.parent / "dd-mockdata"


@pytest.fixture(scope="module")
def built():
    if not (CORPUS_DEFAULT / "enhance_lib.py").exists():
        pytest.skip(f"dd-mockdata not found at {CORPUS_DEFAULT}")
    triples, dd = build_triples(Corpus(CORPUS_DEFAULT))
    return triples, dd


def test_at_least_20k_triples(built) -> None:
    triples, _ = built
    assert len(triples) >= 20_000, f"expected ≥20k triples, got {len(triples)}"


def test_dod_type_thresholds(built) -> None:
    triples, _ = built
    typ = Counter(t.o for t in triples if t.p == NS.RDF + "type")
    assert typ[NS.DD + "EmploymentContract"] >= 200
    assert typ[NS.DD + "Patent"] >= 30
    assert typ[NS.DD + "CovenantObservation"] >= 16
    assert typ[NS.DD + "Person"] >= 100


def test_canonical_wins_conflicts(built) -> None:
    # every dropped functional conflict must have been a non-canonical (conf<1) triple
    _, dd = built
    assert all(dropped.confidence < 1.0 for _, dropped in dd.conflicts), \
        "a canonical (confidence 1.0) triple was dropped as a conflict"


def test_shacl_conforms(built) -> None:
    pytest.importorskip("pyshacl")
    from pyshacl import validate
    triples, _ = built
    data = to_rdf(triples)
    shapes = ROOT / "schema" / "shapes.ttl"
    onto = ROOT / "schema" / "ontology.ttl"
    conforms, _graph, text = validate(
        data, shacl_graph=str(shapes), ont_graph=str(onto),
        inference="none", advanced=True,
    )
    assert conforms, f"SHACL validation failed:\n{text}"
