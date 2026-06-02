"""Covenants extractor — financial covenants + quarterly observations.

Parses the eight ``REA_Covenant_Compliance_<year>_<quarter>.docx`` certificates
in the Brennhagen (REA) dataset. Each certificate carries a single table whose rows
report a metric, its measured value and the covenant threshold. We model the one
2022 Konsortialkredit facility, its three financial covenants (Net Debt/EBITDA,
Interest Coverage Ratio, Eigenkapitalquote) and one observation per covenant per
quarter (8 docs × 3 covenants = 24 observations).

Covenant definitions are SHACL-complete (name + operator + threshold) and are
emitted on every document; identical triples are deduplicated by the build
pipeline. Observations carry confidence 0.9 (parsed, not canonical).
"""
from __future__ import annotations
import re
from typing import Iterable

from . import _common as c
from .. import ids
from ..model import Triple, NS
from ..corpus import Corpus

# The one loan facility every certificate refers to.
LOAN_ID = "rea-konsortialkredit-2022"

_PERIOD_RE = re.compile(r"(20\d{2})_?(Q[1-4])")
# Leading comparison operator followed by the numeric threshold.
_COVENANT_RE = re.compile(r"\s*(<=|>=|<|>|=)\s*([\d.,]+)")


def _classify(kennzahl: str) -> tuple[str, str] | None:
    """Map a "Kennzahl" cell to a stable (cov_id, display_name), or None."""
    k = kennzahl.lower()
    if "leverage" in k or "net debt" in k or "net-debt" in k:
        return "nd-ebitda", "Net Debt / EBITDA"
    if "interest coverage" in k or "icr" in k:
        return "icr", "Interest Coverage Ratio"
    if "eigenkapitalquote" in k or "equity" in k:
        return "eq-quote", "Eigenkapitalquote"
    return None


class CovenantsExtractor:
    name = "covenants"

    def __init__(self, corpus: Corpus) -> None:
        self.corpus = corpus

    # ── public API ────────────────────────────────────────────────────
    def _facility_uri(self, root) -> str:
        """The loan-facility node — anchored on the actual Konsortialkredit
        contract document so covenants share the node the filename/contracts
        extractors populate (signing date, parties). Falls back to a synthetic
        id if the document is absent."""
        for p in root.rglob("*Konsortialkredit*.docx"):
            return ids.contract_from_path(self.corpus.relpath(p))
        return ids.contract("konsortialkredit", ["REA"], "2022")

    def extract(self) -> Iterable[Triple]:
        root = self.corpus.datasets["roehrig_large"]
        if not root.exists():
            return
        facility_uri = self._facility_uri(root)
        facility_emitted = False
        for path in sorted(root.rglob("REA_Covenant_Compliance_*.docx")):
            m = _PERIOD_RE.search(path.name)
            if not m:
                continue
            period = f"{m.group(1)}-{m.group(2)}"
            rel = self.corpus.relpath(path)
            doc = c.open_doc(path)
            if not doc.tables:
                continue
            if not facility_emitted:
                # type only — the filename extractor owns the node's label.
                yield Triple(facility_uri, NS.RDF + "type",
                             NS.DD + "LoanFacility", rel)
                facility_emitted = True
            yield from self._table(doc.tables[0], facility_uri, period, rel)

    # ── per-document table ────────────────────────────────────────────
    def _table(self, table, facility_uri: str, period: str,
               rel: str) -> Iterable[Triple]:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if len(cells) < 3:
                continue
            kennzahl, wert, covenant = cells[0], cells[1], cells[2]
            if kennzahl == "Kennzahl":  # header row
                continue
            if covenant.lower() in ("n/a", "info", ""):
                continue
            classified = _classify(kennzahl)
            if classified is None:
                continue
            cov_id, display_name = classified
            cm = _COVENANT_RE.match(covenant)
            if not cm:
                continue
            operator = cm.group(1)
            threshold = c.parse_number(cm.group(2))
            cov_uri = ids.covenant(LOAN_ID, cov_id)
            # Covenant definition (SHACL-complete; deduplicated downstream).
            yield Triple(cov_uri, NS.RDF + "type", NS.DD + "Covenant", rel)
            yield Triple(cov_uri, NS.RDFS + "label", display_name, rel)
            yield Triple(cov_uri, NS.DD + "covenantName", display_name, rel)
            yield Triple(cov_uri, NS.DD + "covenantOperator", operator, rel)
            yield Triple(cov_uri, NS.DD + "covenantThreshold", threshold, rel)
            yield Triple(facility_uri, NS.DD + "governedBy", cov_uri, rel)
            # Quarterly observation.
            value = c.parse_number(wert)
            obs_uri = ids.covenant_observation(LOAN_ID, cov_id, period)
            yield Triple(obs_uri, NS.RDF + "type",
                         NS.DD + "CovenantObservation", rel, confidence=0.9)
            yield Triple(obs_uri, NS.RDFS + "label",
                         f"{display_name} {period} = {value}", rel,
                         confidence=0.9)
            yield Triple(obs_uri, NS.DD + "observationOf", cov_uri, rel,
                         confidence=0.9)
            yield Triple(obs_uri, NS.DD + "observedValue", value, rel,
                         confidence=0.9)
            yield Triple(obs_uri, NS.DD + "observedPeriod", period, rel,
                         confidence=0.9)
