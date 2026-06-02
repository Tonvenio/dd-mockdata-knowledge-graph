"""Smallest end-to-end example: build the KG, count entities, run a query."""
from pathlib import Path
import sys

# locate ../dd-mockdata
HERE = Path(__file__).resolve().parent
DEFAULT_CORPUS = HERE.parent.parent / "dd-mockdata"
if not (DEFAULT_CORPUS / "enhance_lib.py").exists():
    print(f"clone dd-mockdata next to dd-mockdata-kg (expected at {DEFAULT_CORPUS})")
    sys.exit(1)

from ddkg.corpus import Corpus
from ddkg.extractors import CanonicalExtractor
from ddkg.builders import write_turtle
from rdflib import Graph

corpus = Corpus(DEFAULT_CORPUS)
triples = list(CanonicalExtractor(corpus).extract())
print(f"extracted {len(triples)} triples")

OUT = HERE.parent / "kg" / "gold.ttl"
write_turtle(triples, OUT)
print(f"wrote {OUT}")

g = Graph(); g.parse(OUT, format="turtle")
q = """
PREFIX dd:   <https://w3id.org/dd-mockdata#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?subLabel ?country WHERE {
  ?sub a dd:Subsidiary ;
       dd:parentCompany dd:org/rea ;
       rdfs:label ?subLabel ;
       dd:countryCode ?country .
} ORDER BY ?country
"""
print("\nBrennhagen subsidiaries:")
for row in g.query(q):
    print(f"  {row.country}  {row.subLabel}")
