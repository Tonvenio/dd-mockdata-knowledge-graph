"""Smoke tests for the canonical extractor.

Skips automatically if dd-mockdata is not checked out next to this repo.
"""
from __future__ import annotations
from pathlib import Path
import pytest

from ddkg.corpus import Corpus
from ddkg.extractors import CanonicalExtractor
from ddkg.model import NS

CORPUS_DEFAULT = Path(__file__).resolve().parent.parent.parent / "dd-mockdata"


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    if not (CORPUS_DEFAULT / "enhance_lib.py").exists():
        pytest.skip(
            f"dd-mockdata not found at {CORPUS_DEFAULT}; "
            "clone it next to dd-mockdata-kg or set DD_MOCKDATA_ROOT.",
        )
    return Corpus(CORPUS_DEFAULT)


def test_three_companies(corpus: Corpus) -> None:
    triples = list(CanonicalExtractor(corpus).extract())
    companies = {t.s for t in triples
                 if t.p == NS.RDF + "type" and t.o == NS.DD + "Company"}
    assert len(companies) >= 3, f"expected ≥3 Company entities, got {len(companies)}"


def test_six_roehrig_subsidiaries(corpus: Corpus) -> None:
    triples = list(CanonicalExtractor(corpus).extract())
    subs = {t.s for t in triples
            if t.p == NS.RDF + "type" and t.o == NS.DD + "Subsidiary"}
    assert 6 <= len(subs) <= 8, f"expected 6-8 subsidiaries, got {len(subs)}"


def test_vorstand_positions_linked(corpus: Corpus) -> None:
    triples = list(CanonicalExtractor(corpus).extract())
    rea_positions = [t for t in triples
                     if t.p == NS.DD + "positionAt"
                     and t.o.endswith("org/rea")]
    assert len(rea_positions) >= 4, "Brennhagen should have at least 4 Vorstand positions"


def test_every_person_holds_at_least_one_position(corpus: Corpus) -> None:
    triples = list(CanonicalExtractor(corpus).extract())
    persons = {t.s for t in triples
               if t.p == NS.RDF + "type" and t.o == NS.DD + "Person"}
    holders = {t.s for t in triples if t.p == NS.DD + "holdsPosition"}
    orphans = persons - holders
    assert not orphans, f"persons without a position: {orphans}"
