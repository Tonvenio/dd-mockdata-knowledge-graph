"""Stable URI minting for entities.

We use deterministic slug-based URIs so a re-run yields the same KG.
"""
from __future__ import annotations
import re
import unicodedata
from .model import NS


def _slug(s: str) -> str:
    """Lowercase ASCII slug; deterministic."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "x"


def company(short_or_name: str) -> str:
    return f"{NS.DD}org/{_slug(short_or_name)}"


def person(name: str) -> str:
    return f"{NS.DD}person/{_slug(name)}"


def position(person_name: str, role: str, org_short: str) -> str:
    return f"{NS.DD}position/{_slug(person_name)}--{_slug(role)}--{_slug(org_short)}"


def role(name: str) -> str:
    return f"{NS.DD}role/{_slug(name)}"


def contract(kind: str, parties_short: list[str], identifier: str) -> str:
    parties = "_".join(_slug(p) for p in parties_short)
    return f"{NS.DD}contract/{_slug(kind)}/{parties}/{_slug(identifier)}"


def patent(filing_number: str) -> str:
    return f"{NS.DD}patent/{_slug(filing_number)}"


def product(short: str) -> str:
    return f"{NS.DD}product/{_slug(short)}"


def covenant(loan_id: str, name: str) -> str:
    return f"{NS.DD}covenant/{_slug(loan_id)}/{_slug(name)}"


def covenant_observation(loan_id: str, name: str, period: str) -> str:
    return f"{NS.DD}covenant-obs/{_slug(loan_id)}/{_slug(name)}/{_slug(period)}"


def document_ref(rel_path: str) -> str:
    return f"{NS.DD}doc/{_slug(rel_path)}"


def contract_from_path(rel_path: str) -> str:
    """Stable contract URI keyed off the source file path.

    This is the cross-extractor coordination key: ``filename`` classifies the
    contract type from the file name while ``contracts`` opens the same file to
    add dates / volume / counterparty — both reference the *same* node because
    they derive the URI from the identical relative path.
    """
    return f"{NS.DD}contract/file/{_slug(rel_path)}"


def patent_key(dataset_short: str, num: str) -> str:
    """Stable patent URI shared by the ``filename`` and ``patents`` extractors.

    A single patent is referenced by many files (Patentschrift, Bescheid,
    Jahresgebuehr, …); keying on (dataset, running-number) collapses them onto
    one node. ``filename`` mints the stub; ``patents`` enriches the same URI.
    """
    return f"{NS.DD}patent/{_slug(dataset_short)}-{_slug(str(num))}"


def event_ref(kind: str, org_short: str, identifier: str) -> str:
    """A meta event node (board meeting, QBR, HV, works-council meeting)."""
    return f"{NS.DD}event/{_slug(kind)}/{_slug(org_short)}/{_slug(identifier)}"
