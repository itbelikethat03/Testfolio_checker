import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Patch
import json

SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"

INK="#171a1f"; INK700="#3b3f47"; INK500="#6b6f78"; LINE="#dcd6c8"
GOLD="#a8792f"; STEEL="#3c6b8f"; DANGER="#a8432f"; GOOD="#3f7d52"; PURPLE="#7a5b96"; TEAL="#3c8f7f"
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

with open(rf"{SCRATCH}\div_summary.json") as f:
    OUT = json.load(f)

mkt = np.load(rf"{SCRATCH}\div_mkt.npy"); lev = np.load(rf"{SCRATCH}\div_lev.npy")
sv = np.load(rf"{SCRATCH}\div_sv.npy"); bond = np.load(rf"{SCRATCH}\div_bond.npy")
port_scv = np.load(rf"{SCRATCH}\div_port_scv_m.npy"); port_bond = np.load(rf"{SCRATCH}\div_port_bond_m.npy")
periods = np.load(rf"{SCRATCH}\div_periods.npy", allow_pickle=True)
dates = pd.PeriodIndex(periods, freq="M").to_timestamp()

series = dict(mkt=mkt, lev=lev, sv=sv, port_scv=port_scv, port_bond=port_bond)
colors = dict(mkt=STEEL, lev=PURPLE, sv=GOLD, port_scv="#c9974a", port_bond=TEAL)
labels = dict(mkt="Market", lev="2x Market", sv="Small-Cap Value",
              port_scv="50/50 2x Market + SCV", port_bond="50/50 2x Market + Bonds")

# =============================================================================
# CHART 1: Growth of $1
# =============================================================================
fig, ax = plt.subplots(figsize=(9.7, 5.0), dpi=170)
navs = {}
for k, r in series.items():
    nav = (1+r).cumprod()
    navs[k] = nav
    ax.plot(dates, nav, color=colors[k], linewidth=1.5, label=labels[k])
ax.set_yscale("log")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,p: f"${v:,.0f}" if v>=1 else f"${v:.2f}"))
ax.set_ylabel("Growth of $1 (log scale)")
style_ax(ax)
leg1 = ax.legend(loc="upper left", fontsize=9, framealpha=0.92, edgecolor=LINE)
leg1.get_frame().set_facecolor(PAPER)
# stagger end-labels in log-space so close-together final values don't overlap
end_vals = sorted(((navs[k][-1], k) for k in series), key=lambda t: t[0])
min_gap_log = 0.16
adj_y = {}
prev_log = None
for val, k in end_vals:
    y = np.log10(val)
    if prev_log is not None and y - prev_log < min_gap_log:
        y = prev_log + min_gap_log
    adj_y[k] = y
    prev_log = y
for k in series:
    y_disp = 10 ** adj_y[k]
    ax.annotate(f"${navs[k][-1]:,.0f}", xy=(dates[-1], y_disp), xytext=(6,0),
                textcoords="offset points", color=colors[k], fontsize=8.5, fontweight="bold", va="center")
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\div_chart1_growth.png")
plt.close()

# =============================================================================
# CHART 2: Rolling 25yr annualized returns
# =============================================================================
win_end_str = np.load(rf"{SCRATCH}\div_roll_win_end.npy", allow_pickle=True)
win_end = pd.PeriodIndex(win_end_str, freq="M").to_timestamp()
ann = {k: np.load(rf"{SCRATCH}\div_roll_ann_{k}.npy") for k in series}

fig, ax = plt.subplots(figsize=(9.8, 5.0), dpi=170)
for k in series:
    ax.plot(win_end, ann[k]*100, color=colors[k], linewidth=1.4, label=labels[k])
ax.axhline(0, color=INK500, linewidth=0.7)
ax.set_ylabel("Rolling 25-year annualized return")
ax.set_xlabel("Rolling 25-year window (labeled by end date)")
ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
style_ax(ax)
leg = ax.legend(loc="upper left", fontsize=8.7, ncol=2, framealpha=0.92, edgecolor=LINE)
leg.get_frame().set_facecolor(PAPER)
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\div_chart2_rolling.png")
plt.close()

# =============================================================================
# CHART 3: MC CAGR distribution
# =============================================================================
mc_ann = {k: np.load(rf"{SCRATCH}\div_mc_ann_{k}.npy") for k in series}
fig, ax = plt.subplots(figsize=(9.7, 4.8), dpi=170)
lo = min(v.min() for v in mc_ann.values())*100
hi = max(v.max() for v in mc_ann.values())*100
bins = np.linspace(lo, hi, 90)
for k in ["mkt","lev","sv","port_scv","port_bond"]:
    ax.hist(mc_ann[k]*100, bins=bins, color=colors[k], alpha=0.45, label=labels[k], zorder=3)
