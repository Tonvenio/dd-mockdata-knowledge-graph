"""Smoke tests for the covenants extractor.

Skips automatically if dd-mockdata is not checked out next to this repo.
"""
from __future__ import annotations
from pathlib import Path
import numbers
import pytest

from ddkg.corpus import Corpus
from ddkg.extractors.covenants import CovenantsExtractor
from ddkg.model import NS

CORPUS_DEFAULT = Path(__file__).resolve().parent.parent.parent / "dd-mockdata"

_OPERATORS = {"<=", ">=", "<", ">", "="}


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    if not (CORPUS_DEFAULT / "enhance_lib.py").exists():
        pytest.skip(
            f"dd-mockdata not found at {CORPUS_DEFAULT}; "
            "clone it next to dd-mockdata-kg or set DD_MOCKDATA_ROOT.",
        )
    return Corpus(CORPUS_DEFAULT)


@pytest.fixture(scope="module")
def triples(corpus: Corpus) -> list:
    return list(CovenantsExtractor(corpus).extract())


def test_exactly_three_covenants(triples: list) -> None:
    covenants = {t.s for t in triples
                 if t.p == NS.RDF + "type" and t.o == NS.DD + "Covenant"}
    assert len(covenants) == 3, f"expected 3 covenants, got {len(covenants)}"


def test_at_least_sixteen_observations(triples: list) -> None:
    obs = {t.s for t in triples
           if t.p == NS.RDF + "type" and t.o == NS.DD + "CovenantObservation"}
    assert len(obs) >= 16, f"expected >=16 observations, got {len(obs)}"


def test_every_covenant_is_shacl_complete(triples: list) -> None:
    covenants = {t.s for t in triples
                 if t.p == NS.RDF + "type" and t.o == NS.DD + "Covenant"}
    names = {t.s for t in triples if t.p == NS.DD + "covenantName"}
    thresholds = {t.s for t in triples if t.p == NS.DD + "covenantThreshold"}
    operators = {t.s: t.o for t in triples
                 if t.p == NS.DD + "covenantOperator"}
    for cov in covenants:
        assert cov in names, f"{cov} missing covenantName"
        assert cov in thresholds, f"{cov} missing covenantThreshold"
        assert cov in operators, f"{cov} missing covenantOperator"
        assert operators[cov] in _OPERATORS, \
            f"{cov} has bad operator {operators[cov]!r}"


def test_observed_values_non_negative_numbers(triples: list) -> None:
    values = [t.o for t in triples if t.p == NS.DD + "observedValue"]
    assert values, "no observedValue triples emitted"
    for v in values:
        assert isinstance(v, numbers.Number) and not isinstance(v, bool), \
            f"observedValue {v!r} is not a number"
        assert v >= 0, f"observedValue {v!r} is negative"
