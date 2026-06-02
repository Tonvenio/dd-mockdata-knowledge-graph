"""Patents extractor — deep parse of Brennhagen Patentschrift documents.

Opens ``roehrig_large/**/Patent_NN_*.docx`` and, for every file that is an
actual Patentschrift (carries an *Aktenzeichen*), enriches the patent node that
``filename`` already minted (``ids.patent_key("REA", NN)``) with:

  * ``dd:filingNumber``  — e.g. "EP 10241096.4"
  * ``dd:jurisdiction``  — EP / DE / US / CN / JP / WO (from the Aktenzeichen)
  * ``dd:patentTitle``   — the title after "Patentschrift Nr. NN – …"
  * ``dd:inventedBy``    — one dd:Person per name in the "Erfinder" table cell
  * ``dd:assignee``      — the "Anmelder" company (default Brennhagen AG)
  * ``dd:relatesTo``     — product code(s) referenced in the body

Provenance is the file path; confidence 0.9 (deep parse of generated prose).
"""
from __future__ import annotations

import re
from typing import Iterable

from .. import ids
from ..model import Triple, NS
from ..corpus import Corpus
from . import _common as c

CONF = 0.9
_D = NS.DD
_PRODUCTS = ("ICP-3", "BMS-12", "ADAS-V4D", "ECU-900", "LightCtrl-7")
_JURIS_RE = re.compile(r"\b(EP|DE|US|CN|JP|WO)\b")


def _t(local: str) -> str:
    return _D + local


class PatentsExtractor:
    name = "patents"

    def __init__(self, corpus: Corpus) -> None:
        self.corpus = corpus

    def extract(self) -> Iterable[Triple]:
        root = self.corpus.datasets["roehrig_large"]
        if not root.exists():
            return
        org_uri = ids.company("REA")
        for path in sorted(root.rglob("Patent_*.docx")):
            m = re.match(r"Patent_(\d+)", path.stem, re.I)
            if not m:
                continue
            try:
                doc = c.open_doc(path)
            except Exception:
                continue
            title = c.heading2(doc) or ""
            if "Patentschrift" not in title:
                continue                       # Bescheid / Jahresgebuehr / etc.
            yield from self._patentschrift(doc, m.group(1), title,
                                           self.corpus.relpath(path), org_uri)

    def _patentschrift(self, doc, nn: str, title: str, rel: str,
                       org_uri: str) -> Iterable[Triple]:
        u = ids.patent_key("REA", nn)
        # node is already typed by `filename`; (re)assert type for standalone use
        yield Triple(u, NS.RDF + "type", _t("Patent"), rel, None, CONF)
        clean_title = c.title_tail(title) or title
        yield Triple(u, _t("patentTitle"), clean_title, rel, None, CONF)

        paras = [text for _, _, text in c.iter_paragraphs(doc)]
        body = "\n".join(paras)

        # Aktenzeichen line: "Aktenzeichen EP 10243411.6, IPC-Klasse …"
        filing, juris = self._filing(doc, body)
        if filing:
            yield Triple(u, _t("filingNumber"), filing, rel, None, CONF)
        if juris:
            yield Triple(u, _t("jurisdiction"), juris, rel, None, CONF)

        # table fields (Feld | Inhalt)
        fields = self._table_fields(doc)
        anmelder = fields.get("anmelder", "")
        assignee = org_uri if (not anmelder or "Brennhagen" in anmelder or "Brennhagen" in anmelder) \
            else ids.company(anmelder.split(",")[0].strip())
        yield Triple(u, _t("assignee"), assignee, rel, None, CONF)

        for inv in self._inventors(fields.get("erfinder", "")):
            yield from c.person_with_position(inv, "Erfinder", "REA", org_uri, rel, CONF)
            yield Triple(u, _t("inventedBy"), ids.person(c.clean_person_name(inv)),
                         rel, None, CONF)

        for prod in sorted({p for p in _PRODUCTS if p in body}):
            yield Triple(u, _t("relatesTo"), ids.product(prod), rel, None, CONF)

    # ── helpers ───────────────────────────────────────────────────────
    def _filing(self, doc, body: str) -> tuple[str | None, str | None]:
        m = re.search(r"Aktenzeichen\s+((EP|DE|US|CN|JP|WO)\s*[\d.\s/]+\d)", body)
        if m:
            num = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(",")
            return num, m.group(2)
        # fall back to the table's Aktenzeichen cell
        fields = self._table_fields(doc)
        for k, v in fields.items():
            if k.startswith("aktenzeichen") and v:
                jm = _JURIS_RE.search(v)
                return v.strip(), (jm.group(1) if jm else None)
        return None, None

    def _table_fields(self, doc) -> dict[str, str]:
        out: dict[str, str] = {}
        for table in doc.tables:
            for row in table.rows:
                if len(row.cells) >= 2:
                    key = row.cells[0].text.strip().lower()
                    val = row.cells[1].text.strip()
                    if key and key not in out:
                        out[key] = val
        return out

    def _inventors(self, cell: str) -> list[str]:
        names: list[str] = []
        for part in re.split(r"[;]", cell):
            part = re.sub(r"\([^)]*\)", "", part)          # drop "(REG)" affiliation
            part = re.sub(r"\b(et al\.?|u\.\s*a\.)\b", "", part, flags=re.I)
            name = c.clean_person_name(part)
            if name and len(name.split()) >= 2:
                names.append(name)
        return names
