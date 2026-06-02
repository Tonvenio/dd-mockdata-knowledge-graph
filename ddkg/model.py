"""Core data model: namespaces, Triple, Entity helpers."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Iterable
from datetime import date


class NS:
    """Canonical namespaces used throughout the KG."""
    DD     = "https://w3id.org/dd-mockdata#"
    ORG    = "http://www.w3.org/ns/org#"
    FOAF   = "http://xmlns.com/foaf/0.1/"
    PROV   = "http://www.w3.org/ns/prov#"
    SCHEMA = "https://schema.org/"
    XSD    = "http://www.w3.org/2001/XMLSchema#"
    RDF    = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    RDFS   = "http://www.w3.org/2000/01/rdf-schema#"


@dataclass(frozen=True)
class Triple:
    """An RDF triple with optional provenance + confidence."""
    s: str                                    # subject URI
    p: str                                    # predicate URI
    o: Any                                    # object: URI (str), literal (str/int/float/date), or bool
    source: str | None = None                 # provenance: source file path (relative to corpus root)
    paragraph: int | None = None              # provenance: paragraph index (optional)
    confidence: float = 1.0                   # 0..1; canonical extractor → 1.0


@dataclass
class Entity:
    """A typed entity with a stable URI and attributes."""
    uri: str
    type: str                                 # full URI of the rdf:type
    label: str
    attrs: dict[str, Any] = field(default_factory=dict)
    source: str | None = None

    def triples(self) -> Iterable[Triple]:
        yield Triple(self.uri, NS.RDF + "type", self.type, self.source)
        yield Triple(self.uri, NS.RDFS + "label", self.label, self.source)
        for pred, obj in self.attrs.items():
            if obj is None or obj == "":
                continue
            yield Triple(self.uri, pred, obj, self.source)
