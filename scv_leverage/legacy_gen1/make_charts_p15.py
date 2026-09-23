import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Patch

SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"

INK="#171a1f"; INK700="#3b3f47"; INK500="#6b6f78"; LINE="#dcd6c8"
GOLD="#a8792f"; STEEL="#3c6b8f"; TEAL="#3c8f7f"; PURPLE="#7a5b96"; RUST="#b5622f"
NAVY="#2e4a6b"; SAND="#c9a24b"
PAPER="#fffdf9"

plt.rcParams.update({
    "font.family":"DejaVu Sans","axes.edgecolor":LINE,"axes.labelcolor":INK700,
    "text.color":INK,"xtick.color":INK500,"ytick.color":INK500,
    "axes.facecolor":PAPER,"figure.facecolor":PAPER,"savefig.facecolor":PAPER,"font.size":11,
})

def style_ax(ax, grid_axis="y"):
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False); ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.grid(axis=grid_axis, color=LINE, linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True); ax.tick_params(length=0)

df = pd.read_csv(rf"{SCRATCH}\portfolios_annual.csv", index_col=0)
years = df.index.to_numpy()

# =============================================================================
# CHART 1: Growth of $1 -- both portfolios + Market for reference
# =============================================================================
fig, ax = plt.subplots(figsize=(9.5, 5.0), dpi=170)
for col, label, color in [("Mkt","Market",STEEL), ("Port_A","Portfolio A (2x Market core)",NAVY), ("Port_B","Portfolio B (SCV core)",RUST)]:
    nav = (1+df[col]).cumprod()
    ax.plot(years, nav, color=color, linewidth=1.8, marker="o", markersize=3, label=label)
    ax.annotate(f"${nav.iloc[-1]:,.0f}", xy=(years[-1], nav.iloc[-1]), xytext=(6,0),
                textcoords="offset points", color=color, fontsize=9, fontweight="bold", va="center")
ax.set_yscale("log")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,p: f"${v:,.0f}" if v>=1 else f"${v:.2f}"))
ax.set_ylabel("Growth of $1 (log scale), 1985 = $1")
style_ax(ax)
leg = ax.legend(loc="upper left", fontsize=9.5, framealpha=0.92, edgecolor=LINE)
leg.get_frame().set_facecolor(PAPER)
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\p15_chart1_growth.png")
plt.close()

# =============================================================================
# CHART 2: Monte Carlo CAGR distribution, A vs B
# =============================================================================
ann_A = np.load(rf"{SCRATCH}\p15_mc_ann_A.npy")
ann_B = np.load(rf"{SCRATCH}\p15_mc_ann_B.npy")

fig, ax = plt.subplots(figsize=(9.5, 4.6), dpi=170)
lo = min(ann_A.min(), ann_B.min())*100
hi = max(ann_A.max(), ann_B.max())*100
bins = np.linspace(lo, hi, 90)
ax.hist(ann_A*100, bins=bins, color=NAVY, alpha=0.55, label="Portfolio A (2x Market core)", zorder=3)
ax.hist(ann_B*100, bins=bins, color=RUST, alpha=0.55, label="Portfolio B (SCV core)", zorder=3)
ax.axvline(0, color=INK, linewidth=1)
ax.set_xlabel("25-year annualized return (simulated)")
ax.set_ylabel("Number of simulated paths")
ax.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
style_ax(ax)
ax.legend(frameon=False, loc="upper right", fontsize=9.5)
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\p15_chart2_mc_dist.png")
plt.close()

# =============================================================================
# CHART 3: drawdown comparison, box-style percentile bars
# =============================================================================
dd_A = np.load(rf"{SCRATCH}\p15_mc_dd_A.npy")
dd_B = np.load(rf"{SCRATCH}\p15_mc_dd_B.npy")

fig, ax = plt.subplots(figsize=(9.2, 3.0), dpi=170)
order = [("Portfolio B (SCV core)", dd_B, RUST), ("Portfolio A (2x Market core)", dd_A, NAVY)]
for i, (name, d, color) in enumerate(order):
    d = d*100
    p5, p25, p50, p75, p95 = np.percentile(d, [5,25,50,75,95])
    ax.plot([p5,p95],[i,i], color=color, linewidth=2, alpha=0.5, zorder=2)
    ax.plot([p25,p75],[i,i], color=color, linewidth=10, alpha=0.85, zorder=3, solid_capstyle="butt")
    ax.plot([p50],[i], marker="o", color=INK, markersize=6, zorder=4)
    ax.text(p95+1, i, f"p50 {p50:.0f}%", va="center", fontsize=9.5, color=INK700)
ax.set_yticks(range(len(order))); ax.set_yticklabels([n for n,_,_ in order], fontsize=10)
ax.set_xlabel("Max drawdown over a simulated 25-year path")
ax.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
ax.set_xlim(5, -65)
style_ax(ax, grid_axis="x")
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\p15_chart3_dd.png")
plt.close()

print("All 1.5x-portfolio charts saved.")
