"""Smoke tests for the patents extractor (Brennhagen Patentschriften)."""
from __future__ import annotations
from pathlib import Path
import pytest

from ddkg.corpus import Corpus
from ddkg.extractors.patents import PatentsExtractor
from ddkg.model import NS

CORPUS_DEFAULT = Path(__file__).resolve().parent.parent.parent / "dd-mockdata"


@pytest.fixture(scope="module")
def triples():
    if not (CORPUS_DEFAULT / "enhance_lib.py").exists():
        pytest.skip(f"dd-mockdata not found at {CORPUS_DEFAULT}")
    return list(PatentsExtractor(Corpus(CORPUS_DEFAULT)).extract())


def test_filing_numbers_extracted(triples) -> None:
    filings = [t for t in triples if t.p == NS.DD + "filingNumber"]
    assert len(filings) >= 12, f"expected ≥12 patent filing numbers, got {len(filings)}"


def test_jurisdictions_are_known(triples) -> None:
    allowed = {"EP", "DE", "US", "CN", "JP", "WO"}
    juris = [t.o for t in triples if t.p == NS.DD + "jurisdiction"]
    assert juris, "no jurisdictions extracted"
    assert all(j in allowed for j in juris), f"unexpected jurisdiction in {set(juris)}"


def test_inventors_are_persons(triples) -> None:
    inventors = {t.o for t in triples if t.p == NS.DD + "inventedBy"}
    persons = {t.s for t in triples
               if t.p == NS.RDF + "type" and t.o == NS.DD + "Person"}
    assert inventors, "no inventors linked"
    assert inventors <= persons, "an inventedBy target is not typed dd:Person"


def test_inventors_hold_positions(triples) -> None:
    persons = {t.s for t in triples
               if t.p == NS.RDF + "type" and t.o == NS.DD + "Person"}
    holders = {t.s for t in triples if t.p == NS.DD + "holdsPosition"}
    assert not (persons - holders), "an inventor Person holds no position (SHACL risk)"


def test_patents_relate_to_products(triples) -> None:
    rel = [t for t in triples if t.p == NS.DD + "relatesTo"]
    assert len(rel) >= 5, f"expected patents to reference products, got {len(rel)}"
