"""Triple → Neo4j Cypher serializer.

Groups triples by subject, emits one `MERGE (n:Label {uri: '...'})` per node
followed by `SET n.prop = ...` for datatype properties, then `MATCH/CREATE`
edges for object properties. Output is one self-contained .cypher script
that can be `cat`-piped into cypher-shell.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Iterable
import json
import re

from ..model import Triple, NS

# Generic super-classes: never used as a node's *primary* label when a more
# specific type is also present (e.g. a TransferPricingFile is also a
# DocumentReference — we surface the specific one).
_GENERIC_LABELS = {"DocumentReference", "Contract", "Event"}

# A few relationship names read better than the mechanical snake-case form.
_REL_OVERRIDES = {
    "counterpartyOf": "HAS_COUNTERPARTY",
    "documentOrg":    "DOCUMENT_OF",
    "eventOrg":       "EVENT_OF",
    "assignee":       "ASSIGNED_TO",
    "relatesTo":      "RELATES_TO",
}


def _label_of(type_uri: str) -> str | None:
    """Neo4j label = local name of any dd: rdf:type (faithful, future-proof)."""
    return type_uri[len(NS.DD):] if type_uri.startswith(NS.DD) else None


def _rel_of(pred_uri: str) -> str:
    """Relationship type = SNAKE_UPPER of the predicate local name."""
    local = pred_uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    if local in _REL_OVERRIDES:
        return _REL_OVERRIDES[local]
    return re.sub(r"(?<!^)(?=[A-Z])", "_", local).upper()


def _cy_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, date):
        return f"date('{v.isoformat()}')"
    return json.dumps(str(v), ensure_ascii=False)


def _short(uri: str) -> str:
    return uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def write_cypher(triples: Iterable[Triple], out: Path | str) -> int:
    triples = list(triples)
    labels: dict[str, set[str]] = defaultdict(set)   # uri → {labels}
    props: dict[str, dict[str, object]] = defaultdict(dict)
    rels: list[tuple[str, str, str]] = []            # (s, rel, o)

    for t in triples:
        if t.p == NS.RDF + "type":
            lbl = _label_of(t.o)
            if lbl:
                labels[t.s].add(lbl)
        elif t.p == NS.RDFS + "label":
            props[t.s]["label"] = t.o
        elif isinstance(t.o, str) and t.o.startswith(("http://", "https://")):
            # object property → relationship (every typed node is emitted below,
            # so both endpoints exist and the MERGE resolves).
            rels.append((t.s, _rel_of(t.p), t.o))
        else:
            props[t.s][_short(t.p)] = t.o

    # Safety net: any node that only ever appears as an edge endpoint still
    # needs to exist, or its relationship MERGE would match nothing and the
    # edge would be silently lost. Give such orphans a generic :Resource label.
    endpoints = {s for s, _, _ in rels} | {o for _, _, o in rels}
    for uri in endpoints - set(labels):
        labels[uri].add("Resource")

    lines = [
        "// dd-mockdata-kg — Neo4j Cypher dump",
        "// Run with: cypher-shell -f gold.cypher",
        "",
    ]
    # Nodes — primary label + any additional labels, all properties.
    for uri in sorted(labels):
        all_labels = sorted(labels[uri])
        # specific subclasses first, generic super-classes last; each once
        ordered = ([l for l in all_labels if l not in _GENERIC_LABELS]
                   + [l for l in all_labels if l in _GENERIC_LABELS])
        primary, extra = ordered[0], ordered[1:]
        attrs = {"uri": uri, **props.get(uri, {})}
        kv = ", ".join(f"`{k}`: {_cy_value(v)}" for k, v in attrs.items())
        set_extra = "".join(f":{l}" for l in extra)
        set_clause = f"SET n += {{{kv}}}" + (f", n{set_extra}" if extra else "")
        lines.append(f"MERGE (n:{primary} {{uri: {_cy_value(uri)}}}) {set_clause};")
    lines.append("")
    # Edges
    for s, rel, o in rels:
        lines.append(
            f"MATCH (a {{uri: {_cy_value(s)}}}), (b {{uri: {_cy_value(o)}}}) "
            f"MERGE (a)-[:{rel}]->(b);"
        )
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(labels) + len(rels)
