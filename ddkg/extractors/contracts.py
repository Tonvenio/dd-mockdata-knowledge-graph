"""Contracts extractor — parses dates, volumes and counterparties from the
contract .docx files (supply / NDA / loan / executive employment).

This extractor *enriches* the contract node that the ``filename`` extractor
classifies and labels: both derive the contract URI from the identical relative
path via :func:`ids.contract_from_path`, so they reference the same node. We
therefore emit **only** the parsed facts here (effectiveDate, expiryDate,
volumeEur, counterpartyOf, and — for executive contracts — the employee Person
+ partyTo link). We never emit ``rdf:type`` / ``rdfs:label`` for the contract:
the filename extractor owns those.

Counterparties are reconciled against the canonical whitelist pulled from
``corpus.facts()`` (customers / suppliers / distributors / clinics / OEM
customers). A canonical match reuses the existing company node at confidence
0.9; an unrecognised party is minted as a fresh dd:Counterparty at 0.6.

All emitted facts carry ``source=rel`` provenance and, where a specific
paragraph drove the value, the paragraph index.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Iterable

from . import _common as c
from .. import ids
from ..corpus import Corpus
from ..model import Triple, Entity, NS


# Words that mark the owning company (never the counterparty).
_OWNER_TOKENS = ("müller", "mueller", "biotech", "röhrig", "roehrig",
                 "mmb", "btp", "rea")

# Party-role labels that introduce a named party on a "Label: <Company>" line.
_PARTY_LABELS = ("Lieferantin", "Lieferant", "Empfaengerin", "Empfänger",
                 "Empfaenger", "Auftraggeberin", "Auftraggeber",
                 "Kundin", "Kunde", "Abnehmerin", "Abnehmer",
                 "Bestellerin", "Besteller")
_PARTY_LINE_RE = re.compile(
    r"^\s*(?:" + "|".join(_PARTY_LABELS) + r")\s*[:\n]", re.IGNORECASE)
# Numbered parties block: "1. Müller … GmbH, …" / "2. ThyssenKrupp … AG, …".
_NUM_PARTY_RE = re.compile(r"^\s*\d+\.\s+(.+)$")
# Leading German articles that occasionally precede a party name.
_LEAD_ARTICLE_RE = re.compile(r"^(?:der|die|das|den|dem)\s+", re.IGNORECASE)

# Volume context words (an EUR amount on such a line is a contract / annual
# volume, not a unit price, interest rate or insurance cover).
_VOLUME_WORDS = ("Volumen", "Auftragsvolumen", "Jahreshorizont", "bezieht",
                 "Jahresvolumen", "Auftragswert", "Vertragswert",
                 "Gesamtvolumen")
# Lines whose EUR figure is *not* a volume (unit prices, surcharges, …).
_VOLUME_EXCLUDE = ("Stueckpreis", "Stückpreis", "pro Stueck", "pro Stück",
                   "je Stueck", "je Stück", "EXW", "Skonto")

# Signature / closing line that carries the contract date — either the
# "Ort, Datum: …" label or a "<City>, den <date>" closing line.
_SIG_RE = re.compile(
    r"ort\s*,?\s*datum|^[A-ZÄÖÜ][\wäöüß.\-/ ]{1,40},\s*den\s", re.IGNORECASE)
# Employment-/appointment-start cues — the date on such a line is the contract's
# effective date (when the engagement begins), the strongest signal we have.
_START_CUE_RE = re.compile(
    r"beginnt\s+am|mit\s+Wirkung\s+(?:ab|zum)|Arbeitsverh[äa]ltnis\s+beginnt|"
    r"Vertrag\s+beginnt|Beginn\s+(?:der\s+)?(?:T[äa]tigkeit|Anstellung)|"
    r"wird\b[^.]*\bbestellt|tritt\b[^.]*\bein\b", re.IGNORECASE)
# Birth-date cues — a date on such a line must never be read as a contract date.
_BIRTH_CUE_RE = re.compile(r"geboren|geb\.|geburtsdatum|geb\s", re.IGNORECASE)
# Absolute expiry markers ("Laufzeit … bis <date>", "befristet bis <date>").
_EXPIRY_RE = re.compile(r"(?:befristet\s+bis|laufzeit[^.]*\bbis\b)",
                        re.IGNORECASE)


class ContractsExtractor:
    name = "contracts"

    def __init__(self, corpus: Corpus) -> None:
        self.corpus = corpus
        self._canonical = self._load_canonical_names()

    # ── canonical counterparty whitelist ──────────────────────────────
    def _load_canonical_names(self) -> list[str]:
        """Flatten every canonical counterparty name from the fact tables."""
        f = self.corpus.facts()
        names: list[str] = []
        m, b, r = f["mueller"], f["biotech"], f["roehrig_ag"]
        names += m.get("kunden", []) + m.get("lieferanten", [])
        names += (b.get("distributoren", []) + b.get("lieferanten", [])
                  + b.get("kliniken", []))
        names += r.get("oem_kunden", [])
        # de-dupe while preserving order
        seen: set[str] = set()
        out: list[str] = []
        for n in names:
            if n and n not in seen:
                seen.add(n)
                out.append(n)
        return out

    # ── public API ────────────────────────────────────────────────────
    def extract(self) -> Iterable[Triple]:
        for path in self.corpus.docx_files():
            kind = self._classify(path.name)
            if kind is None:
                continue
            rel = self.corpus.relpath(path)
            try:
                doc = c.open_doc(path)
            except Exception:
                continue  # unreadable docx — skip rather than crash the build
            yield from self._extract_doc(doc, rel, kind)

    # ── file classification (mirrors the filename extractor's matchers) ─
    @staticmethod
    def _classify(filename: str) -> str | None:
        n = filename.lower()
        if n.startswith("nda_") or "vertraulichkeitsver" in n:
            return "nda"
        if "konsortialkredit" in n:
            return "loan"
        if "anstellungsvertrag" in n:
            return "exec"
        if ("liefervertrag" in n or "rahmenvertrag" in n
                or "rahmenliefer" in n
                or re.search(r"kd_\d+_vertrag", n)
                or re.search(r"lf_\w*rahmenvertrag", n)):
            return "supply"
        return None

    # ── per-document extraction ────────────────────────────────────────
    def _extract_doc(self, doc, rel: str, kind: str) -> Iterable[Triple]:
        contract_uri = ids.contract_from_path(rel)
        paras = list(c.iter_paragraphs(doc))
        title = c.heading2(doc) or ""

        # 1) dates ------------------------------------------------------
        eff, eff_idx = self._effective_date(paras)
        exp, exp_idx = self._expiry_date(paras)
        # invariant: never effectiveDate AFTER expiryDate → drop expiry.
        if eff and exp and eff > exp:
            exp = None
        if eff:
            yield Triple(contract_uri, NS.DD + "effectiveDate", eff,
                         rel, eff_idx, 0.9)
        if exp:
            yield Triple(contract_uri, NS.DD + "expiryDate", exp,
                         rel, exp_idx, 0.9)

        # 2) volume -----------------------------------------------------
        vol, vol_idx = self._volume(paras)
        if vol is not None:
            yield Triple(contract_uri, NS.DD + "volumeEur", vol,
                         rel, vol_idx, 0.9)

        # 3) counterparty ----------------------------------------------
        cp_name, cp_idx = self._counterparty(title, paras)
        if cp_name:
            yield from self._emit_counterparty(contract_uri, cp_name,
                                               cp_idx, rel)

        # 4) executive employment: the employed Person ------------------
        if kind == "exec":
            yield from self._exec_person(contract_uri, title, eff, eff_idx, rel)

    # ── date helpers ───────────────────────────────────────────────────
    def _effective_date(self, paras) -> tuple[date | None, int | None]:
        """Pick the contract's effective date by priority:

          1. a line with an employment/appointment *start* cue
             ("beginnt am", "mit Wirkung ab dem", "wird … bestellt"),
          2. the signature / closing line ("Ort, Datum: …" or "<City>, den …"),
          3. the first parseable date on any line that is *not* a birth-date
             line ("… geboren am …").

        Birth-date lines are always skipped so a CV/Vita date can never be
        mistaken for the contract date.
        """
        sig: tuple[date, int] | None = None
        for i, _style, t in paras:
            is_birth = bool(_BIRTH_CUE_RE.search(t))
            if _START_CUE_RE.search(t) and not is_birth:
                d = c.first_date(t)
                if d:
                    return d, i                     # priority 1 — done
            if sig is None and _SIG_RE.search(t) and not is_birth:
                d = c.first_date(t)
                if d:
                    sig = (d, i)                    # priority 2 — remember
        if sig:
            return sig
        for i, _style, t in paras:                  # priority 3 — non-birth date
            if _BIRTH_CUE_RE.search(t):
                continue
            d = c.first_date(t)
            if d:
                return d, i
        return None, None

    def _expiry_date(self, paras) -> tuple[date | None, int | None]:
        """Only an *absolute* end date counts; a pure duration ("36 Monate")
        is ignored. We read the date that follows a "… bis" / "befristet bis"
        span on the same paragraph."""
        for i, _style, t in paras:
            m = _EXPIRY_RE.search(t)
            if not m:
                continue
            d = c.first_date(t[m.start():])
            if d:
                return d, i
        return None, None

    # ── volume helper ──────────────────────────────────────────────────
    def _volume(self, paras) -> tuple[float | None, int | None]:
        best: float | None = None
        best_idx: int | None = None
        for i, _style, t in paras:
            if "EUR" not in t and "€" not in t:
                continue
            if not any(w in t for w in _VOLUME_WORDS):
                continue
            if any(x in t for x in _VOLUME_EXCLUDE):
                continue
            v = c.find_eur(t)
            if v is not None and (best is None or v > best):
                best, best_idx = v, i
        return best, best_idx

    # ── counterparty helpers ───────────────────────────────────────────
    def _counterparty(self, title: str, paras) -> tuple[str | None, int | None]:
        """Find the party that is NOT the owning company.

        Strategy (in priority order):
          1. a labelled party line ("Lieferant: <Company>, …"),
          2. a numbered party line ("2. <Company>, …"),
          3. a title segment after " – " that looks like a company name,
          4. a "zwischen A und B" / "A und B" parties sentence.
        """
        # 1) labelled party line
        for i, _style, t in paras:
            m = _PARTY_LINE_RE.match(t)
            if not m:
                continue
            name = self._first_org(t[m.end():])
            if name and not self._is_owner(name):
                return name, i

        # 2) numbered parties block ("1. Owner …" / "2. Counterparty …")
        for i, _style, t in paras:
            m = _NUM_PARTY_RE.match(t)
            if not m:
                continue
            name = self._first_org(m.group(1))
            if name and self._looks_like_company(name) \
                    and not self._is_owner(name):
                return name, i

        # 3) title segments (supply "… – <Counterparty> [– »Scope«]"). The
        # last segment is often a »quoted« scope, so we test every segment and
        # take the first that looks like a company (skipping quoted scopes).
        for seg in re.split(r"\s[–—-]\s", title)[1:]:
            if "»" in seg or "«" in seg:
                continue  # quoted scope phrase, not a party
            cand = self._clean_org(seg)
            if cand and self._looks_like_company(cand) \
                    and not self._is_owner(cand):
                return cand, None

        # 4) "zwischen A und B" / "A und B" in the parties section
        for i, _style, t in paras:
            cand = self._from_und(t)
            if cand and not self._is_owner(cand):
                return cand, i

        return None, None

    @staticmethod
    def _first_org(text: str) -> str | None:
        """Take the first organisation token off a party value, stripping the
        address tail after the first comma / newline."""
        return ContractsExtractor._clean_org(
            re.split(r"[\n,]", text.strip(), 1)[0])

    @staticmethod
    def _clean_org(s: str) -> str:
        s = s.strip().strip("»«\"'")
        s = _LEAD_ARTICLE_RE.sub("", s)            # drop "der/die/das …"
        # drop a trailing quoted-alias artefact, e.g. "('Lieferant')".
        s = re.sub(r"\s*\(['»\"].*?['«\"]\)\s*$", "", s)
        # drop a trailing "(2023)" year artefact from a title segment.
        s = re.sub(r"\s*\(\d{4}\)\s*$", "", s)
        s = re.sub(r"\s+", " ", s)
        return s.strip(" -–—:.")

    def _from_und(self, text: str) -> str | None:
        """Parse "[zwischen] A und B …" into the non-owner side."""
        if " und " not in text:
            return None
        body = text
        mz = re.search(r"\bzwischen\b", body, re.IGNORECASE)
        if mz:
            body = body[mz.end():]
        # split on the (last) " und " connecting the two parties
        left, _, right = body.partition(" und ")
        for side in (left, right):
            name = self._clean_org(re.split(r"[\n,(]", side.strip(), 1)[0])
            # drop quoted-alias artefacts like "('Lieferant')"
            name = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
            if name and self._looks_like_company(name) \
                    and not self._is_owner(name):
                return name
        return None

    @staticmethod
    def _looks_like_company(name: str) -> bool:
        """Heuristic: a plausible company name has a legal form or is multi-word
        and not obviously a product / scope phrase."""
        if len(name) < 3 or len(name) > 90:
            return False
        legal = ("AG", "SE", "GmbH", "KG", "KGaA", "N.V.", "mbH", "e.V.",
                 "Co.", "Inc", "Ltd", "Gruppe", "Group", "Werke",
                 "Universitätsmedizin", "Universitätsklinikum", "Klinikum",
                 "Institut", "Bank")
        return any(tok in name for tok in legal)

    def _is_owner(self, name: str) -> bool:
        low = name.lower()
        return any(tok in low for tok in _OWNER_TOKENS)

    def _match_canonical(self, name: str) -> str | None:
        """Case-insensitive substring match (either direction) against the
        canonical whitelist; returns the canonical name on a hit."""
        low = name.lower()
        for canon in self._canonical:
            cl = canon.lower()
            if cl in low or low in cl:
                return canon
        return None

    def _emit_counterparty(self, contract_uri: str, name: str,
                           idx: int | None, rel: str) -> Iterable[Triple]:
        canon = self._match_canonical(name)
        if canon:
            cp_uri = ids.company(canon)
            # reuse the canonical node — no new typing needed.
            yield Triple(contract_uri, NS.DD + "counterpartyOf", cp_uri,
                         rel, idx, 0.9)
        else:
            cp_uri = ids.company(name)
            yield from Entity(
                cp_uri, NS.DD + "Counterparty", name,
                attrs={NS.DD + "counterpartyKind": "contract"},
                source=rel,
            ).triples()
            yield Triple(contract_uri, NS.DD + "counterpartyOf", cp_uri,
                         rel, idx, 0.6)

    # ── executive-employment person ────────────────────────────────────
    def _exec_person(self, contract_uri: str, title: str,
                     eff: date | None, eff_idx: int | None,
                     rel: str) -> Iterable[Triple]:
        """The employed person is the first title segment after "– "; the role
        is the title tail. e.g. "Anstellungsvertrag … – Klaus Mueller – CFO"."""
        parts = re.split(r"\s[–—-]\s", title)
        if len(parts) < 2:
            return
        name = parts[1].strip()
        role = c.title_tail(title) if len(parts) > 2 else None
        ds = c.dataset_of(rel)
        org_short = c.DATASET_ORG_SHORT.get(ds or "", "REA")
        org_uri = ids.company(org_short)
        yield from c.person_with_position(
            name, role or "Vorstand", org_short, org_uri, rel, 0.9, eff_idx)
        person_uri = ids.person(c.clean_person_name(name))
        yield Triple(person_uri, NS.DD + "partyTo", contract_uri,
                     rel, None, 0.9)
