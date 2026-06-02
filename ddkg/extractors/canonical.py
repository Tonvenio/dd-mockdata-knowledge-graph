"""Canonical extractor — emits triples from `enhance_lib.py` constants.

This extractor produces the ground-truth seed KG and runs first. Every triple
it emits has confidence = 1.0 because it's derived directly from the canonical
fact tables of the corpus (no LLM, no parsing). Document-level extractors then
enrich this seed with file-specific facts.

Typical yield: ~1,500 triples (3 companies + 7 subsidiaries + ~40 persons +
~50 positions + ~30 products + a handful of patents and counterparties).
"""
from __future__ import annotations
from typing import Iterable

from .. import ids
from ..model import Triple, Entity, NS
from ..corpus import Corpus


class CanonicalExtractor:
    name = "canonical"

    def __init__(self, corpus: Corpus) -> None:
        self.corpus = corpus
        self.facts = corpus.facts()

    # ── public API ────────────────────────────────────────────────────
    def extract(self) -> Iterable[Triple]:
        yield from self._mueller()
        yield from self._biotech()
        yield from self._roehrig()

    # ── Müller (mid-market mechanical engineering) ────────────────────
    def _mueller(self) -> Iterable[Triple]:
        m = self.facts["mueller"]
        src = "mueller_small/enhance_lib.py"
        co_uri = ids.company(m["short"])
        yield from Entity(
            uri=co_uri, type=NS.DD + "Company", label=m["name"],
            attrs={
                NS.DD + "hrb":         m["hrb"],
                NS.DD + "ustId":       m["ust"],
                NS.DD + "iban":        m["iban"],
                NS.DD + "countryCode": "DE",
                NS.DD + "employees":   m.get("employees_2023"),
                NS.DD + "revenueEur":  m.get("revenue_2023"),
                NS.DD + "ebitdaEur":   m.get("ebitda_2023"),
                NS.SCHEMA + "address": m["addr"],
            }, source=src,
        ).triples()
        # Vorstand / GF
        for role_key, role_label in [("ceo", "CEO / Geschäftsführer"),
                                      ("cfo", "CFO / Geschäftsführerin")]:
            if m.get(role_key):
                yield from self._person_in_role(m[role_key], role_label, m["short"], co_uri, src)
        # Counterparties (customers + suppliers)
        for cust in m.get("kunden", []):
            yield from self._counterparty(cust, "customer", src)
        for sup in m.get("lieferanten", []):
            yield from self._counterparty(sup, "supplier", src)
        # Products
        for prod in m.get("produkte", []):
            yield from self._product(prod, co_uri, src)

    # ── BioTech (medtech growth) ──────────────────────────────────────
    def _biotech(self) -> Iterable[Triple]:
        b = self.facts["biotech"]
        src = "biotech_medium/enhance_lib.py"
        co_uri = ids.company(b["short"])
        yield from Entity(
            uri=co_uri, type=NS.DD + "Company", label=b["name"],
            attrs={
                NS.DD + "hrb":         b["hrb"],
                NS.DD + "ustId":       b["ust"],
                NS.DD + "countryCode": "DE",
                NS.DD + "employees":   b.get("employees_2023"),
                NS.DD + "revenueEur":  b.get("revenue_2023"),
                NS.DD + "ebitdaEur":   b.get("ebitda_2023"),
                NS.SCHEMA + "address": b["addr"],
            }, source=src,
        ).triples()
        for k, label in [("ceo","CEO"),("cto","CTO"),("cfo","CFO"),
                         ("cmo","CMO"),("qra","QRA")]:
            if b.get(k):
                yield from self._person_in_role(b[k], label, b["short"], co_uri, src)
        for inv, share in b.get("investoren", []):
            inv_uri = ids.company(inv)
            yield from Entity(inv_uri, NS.DD + "Counterparty", inv, source=src).triples()
            yield Triple(co_uri, NS.DD + "investorShare", f"{inv}: {share}", src)
        for name, cls, ref in b.get("produkte", []):
            yield from self._product_with_class(name, cls, ref, co_uri, src)
        for d in b.get("distributoren", []):
            yield from self._counterparty(d, "distributor", src)
        for c in b.get("kliniken", []):
            yield from self._counterparty(c, "clinic", src)
        for s in b.get("lieferanten", []):
            yield from self._counterparty(s, "supplier", src)

    # ── Brennhagen (listed AG holding + 6 subsidiaries) ───────────────────
    def _roehrig(self) -> Iterable[Triple]:
        r = self.facts["roehrig_ag"]
        subs = self.facts["roehrig_subs"]
        src = "roehrig_large/enhance_lib.py"
        holding = ids.company(r["short"])
        yield from Entity(
            uri=holding, type=NS.DD + "Company", label=r["name"],
            attrs={
                NS.DD + "hrb":          r["hrb"],
                NS.DD + "ustId":        r["ust"],
                NS.DD + "wkn":          r.get("wkn"),
                NS.DD + "isin":         r.get("isin"),
                NS.DD + "countryCode":  "DE",
                NS.DD + "employees":    r.get("employees_2023"),
                NS.DD + "revenueEur":   r.get("revenue_2023"),
                NS.DD + "ebitdaEur":    r.get("ebitda_2023"),
                NS.SCHEMA + "address":  r["addr"],
            }, source=src,
        ).triples()
        # Vorstand
        for k, label in [("ceo","CEO / Vorstandsvorsitzende"),("cfo","CFO"),
                         ("coo","COO"),("cto","CTO")]:
            if r.get(k):
                yield from self._person_in_role(r[k], label, r["short"], holding, src)
        # AR
        if r.get("ar_vorsitz"):
            yield from self._person_in_role(r["ar_vorsitz"], "Aufsichtsratsvorsitz",
                                            r["short"], holding, src)
        # Subsidiaries (each gets parentCompany → holding)
        for short, sub in subs.items():
            sub_uri = ids.company(short)
            yield from Entity(
                uri=sub_uri, type=NS.DD + "Subsidiary", label=sub["name"],
                attrs={
                    NS.DD + "hrb":         sub.get("hrb"),
                    NS.DD + "countryCode": sub["country"],
                    NS.DD + "employees":   sub.get("employees"),
                    NS.DD + "revenueEur":  (sub.get("revenue_mio") or 0) * 1_000_000,
                    NS.SCHEMA + "address": f"{sub['city']}, {sub['country']}",
                    NS.RDFS + "comment":   sub.get("focus"),
                }, source=src,
            ).triples()
            yield Triple(sub_uri, NS.DD + "parentCompany", holding, src)
        # Products
        for short, label in r.get("produkte", []):
            pu = ids.product(short)
            yield from Entity(pu, NS.DD + "Product", label,
                              attrs={NS.SCHEMA + "identifier": short}, source=src).triples()
            yield Triple(pu, NS.DD + "manufacturedBy", holding, src)
        # OEM counterparties
        for oem in r.get("oem_kunden", []):
            yield from self._counterparty(oem, "oem", src)

    # ── helpers ───────────────────────────────────────────────────────
    def _person_in_role(self, name: str, role_label: str, org_short: str,
                        org_uri: str, src: str) -> Iterable[Triple]:
        p_uri = ids.person(name)
        r_uri = ids.role(role_label)
        pos_uri = ids.position(name, role_label, org_short)
        yield from Entity(p_uri, NS.DD + "Person", name, source=src).triples()
        yield from Entity(r_uri, NS.DD + "Role", role_label, source=src).triples()
        yield from Entity(pos_uri, NS.DD + "Position",
                          f"{name} — {role_label} @ {org_short}", source=src).triples()
        yield Triple(p_uri, NS.DD + "holdsPosition", pos_uri, src)
        yield Triple(pos_uri, NS.DD + "positionRole", r_uri, src)
        yield Triple(pos_uri, NS.DD + "positionAt", org_uri, src)

    def _counterparty(self, name: str, kind: str, src: str) -> Iterable[Triple]:
        u = ids.company(name)
        yield from Entity(u, NS.DD + "Counterparty", name,
                          attrs={NS.DD + "counterpartyKind": kind}, source=src).triples()

    def _product(self, label: str, org_uri: str, src: str) -> Iterable[Triple]:
        u = ids.product(label)
        yield from Entity(u, NS.DD + "Product", label, source=src).triples()
        yield Triple(u, NS.DD + "manufacturedBy", org_uri, src)

    def _product_with_class(self, name: str, cls: str, ref: str,
                            org_uri: str, src: str) -> Iterable[Triple]:
        u = ids.product(name)
        yield from Entity(u, NS.DD + "Product", name, attrs={
            NS.DD + "regulatoryClass": cls,
            NS.SCHEMA + "identifier":  ref,
        }, source=src).triples()
        yield Triple(u, NS.DD + "manufacturedBy", org_uri, src)
