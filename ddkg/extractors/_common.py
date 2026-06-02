"""Shared helpers for the document-level extractors.

All v0.2 extractors build on these primitives so URI schemes, German-date
parsing, EUR parsing and the PII guard stay identical across files. Keep this
module dependency-light (only stdlib + python-docx).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Iterable, Iterator

from .. import ids
from ..model import Triple, Entity, NS

# ── German month parsing ──────────────────────────────────────────────────
# Documents use both the umlaut form ("März") and the ASCII-folded form
# ("Maerz") that the regen pass produced. Accept both.
_MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5,
    "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
    "november": 11, "dezember": 12,
}
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))

_DE_DATE_RE = re.compile(
    rf"\b(\d{{1,2}})\.\s*({_MONTH_ALT})\s+(\d{{4}})\b", re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def all_dates(text: str) -> list[date]:
    """Return every German-long-form or ISO date found in ``text`` (in order)."""
    out: list[date] = []
    for m in _DE_DATE_RE.finditer(text):
        try:
            out.append(date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1))))
        except ValueError:
            pass
    for m in _ISO_DATE_RE.finditer(text):
        try:
            out.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            pass
    return out


def first_date(text: str) -> date | None:
    ds = all_dates(text)
    return ds[0] if ds else None


# ── EUR amount parsing ────────────────────────────────────────────────────
_NUM = r"\d[\d.,]*\d|\d"
_EUR_BEFORE = re.compile(
    rf"({_NUM})\s*(Mrd\.?|Mio\.?|Tsd\.?)?\s*(?:EUR|€|Euro)", re.IGNORECASE)
_EUR_AFTER = re.compile(
    rf"(?:EUR|€)\s*({_NUM})\s*(Mrd\.?|Mio\.?|Tsd\.?)?", re.IGNORECASE)
_SCALE = {"mrd": 1_000_000_000, "mio": 1_000_000, "tsd": 1_000}


def parse_number(s: str) -> float:
    """Parse a German/English formatted number string to a float.

    Handles ``1.400.000`` → 1400000, ``350,000`` → 350000, ``75.6`` → 75.6,
    ``3,0`` → 3.0, ``1.234,56`` → 1234.56, ``412.50`` → 412.5.
    """
    s = s.strip()
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):        # German: 1.234,56
            s = s.replace(".", "").replace(",", ".")
        else:                                   # English: 1,234.56
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) == 3:
            s = s.replace(",", "")              # 350,000 -> 350000 (thousands)
        else:
            s = s.replace(",", ".")             # 3,0 -> 3.0 (decimal)
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
            s = s.replace(".", "")              # 1.400.000 -> 1400000
        elif len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3:
            s = s.replace(".", "")              # 46.000 -> 46000
        # else keep as decimal (75.6, 412.50)
    return float(s)


def _scaled(num: str, scale: str | None) -> float:
    val = parse_number(num)
    if scale:
        val *= _SCALE.get(scale.lower().rstrip("."), 1)
    return val


def find_eur(text: str) -> float | None:
    """First plausible EUR amount in ``text`` (handles Mio./Mrd. and EUR on
    either side of the number)."""
    amounts = find_eur_amounts(text)
    return amounts[0] if amounts else None


def find_eur_amounts(text: str) -> list[float]:
    out: list[float] = []
    for m in _EUR_BEFORE.finditer(text):
        try:
            out.append(_scaled(m.group(1), m.group(2)))
        except ValueError:
            pass
    if not out:
        for m in _EUR_AFTER.finditer(text):
            try:
                out.append(_scaled(m.group(1), m.group(2)))
            except ValueError:
                pass
    return out


# ── PII guard ─────────────────────────────────────────────────────────────
# Real-person names that were rewritten to fictional equivalents during the
# corpus PII clean-up. They must NEVER appear in the KG. If an extractor ever
# encounters one (e.g. in an un-regenerated PDF), it is mapped to the
# fictional replacement via REAL_TO_FICTIONAL.
REAL_TO_FICTIONAL = {
    "Carsten Breitfeld": "Carsten Brendel",
    "Lutz Eckstein": "Ludwig Eckhardt",
    "Markus Lienkamp": "Martin Lindenmann",
    "Sebastian Schreiber": "Sebastian Strohmeier",
    "Frank Weber": "Frank Wendler",
    "Andreas Reschka": "Andreas Rehbein",
}
PII_FORBIDDEN = set(REAL_TO_FICTIONAL)


def scrub_name(name: str) -> str:
    """Map any leftover real-person name onto its fictional replacement."""
    out = name
    for real, fake in REAL_TO_FICTIONAL.items():
        if real in out:
            out = out.replace(real, fake)
    return out


# ── name cleaning ─────────────────────────────────────────────────────────
_NAME_NOISE = re.compile(r"\b(FINAL|ENTWURF|DRAFT|WIP|rev|v\d+|kopie|copy)\b", re.IGNORECASE)
_TITLE_TOKENS = {"dr", "dr.", "prof", "prof.", "dipl.-ing.", "dipl.-kfm.",
                 "dipl.", "ing.", "mba", "llm", "ll.m."}


def clean_person_name(raw: str) -> str:
    """Normalise a person name pulled from a filename or title.

    Replaces underscores with spaces, drops file-noise tokens and trailing
    standalone digits, collapses whitespace and scrubs any PII name.
    """
    s = raw.replace("_", " ")
    s = _NAME_NOISE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" -–—,.")
    # drop standalone numeric tokens (e.g. "Claudia Fischer 90")
    s = " ".join(tok for tok in s.split() if not tok.isdigit())
    return scrub_name(s).strip()


# ── docx iteration helpers ────────────────────────────────────────────────
def open_doc(path):
    """Open a .docx, returning a python-docx Document (raises on failure)."""
    from docx import Document
    return Document(str(path))


def iter_paragraphs(doc) -> Iterator[tuple[int, str, str]]:
    """Yield (index, style_name, text) for every non-empty paragraph."""
    for i, p in enumerate(doc.paragraphs):
        t = p.text.strip()
        if t:
            yield i, p.style.name, t


def heading2(doc) -> str | None:
    """The level-2 heading (the document title) of a write_doc() document."""
    for _, style, text in iter_paragraphs(doc):
        if style.startswith("Heading 2"):
            return text
    return None


def title_tail(title: str) -> str | None:
    """Text after the last en/em-dash in a title (party / person name).

    ``"Rahmen-Liefervertrag – Schunk GmbH & Co. KG"`` → ``"Schunk GmbH & Co. KG"``
    ``"Anstellungsvertrag – Anna Müller – Vorstandsvorsitzende"`` → ``"Vorstandsvorsitzende"``
    """
    parts = re.split(r"\s[–—-]\s", title)
    return parts[-1].strip() if len(parts) > 1 else None


# ── person + position emission (SHACL-safe) ───────────────────────────────
def person_with_position(name: str, role_label: str, org_short: str,
                         org_uri: str, src: str, conf: float = 0.95,
                         paragraph: int | None = None) -> Iterable[Triple]:
    """Emit a dd:Person + dd:Role + dd:Position triple set.

    Mirrors ``CanonicalExtractor._person_in_role`` so that *every* Person the
    document extractors mint also satisfies the SHACL requirement of holding at
    least one fully-specified Position (positionAt + positionRole). Always use
    this helper instead of minting a bare dd:Person.
    """
    name = clean_person_name(name)
    if not name:
        return
    p_uri = ids.person(name)
    r_uri = ids.role(role_label)
    pos_uri = ids.position(name, role_label, org_short)
    yield from Entity(p_uri, NS.DD + "Person", name, source=src).triples()
    yield from Entity(r_uri, NS.DD + "Role", role_label, source=src).triples()
    yield from Entity(pos_uri, NS.DD + "Position",
                      f"{name} — {role_label} @ {org_short}", source=src).triples()
    yield Triple(p_uri, NS.DD + "holdsPosition", pos_uri, src, paragraph, conf)
    yield Triple(pos_uri, NS.DD + "positionRole", r_uri, src, paragraph, conf)
    yield Triple(pos_uri, NS.DD + "positionAt", org_uri, src, paragraph, conf)


# ── canonical company short-codes per dataset ─────────────────────────────
DATASET_ORG_SHORT = {
    "mueller_small": "MMB",
    "biotech_medium": "BTP",
    "roehrig_large": "REA",
}


def dataset_of(rel_path: str) -> str | None:
    head = rel_path.replace("\\", "/").split("/", 1)[0]
    return head if head in DATASET_ORG_SHORT else None
