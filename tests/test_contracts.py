"""Smoke tests for the contracts extractor.

Skips automatically if dd-mockdata is not checked out next to this repo.
Thresholds are deliberately conservative (well below the values verified
against the live corpus) so the tests stay robust to small corpus changes.
"""
from __future__ import annotations
from pathlib import Path
import pytest

from ddkg.corpus import Corpus
from ddkg.extractors.contracts import ContractsExtractor
from ddkg.model import NS

CORPUS_DEFAULT = Path(__file__).resolve().parent.parent.parent / "dd-mockdata"


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    if not (CORPUS_DEFAULT / "enhance_lib.py").exists():
        pytest.skip(
            f"dd-mockdata not found at {CORPUS_DEFAULT}; "
            "clone it next to dd-mockdata-kg.",
        )
    return Corpus(CORPUS_DEFAULT)


@pytest.fixture(scope="module")
def triples(corpus: Corpus) -> list:
    return list(ContractsExtractor(corpus).extract())


def test_contracts_have_effective_dates(triples: list) -> None:
    """At least 20 distinct contracts carry a parsed effectiveDate."""
    contracts = {t.s for t in triples if t.p == NS.DD + "effectiveDate"}
    assert len(contracts) >= 20, (
        f"expected ≥20 contracts with an effectiveDate, got {len(contracts)}"
    )


def test_counterparty_links(triples: list) -> None:
    """At least 30 distinct contracts link to a counterparty company."""
    links = {t.s for t in triples if t.p == NS.DD + "counterpartyOf"}
    assert len(links) >= 30, (
        f"expected ≥30 distinct counterpartyOf links, got {len(links)}"
    )
    # every link must point at an org/ URI
    for t in triples:
        if t.p == NS.DD + "counterpartyOf":
            assert "org/" in t.o, f"counterparty target is not an org URI: {t.o}"


def test_volume_amounts_positive(triples: list) -> None:
    """Some contracts carry a positive EUR volume."""
    vols = [t for t in triples if t.p == NS.DD + "volumeEur"]
    assert len(vols) >= 10, f"expected ≥10 volumeEur facts, got {len(vols)}"
    assert all(isinstance(t.o, (int, float)) and t.o > 0 for t in vols)


def test_effective_never_after_expiry(triples: list) -> None:
    """The temporal invariant: no contract's effectiveDate is after its
    own expiryDate (the extractor must drop the expiry when they conflict)."""
    eff = {t.s: t.o for t in triples if t.p == NS.DD + "effectiveDate"}
    exp = {t.s: t.o for t in triples if t.p == NS.DD + "expiryDate"}
    violations = [s for s in eff if s in exp and eff[s] > exp[s]]
    assert not violations, f"effectiveDate after expiryDate for: {violations}"


def test_executive_contract_yields_person_partyto(triples: list) -> None:
    """At least one Anstellungsvertrag yields a Person who is partyTo a
    contract, and that Person holds a fully-specified Position (SHACL)."""
    party_to = [t for t in triples if t.p == NS.DD + "partyTo"]
    assert party_to, "expected at least one partyTo link from an exec contract"
    persons = {t.s for t in triples
               if t.p == NS.RDF + "type" and t.o == NS.DD + "Person"}
    holders = {t.s for t in triples if t.p == NS.DD + "holdsPosition"}
    for t in party_to:
        assert t.s in persons, f"partyTo subject {t.s} is not a Person"
        assert t.s in holders, f"Person {t.s} holds no Position (SHACL break)"
        assert "contract/" in t.o, f"partyTo target is not a contract: {t.o}"
