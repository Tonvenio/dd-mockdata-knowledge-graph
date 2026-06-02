"""Filename extractor — entity & document references from file *names* only.

This pass never opens a file: it is fast, high-precision and derives structural
facts straight from the corpus naming conventions. It produces three kinds of
output:

1. **Document index** — one ``dd:DocumentReference`` per corpus file (the same
   ``dd:doc/{path}`` node the RDF builder links provenance to), carrying
   ``dd:filePath``, ``dd:docType`` and ``dd:documentOrg``. This is the bulk of
   the KG and the backbone for RAG-style retrieval.
2. **Entities** — ``dd:EmploymentContract`` (+ ``dd:Person`` / ``dd:Position``)
   from ``AV_*`` / ``*_Arbeitsvertrag_*`` names, and ``dd:Patent`` stubs from
   ``Patent_NN`` / ``PAT_NNN`` / ``IP_NNN_Patent_DE…`` names. The patent stubs
   share ``ids.patent_key`` with the ``patents`` extractor so the deep parse
   enriches the same node.
3. **Events** — board / shareholder / works-council meetings, OEM QBRs and
   transfer-pricing files.

Confidence is 0.95 — the filename is structural but ~5 % of files are misfiled
in the original generator.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from .. import ids
from ..model import Triple, Entity, NS
from ..corpus import Corpus
from . import _common as c

CONF = 0.95
_D = NS.DD


def _t(local: str) -> str:
    return _D + local


# Map a filename to a coarse document class.
_DOC_RULES = [
    (re.compile(r"(?:^AV_|^HR_\d|Arbeitsvertrag|Anstellungsvertrag)", re.I), "employment"),
    (re.compile(r"Covenant_Compliance", re.I),                "covenant"),
    (re.compile(r"Konsortialkredit",    re.I),                "loan"),
    (re.compile(r"^NDA_|Vertraulichkeitsver", re.I),          "nda"),
    (re.compile(r"Liefervertrag|Rahmenvertrag|Rahmenliefer|KD_\d+_Vertrag|LF_\w*Rahmen", re.I), "supply"),
    (re.compile(r"Mietvertrag",         re.I),                "lease"),
    (re.compile(r"^Patent_\d|^PAT_\d|IP_\d+_Patent", re.I),   "patent"),
    (re.compile(r"Vorstand_Bestellung|Vorstandsbestellung", re.I), "appointment"),
    (re.compile(r"HV_Protokoll",        re.I),                "shareholder-meeting"),
    (re.compile(r"AR_Sitzungsprotokoll|Aufsichtsrat", re.I),  "board-meeting"),
    (re.compile(r"QBR",                 re.I),                "review"),
    (re.compile(r"^BR_.*Protokoll|Betriebsrat", re.I),        "works-council"),
    (re.compile(r"TP_LocalFile",        re.I),                "transfer-pricing"),
    (re.compile(r"^8D_",                re.I),                "quality-8d"),
]


# Contract docTypes that get a first-class typed Contract node (enriched by
# the contracts extractor) keyed on the same contract_from_path URI.
_CONTRACT_CLASS = {
    "supply": "SupplyContract",
    "nda": "NDA",
    "loan": "LoanFacility",
    "lease": "LeaseContract",
}


def _doc_type(stem: str, suffix: str) -> str:
    for rx, label in _DOC_RULES:
        if rx.search(stem):
            return label
    return "spreadsheet" if suffix.lower() == ".xlsx" else "document"


class FilenameExtractor:
    name = "filename"

    def __init__(self, corpus: Corpus) -> None:
        self.corpus = corpus

    # ── public API ────────────────────────────────────────────────────
    def extract(self) -> Iterable[Triple]:
        for dataset, root in self.corpus.datasets.items():
            if not root.exists():
                continue
            short = c.DATASET_ORG_SHORT[dataset]
            org_uri = ids.company(short)
            for path in sorted(root.rglob("*")):
                if path.suffix.lower() not in (".docx", ".xlsx", ".pdf"):
                    continue
                rel = self.corpus.relpath(path)
                stem = path.stem
                dtype = _doc_type(stem, path.suffix)
                # PDFs only enter the index if they carry an entity (patents);
                # otherwise they'd bloat the index without docx-level structure.
                if path.suffix.lower() == ".pdf" and dtype != "patent":
                    continue
                yield from self._document(rel, stem, dtype, org_uri)

                if dtype == "employment":
                    yield from self._employment(rel, stem, short, org_uri)
                elif dtype in _CONTRACT_CLASS:
                    yield from self._contract_stub(rel, stem, dtype)
                elif dtype == "patent":
                    yield from self._patent(rel, stem, dataset, short, org_uri)
                elif dtype in ("board-meeting", "shareholder-meeting",
                               "works-council", "review"):
                    yield from self._event(rel, stem, dtype, short, org_uri)
                elif dtype == "transfer-pricing":
                    yield from self._transfer_pricing(rel, stem, org_uri)

    # ── document index ────────────────────────────────────────────────
    def _document(self, rel: str, stem: str, dtype: str, org_uri: str) -> Iterable[Triple]:
        u = ids.document_ref(rel)
        yield Triple(u, NS.RDF + "type", _t("DocumentReference"), rel, None, CONF)
        yield Triple(u, NS.RDFS + "label", stem, rel, None, CONF)
        yield Triple(u, _t("filePath"), rel, rel, None, CONF)
        yield Triple(u, _t("docType"), dtype, rel, None, CONF)
        yield Triple(u, _t("documentOrg"), org_uri, rel, None, CONF)

    # ── contract stubs (type + label; contracts.py adds dates/volume) ──
    def _contract_stub(self, rel: str, stem: str, dtype: str) -> Iterable[Triple]:
        u = ids.contract_from_path(rel)
        yield Triple(u, NS.RDF + "type", _t(_CONTRACT_CLASS[dtype]), rel, None, CONF)
        yield Triple(u, NS.RDFS + "label", stem.replace("_", " "), rel, None, CONF)

    # ── employment ────────────────────────────────────────────────────
    def _employment(self, rel: str, stem: str, short: str, org_uri: str) -> Iterable[Triple]:
        name, role = _split_employee(stem)
        if not name:
            return
        contract = ids.contract_from_path(rel)
        yield Triple(contract, NS.RDF + "type", _t("EmploymentContract"), rel, None, CONF)
        yield Triple(contract, NS.RDFS + "label", f"Arbeitsvertrag – {name}", rel, None, CONF)
        d = c.first_date(stem)
        if d:
            yield Triple(contract, _t("effectiveDate"), d, rel, None, CONF)
        yield Triple(contract, _t("counterpartyOf"), org_uri, rel, None, CONF)
        yield from c.person_with_position(name, role or "Mitarbeiter", short, org_uri, rel, CONF)
        yield Triple(ids.person(c.clean_person_name(name)), _t("partyTo"), contract, rel, None, CONF)

    # ── patents ───────────────────────────────────────────────────────
    def _patent(self, rel: str, stem: str, dataset: str, short: str, org_uri: str) -> Iterable[Triple]:
        m_rea = re.match(r"Patent_(\d+)", stem, re.I)
        m_btp = re.match(r"PAT_(\d+)", stem, re.I)
        m_mmb = re.match(r"IP_\d+_Patent_([A-Z]{2}\d+)", stem, re.I)
        if m_rea:
            nn = m_rea.group(1)
            u = ids.patent_key("REA", nn)
            label = f"Patent REA-{nn}"
            jurisdiction = "EP"
            yield from self._patent_base(u, label, jurisdiction, org_uri, rel)
            mj = re.search(r"Bescheid_(EPA|USPTO|CNIPA|DPMA)", stem, re.I)
            if mj:
                juris = {"epa": "EP", "uspto": "US", "cnipa": "CN", "dpma": "DE"}[mj.group(1).lower()]
                yield Triple(u, _t("jurisdiction"), juris, rel, None, CONF)
            mfee = re.search(r"Jahresgebuehr_(\d{4})", stem, re.I)
            if mfee:
                yield Triple(u, _t("annualFeeYear"), int(mfee.group(1)), rel, None, CONF)
        elif m_btp:
            nnn = m_btp.group(1)
            u = ids.patent_key("BTP", nnn)
            yield from self._patent_base(u, f"Patent BTP-{nnn}", "DE", org_uri, rel)
            ms = re.search(r"Status_(Erteilt|Angemeld\w*|Provisio\w*|Zurueck\w*)", stem, re.I)
            if ms:
                status = {"erteilt": "Erteilt", "angemeld": "Angemeldet",
                          "provisio": "Provisional", "zurueck": "Zurückgezogen"}
                key = ms.group(1).lower()[:8]
                yield Triple(u, _t("patentStatus"),
                             next((v for k, v in status.items() if key.startswith(k)), "Angemeldet"),
                             rel, None, CONF)
        elif m_mmb:
            filing = m_mmb.group(1).upper()
            u = ids.patent(filing)
            yield from self._patent_base(u, f"Patent {filing}", "DE", org_uri, rel)
            yield Triple(u, _t("filingNumber"), filing, rel, None, CONF)

    def _patent_base(self, u: str, label: str, juris: str, org_uri: str, rel: str) -> Iterable[Triple]:
        yield Triple(u, NS.RDF + "type", _t("Patent"), rel, None, CONF)
        yield Triple(u, NS.RDFS + "label", label, rel, None, CONF)
        yield Triple(u, _t("jurisdiction"), juris, rel, None, CONF)
        yield Triple(u, _t("assignee"), org_uri, rel, None, CONF)

    # ── events ────────────────────────────────────────────────────────
    def _event(self, rel: str, stem: str, dtype: str, short: str, org_uri: str) -> Iterable[Triple]:
        cls = {"board-meeting": "BoardMeeting", "shareholder-meeting": "ShareholderMeeting",
               "works-council": "WorksCouncilMeeting", "review": "ReviewEvent"}[dtype]
        period = "-".join(re.findall(r"(20\d{2}|Q[1-4])", stem)) or stem
        u = ids.event_ref(dtype, short, period)
        yield Triple(u, NS.RDF + "type", _t(cls), rel, None, CONF)
        yield Triple(u, NS.RDFS + "label", stem.replace("_", " "), rel, None, CONF)
        yield Triple(u, _t("eventOrg"), org_uri, rel, None, CONF)
        # QBR: link to the product whose code appears in the filename
        if dtype == "review":
            mp = re.search(r"(ICP-3|BMS-12|ADAS-V4D|ECU-900|LightCtrl-7)", stem)
            if mp:
                yield Triple(u, _t("relatesTo"), ids.product(mp.group(1)), rel, None, CONF)

    # ── transfer pricing ──────────────────────────────────────────────
    def _transfer_pricing(self, rel: str, stem: str, org_uri: str) -> Iterable[Triple]:
        u = ids.document_ref(rel)
        yield Triple(u, NS.RDF + "type", _t("TransferPricingFile"), rel, None, CONF)
        m = re.search(r"TP_LocalFile_([A-Z]{3})", stem, re.I)
        if m:
            yield Triple(u, _t("documentOrg"), ids.company(m.group(1).upper()), rel, None, CONF)


# ── employee name/role splitting ──────────────────────────────────────────
_TITLES = {"dr", "dr.", "prof", "prof.", "dipl.-ing.", "dipl."}


def _split_employee(stem: str) -> tuple[str | None, str | None]:
    """Return (name, role) parsed from an employment filename stem."""
    # Form A: "<prefix>_Arbeitsvertrag_<Name>" / "<prefix>_Anstellungsvertrag_<Name>"
    m = re.search(r"(?:Arbeitsvertrag|Anstellungsvertrag)_(.+)$", stem, re.I)
    if m:
        return c.clean_person_name(m.group(1)), None
    # Form B: "AV_NNN_<[Title_]First_Last>_<Role...>[_date]"
    m = re.match(r"AV_\d+_(.+)$", stem, re.I)
    if m:
        toks = m.group(1).split("_")
        # name = (optional leading title) + given + surname = 2 real name tokens
        n = 0
        real = 0
        while n < len(toks) and real < 2:
            if toks[n].lower().rstrip(".") not in {t.rstrip(".") for t in _TITLES}:
                real += 1
            n += 1
        name = c.clean_person_name(" ".join(toks[:n]))
        role_raw = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", " ".join(toks[n:]))
        role = c.clean_person_name(role_raw) or None
        return name, role
    return None, None
