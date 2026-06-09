"""
Final scalability figure for the SEGB evaluation.
Run after the suite, over single_A3_ingest.csv and single_A3_query.csv.

Two corrections vs. the naive version:
  1. Drops a known transient outlier (explicit, see OUTLIERS).
  2. Aligns all three series to the Virtuoso triple count, so ingestion and queries share one x-axis.
"""
import csv
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INGEST = "single_A3_ingest.csv"
QUERY  = "single_A3_query.csv"

# Transient one-off spikes to drop, as (report, kg_triples). Documented for
# transparency: at ~16k triples temporal_emotions showed p50=56.9 / p95=1095 ms,
# isolated from its neighbours (~24 ms).
OUTLIERS = {("temporal_emotions", 16115)}

# --- Virtuoso checkpoints (x-axis shared by every series) ---
kg_ckpts = sorted(set(int(r["kg_triples"]) for r in csv.DictReader(open(QUERY))))

# --- Ingestion: p50 per local 5k-triple batch, mapped onto the Virtuoso axis ---
bins = defaultdict(list)
with open(INGEST) as fh:
    for r in csv.DictReader(fh):
        if r["ok"] not in ("True", "true", "1"):
            continue
        bins[int(r["cumulative_triples"]) // 5000].append(float(r["latency_ms"]))
ing_x, ing_y = [], []
for b in sorted(bins):
    if b < len(kg_ckpts):
        ing_x.append(kg_ckpts[b] / 1000)
        ing_y.append(float(np.percentile(bins[b], 50)))

# --- Query series (outliers dropped) ---
q = defaultdict(lambda: {"x": [], "y": []})
with open(QUERY) as fh:
    for r in csv.DictReader(fh):
        kg = int(r["kg_triples"])
        if (r["report"], kg) in OUTLIERS:
            continue
        q[r["report"]]["x"].append(kg / 1000)
        q[r["report"]]["y"].append(float(r["p50_ms"]))

# --- Plot ---
plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 11, "axes.labelsize": 11,
    "legend.fontsize": 9.5, "xtick.labelsize": 9.5, "ytick.labelsize": 9.5,
    "axes.linewidth": 0.9,
})
C_ING, C_LIGHT, C_HEAVY = "#2C5F8A", "#3B7A57", "#B5562B"

fig, ax = plt.subplots(figsize=(5.4, 3.3))
ax.plot(ing_x, ing_y, "o-", lw=1.7, ms=6, color=C_ING, mec="white", mew=0.7,
        label="Ingestion")
ax.plot(q["participants"]["x"], q["participants"]["y"], "s--", lw=1.7, ms=6,
        color=C_LIGHT, mec="white", mew=0.7, label="SPARQL query (light)")
ax.plot(q["temporal_emotions"]["x"], q["temporal_emotions"]["y"], "^-", lw=1.7, ms=7,
        color=C_HEAVY, mec="white", mew=0.7, label="SPARQL query (heavy)")

ax.set_xlabel("Knowledge graph size (thousand triples)")
ax.set_ylabel("Latency, p50 (ms)")
ax.set_ylim(0, 45)
ax.set_xlim(8, 58)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.grid(axis="y", ls=":", lw=0.6, color="0.7", alpha=0.8)
ax.tick_params(length=3)
ax.legend(frameon=False, loc="upper left", handlelength=2.4, borderaxespad=0.3)
fig.tight_layout(pad=0.5)
fig.savefig("scalability.pdf")
fig.savefig("scalability.png", dpi=200)
print("Saved scalability.pdf / scalability.png")