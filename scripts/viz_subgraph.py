"""Render a curated, legible subgraph of the gold KG as a PNG.

Drawing all ~13k nodes is unreadable; instead we seed at Brennhagen (REA) and walk a
fixed set of "interesting" relations to a small connected subgraph that shows
every entity kind the v0.2 extractors produce.
"""
from __future__ import annotations
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
from rdflib import Graph, RDF, RDFS, URIRef

DD = "https://w3id.org/dd-mockdata#"
TTL = sys.argv[1] if len(sys.argv) > 1 else "kg/gold.ttl"
OUT = sys.argv[2] if len(sys.argv) > 2 else "kg/subgraph.png"

g = Graph()
g.parse(TTL, format="turtle")

def label(u):
    l = g.value(u, RDFS.label)
    if l:
        return str(l)
    return str(u).split("#")[-1].split("/")[-1]

def typ(u):
    t = g.value(u, RDF.type)
    return str(t).split("#")[-1] if t else "?"

# ── pick a small connected seed set ───────────────────────────────────────
REA = URIRef(DD + "org/rea")
keep: set = {REA}

def add_objs(s, pred, limit=None, where_type=None):
    n = 0
    for o in g.objects(URIRef(s) if isinstance(s, str) else s, URIRef(DD + pred)):
        if where_type and typ(o) != where_type:
            continue
        keep.add(o); n += 1
        if limit and n >= limit:
            break

# subsidiaries -> REA
for sub in g.subjects(URIRef(DD + "parentCompany"), REA):
    keep.add(sub)

# a few Vorstand persons (positions @ REA whose role label looks executive)
execs = 0
for pos in g.subjects(URIRef(DD + "positionAt"), REA):
    role = g.value(pos, URIRef(DD + "positionRole"))
    rl = label(role).lower() if role else ""
    if any(k in rl for k in ("vorstand", "aufsichtsrat")):
        person = next(g.subjects(URIRef(DD + "holdsPosition"), pos), None)
        if person:
            keep |= {person, pos}        # role nodes omitted to reduce clutter
            execs += 1
    if execs >= 3:
        break

# one patent + inventors + product + assignee
patent = URIRef(DD + "patent/rea-08")
if (patent, RDF.type, None) in g:
    keep.add(patent)
    for inv in g.objects(patent, URIRef(DD + "inventedBy")):
        keep.add(inv)
        pos = next(g.objects(inv, URIRef(DD + "holdsPosition")), None)
    for prod in g.objects(patent, URIRef(DD + "relatesTo")):
        keep.add(prod)

# loan facility + covenants + one quarter of observations
for fac in g.subjects(RDF.type, URIRef(DD + "LoanFacility")):
    keep.add(fac)
    for cov in g.objects(fac, URIRef(DD + "governedBy")):
        keep.add(cov)
        for obs in g.subjects(URIRef(DD + "observationOf"), cov):
            if "2023-q1" in str(obs).lower():
                keep.add(obs)

# one supply contract (BMW ECU-900) + its counterparty
for c in g.subjects(RDF.type, URIRef(DD + "SupplyContract")):
    if "bmw" in str(c).lower() and "ecu-900" in str(c).lower():
        keep.add(c)
        for cp in g.objects(c, URIRef(DD + "counterpartyOf")):
            keep.add(cp)
        break

# products manufactured by REA (just the two the patent / supply contract touch)
mp = 0
for prod in g.subjects(URIRef(DD + "manufacturedBy"), REA):
    if any(code in str(prod) for code in ("ecu-900", "bms-12")):
        keep.add(prod); mp += 1
    if mp >= 2:
        break

# ── build the networkx graph over kept nodes, with chosen relations ───────
REL = ["parentCompany", "holdsPosition", "positionAt",
       "inventedBy", "relatesTo", "assignee", "manufacturedBy",
       "governedBy", "observationOf", "counterpartyOf"]
G = nx.DiGraph()
for n in keep:
    G.add_node(n, label=label(n), kind=typ(n))
for p in REL:
    P = URIRef(DD + p)
    for s, o in g.subject_objects(P):
        if s in keep and (o in keep):
            G.add_edge(s, o, rel=p)
# literal leaves for a few telling datatype props
for s in list(keep):
    for p in ("effectiveDate", "covenantThreshold", "observedValue", "covenantOperator"):
        v = g.value(s, URIRef(DD + p))
        if v is not None:
            leaf = f"{p}:{v}"
            G.add_node(leaf, label=str(v), kind="lit")
            G.add_edge(s, leaf, rel=p)

# ── colour by type ────────────────────────────────────────────────────────
PALETTE = {
    "Company": "#2A2E4B", "Subsidiary": "#44A6D8", "Counterparty": "#AC0064",
    "Person": "#F1C643", "Position": "#9aa0c9", "Role": "#cfd3e8",
    "Patent": "#FB525B", "Product": "#1E3A8A",
    "LoanFacility": "#5b8c5a", "Covenant": "#8fbf8e", "CovenantObservation": "#cfe3cf",
    "SupplyContract": "#d98c00", "lit": "#dddddd",
}
def color(n):
    return PALETTE.get(G.nodes[n]["kind"], "#bbbbbb")

plt.figure(figsize=(22, 14))
pos = nx.kamada_kawai_layout(G)
pos = nx.spring_layout(G, pos=pos, k=1.9, iterations=120, seed=11)
sizes = [900 if G.nodes[n]["kind"] != "lit" else 300 for n in G]
nx.draw_networkx_edges(G, pos, edge_color="#9aa0b0", arrows=True,
                       arrowsize=11, width=1.0, alpha=0.7)
nx.draw_networkx_nodes(G, pos, node_color=[color(n) for n in G],
                       node_size=sizes, edgecolors="white", linewidths=1.3)
labels = {n: (G.nodes[n]["label"][:26]) for n in G}
nx.draw_networkx_labels(G, pos, labels, font_size=8, font_color="#11131f")
edge_lbls = {(u, v): d["rel"] for u, v, d in G.edges(data=True)}
nx.draw_networkx_edge_labels(G, pos, edge_lbls, font_size=6.2,
                             font_color="#55607a", rotate=False,
                             bbox=dict(boxstyle="round,pad=0.05", fc="white", ec="none", alpha=0.6))
handles = [mpatches.Patch(color=c, label=k) for k, c in PALETTE.items() if k != "lit"]
plt.legend(handles=handles, loc="lower left", fontsize=9, ncol=2, frameon=True)
plt.title("dd-mockdata-kg — Brennhagen Elektronik AG curated subgraph "
          f"({G.number_of_nodes()} nodes / {G.number_of_edges()} edges of {len(g)} total statements)",
          fontsize=13, color="#2A2E4B")
plt.axis("off")
plt.tight_layout()
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
plt.savefig(OUT, dpi=130, bbox_inches="tight", facecolor="white")
print(f"wrote {OUT}  ({G.number_of_nodes()} nodes, {G.number_of_edges()} edges)")
