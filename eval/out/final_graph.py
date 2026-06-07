import csv
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INGEST = "single_A3_ingest.csv"
QUERY  = "single_A3_query.csv"

# Ingesta: p50 en tramos de 5k triples
bins = defaultdict(list)
with open(INGEST) as fh:
    for r in csv.DictReader(fh):
        if r["ok"] not in ("True", "true", "1"):
            continue
        bins[int(r["cumulative_triples"]) // 5000].append(float(r["latency_ms"]))
ing_x = [(b * 5000 + 2500) / 1000 for b in sorted(bins)]
ing_y = [float(np.percentile(bins[b], 50)) for b in sorted(bins)]

# Consultas: p50 por checkpoint
q = defaultdict(lambda: {"x": [], "y": []})
with open(QUERY) as fh:
    for r in csv.DictReader(fh):
        q[r["report"]]["x"].append(int(r["kg_triples"]) / 1000)
        q[r["report"]]["y"].append(float(r["p50_ms"]))

fig, ax = plt.subplots(figsize=(5.2, 3.2))
ax.plot(ing_x, ing_y, "o-", color="#185FA5", label="Ingestion")
ax.plot(q["participants"]["x"], q["participants"]["y"], "s--", color="#0F6E56", label="Report (light)")
ax.plot(q["temporal_emotions"]["x"], q["temporal_emotions"]["y"], "^-", color="#993C1D", label="Report (heavy)")

ax.set_xlabel("KG size (thousand triples)")
ax.set_ylabel("Latency p50 (ms)")
ax.set_ylim(bottom=0)
ax.grid(True, alpha=0.3, linewidth=0.5)
ax.legend(frameon=False, fontsize=9)
fig.tight_layout()
fig.savefig("scalability.pdf")
fig.savefig("scalability.png", dpi=150)
print("Saved scalability.pdf / scalability.png")
