"""Triple → RDF (Turtle, JSON-LD) builder using rdflib."""
from __future__ import annotations
from datetime import date
from pathlib import Path
from typing import Iterable

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD, FOAF, PROV

from ..model import NS, Triple
from .. import ids

DD     = Namespace(NS.DD)
ORG    = Namespace(NS.ORG)
SCHEMA = Namespace(NS.SCHEMA)


def _to_object(o):
    """Coerce a Python object into the right rdflib node."""
    if isinstance(o, str) and o.startswith(("http://", "https://")):
        return URIRef(o)
    if isinstance(o, bool):
        return Literal(o, datatype=XSD.boolean)
    if isinstance(o, int):
        return Literal(o, datatype=XSD.integer)
    if isinstance(o, float):
        # Use an explicit decimal lexical form; a Python float backing an
        # xsd:decimal literal is flagged ill-typed by rdflib/pyshacl.
        return Literal(repr(o), datatype=XSD.decimal)
    if isinstance(o, date):
        return Literal(o.isoformat(), datatype=XSD.date)
    return Literal(str(o))


def to_rdf(triples: Iterable[Triple]) -> Graph:
    g = Graph()
    g.bind("dd", DD)
    g.bind("org", ORG)
    g.bind("foaf", FOAF)
    g.bind("prov", PROV)
    g.bind("schema", SCHEMA)
    g.bind("xsd", XSD)
    g.bind("rdfs", RDFS)
    for t in triples:
        g.add((URIRef(t.s), URIRef(t.p), _to_object(t.o)))
        # provenance reification — emit a single prov:wasDerivedFrom per
        # subject keyed off the source path
        if t.source:
            # provenance node uses the same slug-based scheme as the
            # ``filename`` extractor's dd:DocumentReference, so prov links land
            # on the indexed document node (and the URI is always Turtle-valid).
            src_uri = URIRef(ids.document_ref(t.source))
            g.add((URIRef(t.s), PROV.wasDerivedFrom, src_uri))
    return g


def write_turtle(triples: Iterable[Triple], out: Path | str) -> int:
    g = to_rdf(triples)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(out), format="turtle")
    return len(g)


def write_jsonld(triples: Iterable[Triple], out: Path | str) -> int:
    g = to_rdf(triples)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(out), format="json-ld", indent=2)
    return len(g)
