"""KG characterization via networkx, sourced from GET /events."""
from __future__ import annotations

import requests
import networkx as nx
from rdflib import Graph


def fetch_graph(base_url: str) -> Graph:
    r = requests.get(f"{base_url}/events", timeout=300)
    g = Graph()
    g.parse(data=r.text, format="turtle")
    return g


def load_graph_file(path: str) -> Graph:
    g = Graph()
    g.parse(path, format="turtle")
    return g


def to_networkx(g: Graph) -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    for s, p, o in g:
        G.add_edge(str(s), str(o), predicate=str(p))
    return G


def graph_stats(g: Graph) -> dict:
    G = to_networkx(g)
    n = G.number_of_nodes()
    wccs = list(nx.weakly_connected_components(G)) if n else []
    degrees = [d for _, d in G.degree()]
    return {
        "triples": len(g),
        "nodes": n,
        "edges": G.number_of_edges(),
        "weakly_connected_components": len(wccs),
        "largest_component_nodes": (len(max(wccs, key=len)) if wccs else 0),
        "avg_degree": round(sum(degrees) / len(degrees), 3) if degrees else 0.0,
        "density": round(nx.density(G), 6) if n > 1 else 0.0,
    }
