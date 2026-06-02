"""Smoke tests for the filename extractor.

Skips automatically if dd-mockdata is not checked out next to this repo.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import pytest

from ddkg.corpus import Corpus
from ddkg.extractors.filename import FilenameExtractor
from ddkg.model import NS

CORPUS_DEFAULT = Path(__file__).resolve().parent.parent.parent / "dd-mockdata"


@pytest.fixture(scope="module")
def triples():
    if not (CORPUS_DEFAULT / "enhance_lib.py").exists():
        pytest.skip(f"dd-mockdata not found at {CORPUS_DEFAULT}")
    return list(FilenameExtractor(Corpus(CORPUS_DEFAULT)).extract())


def _types(triples):
    return Counter(t.o for t in triples if t.p == NS.RDF + "type")


def test_document_index_covers_corpus(triples) -> None:
    docs = _types(triples)[NS.DD + "DocumentReference"]
    assert docs >= 5000, f"expected a large document index, got {docs}"


def test_every_document_has_filepath_and_doctype(triples) -> None:
    docs = {t.s for t in triples if t.o == NS.DD + "DocumentReference"
            and t.p == NS.RDF + "type"}
    with_path = {t.s for t in triples if t.p == NS.DD + "filePath"}
    with_type = {t.s for t in triples if t.p == NS.DD + "docType"}
    assert not (docs - with_path), "some DocumentReference lacks dd:filePath"
    assert not (docs - with_type), "some DocumentReference lacks dd:docType"


def test_employment_contracts_and_patents(triples) -> None:
    typ = _types(triples)
    assert typ[NS.DD + "EmploymentContract"] >= 200
    assert typ[NS.DD + "Patent"] >= 30


def test_every_person_is_position_holder(triples) -> None:
    persons = {t.s for t in triples
               if t.p == NS.RDF + "type" and t.o == NS.DD + "Person"}
    holders = {t.s for t in triples if t.p == NS.DD + "holdsPosition"}
    assert not (persons - holders), "filename extractor minted a position-less Person"


def test_no_invalid_uri_chars(triples) -> None:
    # subjects/predicates and URI objects must never contain spaces (Turtle-safe)
    for t in triples:
        assert " " not in t.s and " " not in t.p
        if isinstance(t.o, str) and t.o.startswith("http"):
            assert " " not in t.o, f"space in object URI: {t.o}"
