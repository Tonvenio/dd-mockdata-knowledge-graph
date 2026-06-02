"""Smoke tests for the positions extractor.

Skips automatically if dd-mockdata is not checked out next to this repo.
"""
from __future__ import annotations
from pathlib import Path
import pytest

from ddkg.corpus import Corpus
from ddkg.extractors.positions import PositionsExtractor
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


@pytest.fixture(scope="module")
def triples(corpus: Corpus):
    return list(PositionsExtractor(corpus).extract())


def test_at_least_four_rea_vorstand_positions(triples) -> None:
    rea_positions = [t for t in triples
                     if t.p == NS.DD + "positionAt"
                     and isinstance(t.o, str) and t.o.endswith("org/rea")]
    assert len(rea_positions) >= 4, \
        f"expected >=4 Vorstand positions at REA, got {len(rea_positions)}"


def test_at_least_ten_event_dates(triples) -> None:
    event_dates = [t for t in triples if t.p == NS.DD + "eventDate"]
    assert len(event_dates) >= 10, \
        f"expected >=10 eventDate triples (HV + AR), got {len(event_dates)}"


def test_no_appointed_after_resigned(triples) -> None:
    appointed = {t.s: t.o for t in triples if t.p == NS.DD + "appointedOn"}
    resigned = {t.s: t.o for t in triples if t.p == NS.DD + "resignedOn"}
    for pos, a in appointed.items():
        r = resigned.get(pos)
        if r is not None:
            assert a <= r, f"appointedOn {a} after resignedOn {r} on {pos}"


def test_every_person_holds_a_position(triples) -> None:
    persons = {t.s for t in triples
               if t.p == NS.RDF + "type" and t.o == NS.DD + "Person"}
    holders = {t.s for t in triples if t.p == NS.DD + "holdsPosition"}
    orphans = persons - holders
    assert not orphans, f"persons without a position: {orphans}"
