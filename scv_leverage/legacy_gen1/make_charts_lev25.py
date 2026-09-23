import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Patch

SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"

INK = "#171a1f"; INK700 = "#3b3f47"; INK500 = "#6b6f78"; LINE = "#dcd6c8"
GOLD = "#a8792f"; STEEL = "#3c6b8f"; DANGER = "#a8432f"; GOOD = "#3f7d52"
PURPLE = "#7a5b96"
PAPER = "#fffdf9"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "axes.edgecolor": LINE, "axes.labelcolor": INK700,
    "text.color": INK, "xtick.color": INK500, "ytick.color": INK500,
    "axes.facecolor": PAPER, "figure.facecolor": PAPER, "savefig.facecolor": PAPER, "font.size": 11,
})

def style_ax(ax, grid_axis="y"):
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False); ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.grid(axis=grid_axis, color=LINE, linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True); ax.tick_params(length=0)

# =============================================================================
# CHART 1: Growth of $1 -- Market vs 2x Market vs SCV (log scale)
# =============================================================================
dates = pd.to_datetime(np.load(rf"{SCRATCH}\l25_dates.npy").astype('datetime64[D]'))
mkt_nav = np.load(rf"{SCRATCH}\l25_mkt_nav.npy")
lev_nav = np.load(rf"{SCRATCH}\l25_lev_nav.npy")
sv_nav = np.load(rf"{SCRATCH}\l25_sv_nav.npy")

fig, ax = plt.subplots(figsize=(9.5, 4.8), dpi=170)
ax.plot(dates, mkt_nav, color=STEEL, linewidth=1.5, label="Market")
ax.plot(dates, lev_nav, color=PURPLE, linewidth=1.5, label="2x Market (daily-rebal., w/ costs)")
ax.plot(dates, sv_nav, color=GOLD, linewidth=1.5, label="Small-Cap Value")
ax.set_yscale("log")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"${v:,.0f}" if v>=1 else f"${v:.2f}"))
ax.set_ylabel("Growth of $1 (log scale)")
style_ax(ax)
ax.legend(frameon=False, loc="upper left", fontsize=9.5)
for nav, color in [(sv_nav, GOLD), (lev_nav, PURPLE), (mkt_nav, STEEL)]:
    ax.annotate(f"${nav[-1]:,.0f}", xy=(dates[-1], nav[-1]), xytext=(6,0), textcoords="offset points",
                color=color, fontsize=9, fontweight="bold", va="center")
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\l25_chart1_growth.png")
plt.close()

# =============================================================================
# CHART 2: Rolling 25yr annualized returns, all three
# =============================================================================
win_end = pd.to_datetime(np.load(rf"{SCRATCH}\l25_win_end_dates.npy"))
mkt_ann = np.load(rf"{SCRATCH}\l25_mkt_ann.npy")
lev_ann = np.load(rf"{SCRATCH}\l25_lev_ann.npy")
sv_ann = np.load(rf"{SCRATCH}\l25_sv_ann.npy")

fig, ax = plt.subplots(figsize=(9.8, 4.8), dpi=170)
ax.plot(win_end, mkt_ann*100, color=STEEL, linewidth=1.5, label="Market")
ax.plot(win_end, lev_ann*100, color=PURPLE, linewidth=1.5, label="2x Market")
ax.plot(win_end, sv_ann*100, color=GOLD, linewidth=1.5, label="Small-Cap Value")
ax.axhline(0, color=INK500, linewidth=0.7)
ax.set_ylabel("Rolling 25-year annualized return")
ax.set_xlabel("Rolling 25-year window (labeled by end date)")
ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
style_ax(ax)
ax.legend(frameon=False, loc="upper left", fontsize=9.5)
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\l25_chart2_rolling.png")
plt.close()

# =============================================================================
# CHART 3: Monte Carlo distribution of 25yr CAGR, all three
# =============================================================================
mc_mkt = np.load(rf"{SCRATCH}\l25_mc_mkt_ann.npy")
mc_lev = np.load(rf"{SCRATCH}\l25_mc_lev_ann.npy")
mc_sv = np.load(rf"{SCRATCH}\l25_mc_sv_ann.npy")

