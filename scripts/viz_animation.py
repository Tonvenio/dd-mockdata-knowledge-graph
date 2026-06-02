"""Animated GIF of the gold KG 'building up', tier by tier.

Uses a fixed layout (computed once) so the graph doesn't jitter; each entity
tier fades in cumulatively: company → subsidiaries → people → IP → contracts →
finance. Output: kg/kg-build.gif (matplotlib PillowWriter, no extra deps).
"""
from __future__ import annotations
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.animation import FuncAnimation, PillowWriter
from rdflib import Graph, RDF, RDFS, URIRef

DD = "https://w3id.org/dd-mockdata#"
TTL = sys.argv[1] if len(sys.argv) > 1 else "kg/gold.ttl"
OUT = sys.argv[2] if len(sys.argv) > 2 else "assets/kg-build.gif"

g = Graph(); g.parse(TTL, format="turtle")
def lab(u):
    l = g.value(u, RDFS.label)
    return str(l) if l else str(u).split("#")[-1].split("/")[-1]
def typ(u):
    t = g.value(u, RDF.type)
    return str(t).split("#")[-1] if t else "?"

REA = URIRef(DD + "org/rea")
keep: set = {REA}
for sub in g.subjects(URIRef(DD + "parentCompany"), REA):
    keep.add(sub)
execs = 0
for pos in g.subjects(URIRef(DD + "positionAt"), REA):
    role = g.value(pos, URIRef(DD + "positionRole"))
    rl = lab(role).lower() if role else ""
    if any(k in rl for k in ("vorstand", "aufsichtsrat")):
        per = next(g.subjects(URIRef(DD + "holdsPosition"), pos), None)
        if per:
            keep |= {per, pos}; execs += 1
    if execs >= 3:
        break
patent = URIRef(DD + "patent/rea-08")
if (patent, RDF.type, None) in g:
    keep.add(patent)
    for inv in g.objects(patent, URIRef(DD + "inventedBy")):
        keep.add(inv)
    for prod in g.objects(patent, URIRef(DD + "relatesTo")):
        keep.add(prod)
for fac in g.subjects(RDF.type, URIRef(DD + "LoanFacility")):
    keep.add(fac)
    for cov in g.objects(fac, URIRef(DD + "governedBy")):
        keep.add(cov)
        for obs in g.subjects(URIRef(DD + "observationOf"), cov):
            if "2023-q1" in str(obs).lower():
                keep.add(obs)
for cset in g.subjects(RDF.type, URIRef(DD + "SupplyContract")):
    if "bmw" in str(cset).lower() and "ecu-900" in str(cset).lower():
        keep.add(cset)
        for cp in g.objects(cset, URIRef(DD + "counterpartyOf")):
            keep.add(cp)
        break
mp = 0
for prod in g.subjects(URIRef(DD + "manufacturedBy"), REA):
    if any(c in str(prod) for c in ("ecu-900", "bms-12")):
        keep.add(prod); mp += 1
    if mp >= 2:
        break

REL = ["parentCompany", "holdsPosition", "positionAt", "inventedBy",
       "relatesTo", "assignee", "manufacturedBy", "governedBy",
       "observationOf", "counterpartyOf"]
G = nx.DiGraph()
for n in keep:
    G.add_node(n, kind=typ(n), label=lab(n))
for p in REL:
    for s, o in g.subject_objects(URIRef(DD + p)):
        if s in keep and o in keep:
            G.add_edge(s, o)

PALETTE = {
    "Company": "#2A2E4B", "Subsidiary": "#44A6D8", "Counterparty": "#AC0064",
    "Person": "#F1C643", "Position": "#9aa0c9", "Patent": "#FB525B",
    "Product": "#1E3A8A", "LoanFacility": "#3f7d3e", "Covenant": "#7ab07a",
    "CovenantObservation": "#bcdcbc", "SupplyContract": "#d98c00",
}
# reveal tier per node kind
TIER = {"Company": 0, "Subsidiary": 1, "Person": 2, "Position": 2,
        "Patent": 3, "Product": 3, "SupplyContract": 4, "Counterparty": 4,
        "LoanFacility": 5, "Covenant": 5, "CovenantObservation": 5}
TIER_NAME = ["Group parent", "+ Subsidiaries", "+ People & roles",
             "+ Patents & products", "+ Contracts & counterparties",
             "+ Loan covenants & observations"]
for n in G:
    G.nodes[n]["tier"] = TIER.get(G.nodes[n]["kind"], 5)

pos = nx.kamada_kawai_layout(G)
pos = nx.spring_layout(G, pos=pos, k=1.9, iterations=150, seed=11)

FADE, HOLD = 7, 16
n_tiers = max(d["tier"] for _, d in G.nodes(data=True)) + 1
frames = n_tiers * FADE + HOLD

fig, ax = plt.subplots(figsize=(11.5, 7.4))

def node_alpha(n, f):
    t = G.nodes[n]["tier"]
    start = t * FADE
    if f < start:
        return 0.0
    if f < start + FADE:
        return (f - start + 1) / FADE
    return 1.0

def draw(f):
    ax.clear(); ax.axis("off")
    ax.set_facecolor("#f7f8fb"); fig.set_facecolor("#f7f8fb")
    vis = {n: node_alpha(n, f) for n in G}
    # edges (alpha = min of endpoint alphas)
    for u, v in G.edges():
        a = min(vis[u], vis[v])
        if a <= 0:
            continue
        x1, y1 = pos[u]; x2, y2 = pos[v]
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color="#aab0be",
                                    alpha=a * 0.8, lw=0.9, shrinkA=9, shrinkB=9))
    # nodes
    for n in G:
        a = vis[n]
        if a <= 0:
            continue
        x, y = pos[n]; k = G.nodes[n]["kind"]
        sz = 760 if k in ("Company",) else 520 if k in ("Subsidiary", "Patent",
              "LoanFacility", "SupplyContract", "Counterparty") else 360
        ax.scatter([x], [y], s=sz, c=PALETTE.get(k, "#bbb"), alpha=a,
                   edgecolors="white", linewidths=1.4, zorder=3)
        if a > 0.55:
            ax.text(x, y - 0.052, G.nodes[n]["label"][:22], ha="center",
                    va="top", fontsize=7.2, color="#1b1e2e", alpha=(a - 0.55) / 0.45,
                    zorder=4)
    cur = min(f // FADE, n_tiers - 1)
    ax.set_title(f"Building the dd-mockdata knowledge graph   ·   {TIER_NAME[cur]}",
                 fontsize=13, color="#2A2E4B", pad=12, loc="left")
    ax.margins(0.12)
    return []

anim = FuncAnimation(fig, draw, frames=frames, interval=140, blit=False)
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
anim.save(OUT, writer=PillowWriter(fps=8))
print(f"wrote {OUT}  ({frames} frames, {G.number_of_nodes()} nodes)")
