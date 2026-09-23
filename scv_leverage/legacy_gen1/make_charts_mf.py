import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import json

SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"

INK="#171a1f"; INK700="#3b3f47"; INK500="#6b6f78"; LINE="#dcd6c8"
GOLD="#a8792f"; STEEL="#3c6b8f"; TEAL="#3c8f7f"; PURPLE="#7a5b96"; RUST="#b5622f"
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

df = pd.read_csv(rf"{SCRATCH}\mf_monthly.csv", index_col=0)
periods = pd.PeriodIndex(df.index, freq="M").to_timestamp()

with open(rf"{SCRATCH}\mf_kelly_summary.json") as f:
    OUT = json.load(f)

# =============================================================================
# CHART 1: Growth of $1 -- Market, 2xMarket, and the three 50/50 diversified portfolios
# =============================================================================
fig, ax = plt.subplots(figsize=(9.7, 5.0), dpi=170)
series = {
    "Mkt": ("Market", STEEL),
    "Lev": ("2x Market", PURPLE),
    "Port_SCV_m": ("50/50 2x Market + SCV", GOLD),
    "Port_Bond_m": ("50/50 2x Market + Bonds", TEAL),
    "Port_MF_m": ("50/50 2x Market + Managed Futures", RUST),
}
navs = {}
for col, (label, color) in series.items():
    nav = (1 + df[col]).cumprod()
    navs[col] = nav
    ax.plot(periods, nav, color=color, linewidth=1.6, label=label)
ax.set_yscale("log")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,p: f"${v:,.0f}" if v>=1 else f"${v:.2f}"))
ax.set_ylabel("Growth of $1 (log scale), Jan 1985 = $1")
style_ax(ax)
leg = ax.legend(loc="upper left", fontsize=9, framealpha=0.92, edgecolor=LINE)
leg.get_frame().set_facecolor(PAPER)
for col in series:
    ax.annotate(f"${navs[col].iloc[-1]:,.0f}", xy=(periods[-1], navs[col].iloc[-1]), xytext=(6,0),
                textcoords="offset points", color=series[col][1], fontsize=8.5, fontweight="bold", va="center")
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\mf_chart1_growth.png")
plt.close()

# =============================================================================
# CHART 2: Correlation matrix, 5 assets
# =============================================================================
corr_df = pd.DataFrame(OUT["correlations_mf_period"])
order_c = ["Mkt","Lev","SV","Bond","MF"]
corr_df = corr_df.loc[order_c, order_c]
labels_c = ["Market","2x Market","SCV","Bonds","Managed\nFutures"]

fig, ax = plt.subplots(figsize=(6.0,5.4), dpi=170)
data = corr_df.to_numpy()
cmap = plt.get_cmap("RdBu_r")
im = ax.imshow(data, cmap=cmap, vmin=-1, vmax=1)
ax.set_xticks(range(5)); ax.set_xticklabels(labels_c, rotation=30, ha="right", fontsize=9.5)
ax.set_yticks(range(5)); ax.set_yticklabels(labels_c, fontsize=9.5)
for i in range(5):
    for j in range(5):
        v = data[i,j]
        color = "white" if abs(v)>0.6 else INK
        ax.text(j,i,f"{v:.2f}", ha="center", va="center", fontsize=10.5, color=color, fontweight="bold" if i==j else "normal")
ax.spines[:].set_visible(False)
ax.tick_params(length=0)
cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.05)
cbar.ax.tick_params(labelsize=8, length=0)
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\mf_chart2_corr.png")
plt.close()

# =============================================================================
# CHART 3: Kelly criterion comparison bar chart
# =============================================================================
kelly = OUT["kelly"]
kelly_mf = OUT["kelly_mf"]
assets = [("Market", kelly["market"], STEEL), ("Small-Cap Value", kelly["scv"], GOLD), ("Managed Futures", kelly_mf, RUST)]
metrics = ["quarter_kelly", "half_kelly", "dd_adjusted_kelly", "log_optimal_kelly", "full_kelly"]
metric_labels = ["Quarter\nKelly", "Half\nKelly", "Drawdown-\nadjusted", "Log-optimal\n(grid search)", "Full\nKelly"]

fig, ax = plt.subplots(figsize=(9.5, 4.8), dpi=170)
n_assets = len(assets)
n_metrics = len(metrics)
bar_w = 0.25
x = np.arange(n_metrics)
for i, (name, k, color) in enumerate(assets):
    vals = [k[m] for m in metrics]
    offset = (i - (n_assets-1)/2) * bar_w
    bars = ax.bar(x + offset, vals, width=bar_w, color=color, alpha=0.85, label=name, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x()+b.get_width()/2, v + (0.08 if v>=0 else -0.25), f"{v:.1f}x", ha="center",
                fontsize=7.5, color=color, fontweight="bold")
ax.axhline(1.0, color=INK500, linewidth=0.8, linestyle="--", alpha=0.7)
ax.text(n_metrics-0.5, 1.05, "1.0x (fully invested, no leverage)", fontsize=8, color=INK500, ha="right")
ax.set_xticks(x); ax.set_xticklabels(metric_labels, fontsize=9.5)
ax.set_ylabel("Implied leverage / position size")
style_ax(ax)
ax.legend(frameon=False, loc="upper left", fontsize=9.5)
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\mf_chart3_kelly.png")
plt.close()

print("All MF + Kelly charts saved.")
