"""Extraction pipeline: run extractors in order, deduplicate, report.

The pipeline runs the canonical extractor first (every triple confidence 1.0)
followed by the document-level extractors. Triples are deduplicated on
``(s, p, o)``; for *functional* predicates (a subject may have only one value —
labels, dates, covenant operators, …) the **first** writer wins, which means
the canonical extractor always beats a later, lower-confidence guess. Conflicts
on functional predicates are recorded so ``ddkg build`` can report them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from .model import Triple, NS
from .corpus import Corpus


def _D(local: str) -> str:
    return NS.DD + local


# Predicates that may hold only one value per subject. A second, *different*
# object is treated as a conflict (kept = first writer, i.e. higher precedence).
FUNCTIONAL_PREDICATES: set[str] = {
    NS.RDFS + "label",
    _D("effectiveDate"), _D("expiryDate"),
    _D("appointedOn"), _D("resignedOn"),
    _D("filingNumber"), _D("jurisdiction"), _D("patentStatus"),
    _D("assignee"),
    _D("covenantName"), _D("covenantOperator"), _D("covenantThreshold"),
    _D("observedValue"), _D("observedAt"),
    _D("parentCompany"), _D("positionAt"), _D("positionRole"),
    _D("counterpartyKind"), _D("volumeEur"), _D("eventDate"),
}


def _norm(o) -> str:
    return o.isoformat() if isinstance(o, date) else str(o)


@dataclass
class Deduper:
    """Collects triples, dropping exact duplicates and functional conflicts."""
    triples: list[Triple] = field(default_factory=list)
    _seen: set = field(default_factory=set)
    _functional: dict = field(default_factory=dict)   # (s, p) -> object
    conflicts: list = field(default_factory=list)     # (kept_obj, dropped_triple)

    def add(self, t: Triple) -> None:
        key = (t.s, t.p, _norm(t.o))
        if key in self._seen:
            return
        if t.p in FUNCTIONAL_PREDICATES:
            fk = (t.s, t.p)
            if fk in self._functional:
                # a different value already exists → keep the first writer
                self.conflicts.append((self._functional[fk], t))
                return
            self._functional[fk] = t.o
        self._seen.add(key)
        self.triples.append(t)

    def extend(self, triples: Iterable[Triple]) -> None:
        for t in triples:
            self.add(t)


# Extractors run in this order; canonical first so it wins all conflicts.
def _extractor_classes():
    from .extractors import (
        CanonicalExtractor, FilenameExtractor, ContractsExtractor,
        PatentsExtractor, CovenantsExtractor, PositionsExtractor,
    )
    return [CanonicalExtractor, FilenameExtractor, ContractsExtractor,
            PatentsExtractor, CovenantsExtractor, PositionsExtractor]


def build_triples(corpus: Corpus, verbose: bool = False) -> tuple[list[Triple], Deduper]:
    """Run all extractors through the Deduper and return (triples, deduper)."""
    dd = Deduper()
    for cls in _extractor_classes():
        try:
            ex = cls(corpus)
        except Exception as exc:                       # pragma: no cover
            if verbose:
                print(f"  ! {cls.__name__} init failed: {exc}")
            continue
        before = len(dd.triples)
        n_in = 0
        for t in ex.extract():
            n_in += 1
            dd.add(t)
        if verbose:
            print(f"  {getattr(ex, 'name', cls.__name__):<12} "
                  f"{n_in:>6} emitted → {len(dd.triples) - before:>6} kept")
    return dd.triples, dd