ax.axvline(0, color=INK, linewidth=1)
ax.set_xlabel("25-year annualized return (simulated)")
ax.set_ylabel("Number of simulated paths")
ax.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
style_ax(ax)
ax.legend(frameon=False, loc="upper right", fontsize=8.7)
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\div_chart3_mc_dist.png")
plt.close()

# =============================================================================
# CHART 4: Max drawdown distribution (MC) -- horizontal box-style via percentile bars
# =============================================================================
mc_dd = {k: np.load(rf"{SCRATCH}\div_mc_dd_{k}.npy") for k in series}
fig, ax = plt.subplots(figsize=(9.5, 4.6), dpi=170)
order = ["port_bond","sv","mkt","port_scv","lev"]
ypos = np.arange(len(order))
for i, k in enumerate(order):
    d = mc_dd[k]*100
    p5, p25, p50, p75, p95 = np.percentile(d, [5,25,50,75,95])
    ax.plot([p5,p95],[i,i], color=colors[k], linewidth=2, alpha=0.5, zorder=2)
    ax.plot([p25,p75],[i,i], color=colors[k], linewidth=8, alpha=0.85, zorder=3, solid_capstyle="butt")
    ax.plot([p50],[i], marker="o", color=INK, markersize=6, zorder=4)
    ax.text(p95+1, i, f"p50 {p50:.0f}%", va="center", fontsize=9, color=INK700)
ax.set_yticks(ypos)
ax.set_yticklabels([labels[k] for k in order], fontsize=10)
ax.set_xlabel("Max drawdown over a simulated 25-year path")
ax.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
ax.set_xlim(-105, 15)
style_ax(ax, grid_axis="x")
ax.invert_xaxis()
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\div_chart4_dd_dist.png")
plt.close()

# =============================================================================
# CHART 5: SCV vs Bonds -- distribution of port_scv minus port_bond (MC)
# =============================================================================
diff = mc_ann["port_scv"] - mc_ann["port_bond"]
fig, ax = plt.subplots(figsize=(9.5, 4.4), dpi=170)
bins = np.linspace(np.percentile(diff,0.1)*100, np.percentile(diff,99.9)*100, 70)
counts, edges, patches = ax.hist(diff*100, bins=bins, zorder=3)
for c,p in zip(edges[:-1], patches):
    p.set_facecolor(TEAL if c<0 else "#c9974a")
    p.set_alpha(0.8)
ax.axvline(0, color=INK, linewidth=1.2)
pct_neg = (diff<0).mean()*100
ax.set_xlabel("50/50 2x Market+SCV minus 50/50 2x Market+Bonds, 25yr annualized return")
ax.set_ylabel("Number of simulated paths")
ax.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
style_ax(ax)
ax.text(0.02,0.94, f"Bonds ahead in {pct_neg:.1f}% of paths\nSCV ahead in {100-pct_neg:.1f}% of paths",
        transform=ax.transAxes, fontsize=9.5, color=INK700, va="top",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor=INK500, linewidth=0.8, alpha=0.92))
legend_els=[Patch(facecolor="#c9974a", alpha=0.8, label="SCV portfolio ahead"), Patch(facecolor=TEAL, alpha=0.8, label="Bond portfolio ahead")]
ax.legend(handles=legend_els, frameon=False, loc="upper right", fontsize=9.5)
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\div_chart5_scv_vs_bond.png")
plt.close()

# =============================================================================
# CHART 6: Correlation matrix
# =============================================================================
corr_df = pd.DataFrame(OUT["correlations"])
order_c = ["Mkt","Lev","SV","Bond"]
corr_df = corr_df.loc[order_c, order_c]
labels_c = ["Market","2x Market","SCV","Bonds"]

fig, ax = plt.subplots(figsize=(5.6,5.0), dpi=170)
data = corr_df.to_numpy()
cmap = plt.get_cmap("RdBu_r")
im = ax.imshow(data, cmap=cmap, vmin=-1, vmax=1)
ax.set_xticks(range(4)); ax.set_xticklabels(labels_c, rotation=30, ha="right", fontsize=10)
ax.set_yticks(range(4)); ax.set_yticklabels(labels_c, fontsize=10)
for i in range(4):
    for j in range(4):
        v = data[i,j]
        color = "white" if abs(v)>0.6 else INK
        ax.text(j,i,f"{v:.2f}", ha="center", va="center", fontsize=11, color=color, fontweight="bold" if i==j else "normal")
ax.spines[:].set_visible(False)
ax.tick_params(length=0)
cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.05)
cbar.ax.tick_params(labelsize=8, length=0)
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\div_chart6_corr.png")
plt.close()

print("All diversification charts saved.")
