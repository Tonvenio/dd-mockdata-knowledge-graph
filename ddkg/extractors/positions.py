"""Positions extractor — Vorstand appointments + governance event dates (REA).

Parses three families of files in the listed-AG dataset (``roehrig_large``):

* ``REA_Vorstand_Bestellung_*.docx`` — a Vorstand member's appointment deed.
  The level-2 heading carries the person name and the board role; the body may
  carry an appointment date (``Bestellung zum`` / ``mit Wirkung zum`` / …).
  We mint the Vorstand Position (positionAt REA) and, where a date is found,
  attach ``dd:appointedOn``.
* ``REA_HV_Protokoll_*.docx`` — annual general meeting minutes. The filename
  extractor (runs earlier) already minted the ``dd:ShareholderMeeting`` node;
  here we add its ``dd:eventDate`` from the heading.
* ``REA_AR_Sitzungsprotokoll_*.docx`` — supervisory-board meeting minutes. The
  filename extractor minted the ``dd:BoardMeeting``; here we add ``dd:eventDate``
  from the first real date in the body.

Event URIs are recomputed with the *same* ``period`` rule the filename
extractor uses so the dates land on the existing nodes.
"""
from __future__ import annotations

import re
from typing import Iterable

from . import _common as c
from .. import ids
from ..model import Triple, NS
from ..corpus import Corpus

# Spans that flag an appointment date; we prefer a date found near one of these.
_APPOINT_HINTS = ("mit Wirkung zum", "Bestellung zum", "Amtsbeginn", "beginnt am")
# Dash splitter for the level-2 title (en/em-dash or hyphen, space-padded).
_DASH = re.compile(r"\s[–—-]\s")
# Period tokens shared with the filename extractor.
_PERIOD_RE = re.compile(r"(20\d{2}|Q[1-4])")


class PositionsExtractor:
    name = "positions"

    def __init__(self, corpus: Corpus) -> None:
        self.corpus = corpus

    # ── public API ────────────────────────────────────────────────────
    def extract(self) -> Iterable[Triple]:
        root = self.corpus.datasets["roehrig_large"]
        if not root.exists():
            return
        for path in sorted(root.rglob("REA_Vorstand_Bestellung_*.docx")):
            yield from self._bestellung(path)
        for path in sorted(root.rglob("REA_HV_Protokoll_*.docx")):
            yield from self._hv(path)
        for path in sorted(root.rglob("REA_AR_Sitzungsprotokoll_*.docx")):
            yield from self._ar(path)

    # ── Vorstand Bestellung ───────────────────────────────────────────
    def _bestellung(self, path) -> Iterable[Triple]:
        rel = self.corpus.relpath(path)
        doc = c.open_doc(path)
        title = c.heading2(doc)
        if not title:
            return
        parts = _DASH.split(title)
        if len(parts) < 3:
            return
        name = parts[1].strip()
        role = parts[2].strip()
        if not name or not role:
            return

        org_uri = ids.company("REA")
        yield from c.person_with_position(name, role, "REA", org_uri, rel, 0.9)

        appoint = self._appointment_date(doc)
        if appoint is not None:
            pos_uri = ids.position(c.clean_person_name(name), role, "REA")
            yield Triple(pos_uri, NS.DD + "appointedOn", appoint, rel, confidence=0.85)

    def _appointment_date(self, doc):
        """First date near an appointment hint, else first date in the body."""
        spans: list[str] = []
        for _, _, text in c.iter_paragraphs(doc):
            spans.append(text)
            if any(h in text for h in _APPOINT_HINTS):
                d = c.first_date(text)
                if d is not None:
                    return d
        return c.first_date(" ".join(spans))

    # ── HV Protokoll (ShareholderMeeting) ─────────────────────────────
    def _hv(self, path) -> Iterable[Triple]:
        rel = self.corpus.relpath(path)
        doc = c.open_doc(path)
        title = c.heading2(doc) or ""
        hv_date = c.first_date(title)
        if hv_date is None:
            return
        period = "-".join(_PERIOD_RE.findall(path.stem))
        event_uri = ids.event_ref("shareholder-meeting", "REA", period)
        yield Triple(event_uri, NS.DD + "eventDate", hv_date, rel, confidence=0.9)

    # ── AR Sitzungsprotokoll (BoardMeeting) ───────────────────────────
    def _ar(self, path) -> Iterable[Triple]:
        rel = self.corpus.relpath(path)
        doc = c.open_doc(path)
        body = " ".join(t for _, _, t in c.iter_paragraphs(doc))
        meeting_date = c.first_date(body)
        if meeting_date is None:
            return
        period = "-".join(_PERIOD_RE.findall(path.stem))
        event_uri = ids.event_ref("board-meeting", "REA", period)
        yield Triple(event_uri, NS.DD + "eventDate", meeting_date, rel, confidence=0.85)
