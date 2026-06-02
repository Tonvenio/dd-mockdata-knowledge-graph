"""Standalone INTERACTIVE graph (vis-network) — opens in any browser, no server.

Renders the entity layer of the gold KG (everything except the bulky
dd:DocumentReference provenance index) as a zoomable/draggable HTML file.
"""
from __future__ import annotations
import sys
from pyvis.network import Network
from rdflib import Graph, RDF, RDFS, URIRef

DD = "https://w3id.org/dd-mockdata#"
TTL = sys.argv[1] if len(sys.argv) > 1 else "kg/gold.ttl"
OUT = sys.argv[2] if len(sys.argv) > 2 else "kg/graph.html"

g = Graph(); g.parse(TTL, format="turtle")

def local(u): return str(u).split("#")[-1]
def label(u):
    l = g.value(u, RDFS.label)
    return str(l) if l else local(u).split("/")[-1]
def typ(u):
    t = g.value(u, RDF.type)
    return local(t).split("/")[-1] if t else None

PALETTE = {
    "Company": "#2A2E4B", "Holding": "#2A2E4B", "Subsidiary": "#44A6D8",
    "Counterparty": "#AC0064", "Person": "#F1C643", "Position": "#9aa0c9",
    "Role": "#cfd3e8", "Patent": "#FB525B", "Product": "#1E3A8A",
    "LoanFacility": "#3f7d3e", "Covenant": "#7ab07a",
    "CovenantObservation": "#bcdcbc", "SupplyContract": "#d98c00",
    "EmploymentContract": "#e8b04b", "NDA": "#b06b00", "LeaseContract": "#c98a3a",
    "BoardMeeting": "#7c6f9c", "ShareholderMeeting": "#6a5b91",
    "WorksCouncilMeeting": "#8a7faa", "ReviewEvent": "#a89bc4",
}
SIZE = {"Company": 34, "Holding": 34, "Subsidiary": 24, "Patent": 20,
        "LoanFacility": 22, "Product": 18}

# nodes: every typed node that is NOT a document-reference / TP file
keep = {}
SKIP_TYPES = {"DocumentReference", "TransferPricingFile"}
for s, _, t in g.triples((None, RDF.type, None)):
    tl = local(t).split("/")[-1]
    if tl in SKIP_TYPES:
        continue
    keep[s] = tl

# object-property edges to show (skip provenance + doc links)
REL = {"parentCompany", "holdsPosition", "positionAt", "positionRole",
       "inventedBy", "relatesTo", "assignee", "manufacturedBy",
       "governedBy", "observationOf", "counterpartyOf", "partyTo", "eventOrg"}

net = Network(height="100vh", width="100%", bgcolor="#f7f8fb",
              font_color="#1b1e2e", directed=True, notebook=False)
net.barnes_hut(gravity=-9000, central_gravity=0.25, spring_length=120,
               spring_strength=0.03, damping=0.5)

for uri, tl in keep.items():
    lbl = label(uri)
    net.add_node(str(uri), label=lbl[:30], title=f"{tl}: {lbl}",
                 color=PALETTE.get(tl, "#bbbbbb"), size=SIZE.get(tl, 14),
                 borderWidth=1)

edges = 0
for p in REL:
    P = URIRef(DD + p)
    for s, o in g.subject_objects(P):
        if s in keep and o in keep:
            net.add_edge(str(s), str(o), title=p, color="#c2c7d2",
                         arrowStrikethrough=False, width=0.6)
            edges += 1

net.set_options('{"physics":{"stabilization":{"iterations":300}},'
                '"interaction":{"hover":true,"tooltipDelay":80,"navigationButtons":true},'
                '"edges":{"smooth":{"type":"continuous"},"arrows":{"to":{"scaleFactor":0.4}}}}')
net.write_html(OUT, notebook=False, open_browser=False)
print(f"wrote {OUT}  ({len(keep)} entity nodes, {edges} edges; "
      f"{len(g)} total statements)")