fig, ax = plt.subplots(figsize=(9.5, 4.6), dpi=170)
lo = min(mc_mkt.min(), mc_lev.min(), mc_sv.min())*100
hi = max(mc_mkt.max(), mc_lev.max(), mc_sv.max())*100
bins = np.linspace(lo, hi, 90)
ax.hist(mc_mkt*100, bins=bins, color=STEEL, alpha=0.55, label="Market", zorder=3)
ax.hist(mc_lev*100, bins=bins, color=PURPLE, alpha=0.5, label="2x Market", zorder=3)
ax.hist(mc_sv*100, bins=bins, color=GOLD, alpha=0.55, label="Small-Cap Value", zorder=3)
ax.axvline(0, color=INK, linewidth=1)
ax.set_xlabel("25-year annualized return (simulated)")
ax.set_ylabel("Number of simulated paths")
ax.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
style_ax(ax)
ax.legend(frameon=False, loc="upper right", fontsize=9.5)
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\l25_chart3_mc_dist.png")
plt.close()

# =============================================================================
# CHART 4: distribution of 2x Market CAGR minus SCV CAGR (Monte Carlo)
# =============================================================================
diff = mc_lev - mc_sv
fig, ax = plt.subplots(figsize=(9.5, 4.4), dpi=170)
bins = np.linspace(np.percentile(diff,0.1)*100, np.percentile(diff,99.9)*100, 70)
counts, edges, patches = ax.hist(diff*100, bins=bins, zorder=3)
for c, p in zip(edges[:-1], patches):
    p.set_facecolor(GOLD if c < 0 else PURPLE)
    p.set_alpha(0.75)
ax.axvline(0, color=INK, linewidth=1.2)
pct_neg = (diff < 0).mean() * 100
ax.set_xlabel("2x Market minus SCV, 25-year annualized return")
ax.set_ylabel("Number of simulated paths")
ax.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
style_ax(ax)
ax.text(0.02, 0.94, f"SCV ahead of 2x Market in {pct_neg:.1f}% of paths\n2x Market ahead in {100-pct_neg:.1f}% of paths",
        transform=ax.transAxes, fontsize=9.5, color=INK700, va="top",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor=INK500, linewidth=0.8, alpha=0.92))
legend_els = [Patch(facecolor=PURPLE, alpha=0.75, label="2x Market ahead"),
              Patch(facecolor=GOLD, alpha=0.75, label="SCV ahead")]
ax.legend(handles=legend_els, frameon=False, loc="upper right", fontsize=9.5)
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\l25_chart4_diff.png")
plt.close()

# =============================================================================
# CHART 5: Drawdown comparison -- historical full-period drawdown series
# =============================================================================
def dd_series(nav):
    peak = np.maximum.accumulate(nav)
    return nav / peak - 1.0

dd_mkt = dd_series(mkt_nav)
dd_lev = dd_series(lev_nav)
dd_sv = dd_series(sv_nav)

fig, ax = plt.subplots(figsize=(9.5, 4.2), dpi=170)
ax.fill_between(dates, dd_lev*100, 0, color=PURPLE, alpha=0.55, label=f"2x Market (max {dd_lev.min()*100:.0f}%)", linewidth=0)
ax.fill_between(dates, dd_sv*100, 0, color=GOLD, alpha=0.55, label=f"Small-Cap Value (max {dd_sv.min()*100:.0f}%)", linewidth=0)
ax.fill_between(dates, dd_mkt*100, 0, color=STEEL, alpha=0.7, label=f"Market (max {dd_mkt.min()*100:.0f}%)", linewidth=0)
ax.set_ylabel("Drawdown from prior peak")
ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
style_ax(ax)
ax.legend(frameon=False, loc="lower left", fontsize=9.5)
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\l25_chart5_drawdowns.png")
plt.close()

print("All lev25 charts saved.")
