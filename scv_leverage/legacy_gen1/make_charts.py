import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Patch

SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"
ROOT = r"c:\Python Datoteke"

# palette matching the report tokens
INK = "#171a1f"
INK700 = "#3b3f47"
INK500 = "#6b6f78"
LINE = "#dcd6c8"
GOLD = "#a8792f"
GOLD_SOFT = "#e9d6ab"
STEEL = "#3c6b8f"
STEEL_SOFT = "#b9d3e3"
DANGER = "#a8432f"
GOOD = "#3f7d52"
PAPER = "#fffdf9"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.edgecolor": LINE,
    "axes.labelcolor": INK700,
    "text.color": INK,
    "xtick.color": INK500,
    "ytick.color": INK500,
    "axes.facecolor": PAPER,
    "figure.facecolor": PAPER,
    "savefig.facecolor": PAPER,
    "font.size": 11,
})

# --- reload data needed for charts ---
mkt = pd.read_csv(rf"{ROOT}\F-F_Research_Data_Factors_daily.csv", skiprows=4, encoding="utf-8-sig")
mkt.columns = ["date", "Mkt-RF", "SMB", "HML", "RF"]
mkt["date"] = pd.to_datetime(mkt["date"], format="%Y%m%d", errors="coerce")
mkt = mkt.dropna(subset=["date"])
for c in ["Mkt-RF", "SMB", "HML", "RF"]:
    mkt[c] = pd.to_numeric(mkt[c], errors="coerce")
mkt = mkt.dropna(subset=["Mkt-RF", "RF"]).reset_index(drop=True)
mkt["Mkt_Total"] = (mkt["Mkt-RF"] + mkt["RF"]) / 100.0

sv = pd.read_csv(rf"{SCRATCH}\ff6\6_Portfolios_2x3_Daily.csv", skiprows=18, nrows=26293 - 19)
sv.columns = ["date", "SMALL_LoBM", "ME1_BM2", "SMALL_HiBM", "BIG_LoBM", "ME2_BM2", "BIG_HiBM"]
sv["date"] = pd.to_datetime(sv["date"], format="%Y%m%d", errors="coerce")
sv = sv.dropna(subset=["date"])
sv["SV_Total"] = pd.to_numeric(sv["SMALL_HiBM"], errors="coerce") / 100.0
sv = sv.dropna(subset=["SV_Total"]).reset_index(drop=True)

df = pd.merge(mkt[["date", "Mkt_Total"]], sv[["date", "SV_Total"]], on="date", how="inner")
df = df.sort_values("date").reset_index(drop=True).set_index("date")

mkt_nav = (1 + df["Mkt_Total"]).cumprod()
sv_nav = (1 + df["SV_Total"]).cumprod()

annual_full = pd.read_csv(rf"{SCRATCH}\annual_full.csv", index_col=0)

end_dates = pd.to_datetime(np.load(rf"{SCRATCH}\rolling_end_dates.npy"))
roll_mkt = np.load(rf"{SCRATCH}\rolling_mkt_ann.npy")
roll_sv = np.load(rf"{SCRATCH}\rolling_sv_ann.npy")
roll_diff = np.load(rf"{SCRATCH}\rolling_diff_ann.npy")

mc_diff = np.load(rf"{SCRATCH}\mc_diff_ann.npy")
mc_mkt = np.load(rf"{SCRATCH}\mc_mkt_ann.npy")
mc_sv = np.load(rf"{SCRATCH}\mc_sv_ann.npy")

def style_ax(ax, grid_axis="y"):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.grid(axis=grid_axis, color=LINE, linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)

# =============================================================================
# CHART 1: Cumulative growth of $1 (log scale)
# =============================================================================
fig, ax = plt.subplots(figsize=(9.5, 4.6), dpi=170)
ax.plot(mkt_nav.index, mkt_nav.values, color=STEEL, linewidth=1.6, label="Market")
ax.plot(sv_nav.index, sv_nav.values, color=GOLD, linewidth=1.6, label="Small-Cap Value")
ax.set_yscale("log")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"${v:,.0f}" if v>=1 else f"${v:.2f}"))
ax.set_ylabel("Growth of $1 (log scale)")
style_ax(ax)
ax.legend(frameon=False, loc="upper left", fontsize=10)
ax.annotate(f"${sv_nav.iloc[-1]:,.0f}", xy=(sv_nav.index[-1], sv_nav.iloc[-1]), xytext=(6,0),
            textcoords="offset points", color=GOLD, fontsize=9, fontweight="bold", va="center")
ax.annotate(f"${mkt_nav.iloc[-1]:,.0f}", xy=(mkt_nav.index[-1], mkt_nav.iloc[-1]), xytext=(6,0),
            textcoords="offset points", color=STEEL, fontsize=9, fontweight="bold", va="center")
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\chart1_cumulative.png")
plt.close()

# =============================================================================
# CHART 2: Annual returns, every year, paired bars
# =============================================================================
years = annual_full.index.values
mkt_yr = annual_full["Mkt"].values * 100
sv_yr = annual_full["SV"].values * 100

fig, ax = plt.subplots(figsize=(13.5, 5.4), dpi=170)
x = np.arange(len(years))
w = 0.4
ax.bar(x - w/2, mkt_yr, width=w, color=STEEL, label="Market", zorder=3)
ax.bar(x + w/2, sv_yr, width=w, color=GOLD, label="Small-Cap Value", zorder=3)
ax.axhline(0, color=INK500, linewidth=0.8, zorder=2)
tick_idx = [i for i, y in enumerate(years) if y % 10 == 0]
ax.set_xticks(tick_idx)
ax.set_xticklabels([str(years[i]) for i in tick_idx], fontsize=9)
ax.set_ylabel("Annual return")
ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
style_ax(ax)
ax.legend(frameon=False, loc="upper right", fontsize=10)
ax.set_xlim(-1, len(years))
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\chart2_annual.png")
plt.close()

# =============================================================================
# CHART 3: rolling 10yr annualized return lines + difference panel
# =============================================================================
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6.6), dpi=170, sharex=True,
                                 gridspec_kw={"height_ratios": [2, 1.1], "hspace": 0.12})
ax1.plot(end_dates, roll_mkt*100, color=STEEL, linewidth=1.4, label="Market (10yr ann.)")
ax1.plot(end_dates, roll_sv*100, color=GOLD, linewidth=1.4, label="Small-Cap Value (10yr ann.)")
ax1.axhline(0, color=INK500, linewidth=0.7)
ax1.set_ylabel("Rolling 10yr\nannualized return")
ax1.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
style_ax(ax1)
ax1.legend(frameon=False, loc="upper right", fontsize=9.5)

ax2.fill_between(end_dates, roll_diff*100, 0, where=(roll_diff>=0), color=GOOD, alpha=0.55, linewidth=0, step=None)
ax2.fill_between(end_dates, roll_diff*100, 0, where=(roll_diff<0), color=DANGER, alpha=0.65, linewidth=0, step=None)
ax2.axhline(0, color=INK, linewidth=0.9)
ax2.set_ylabel("SCV minus\nMarket (pp)")
style_ax(ax2)
ax2.set_xlabel("Rolling 10-year window (labeled by end date)")
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\chart3_rolling.png")
plt.close()

# =============================================================================
# CHART 4: distribution of rolling 10yr annualized returns (both)
# =============================================================================
fig, ax = plt.subplots(figsize=(9.5, 4.4), dpi=170)
bins = np.linspace(min(roll_mkt.min(), roll_sv.min())*100 - 1, max(roll_mkt.max(), roll_sv.max())*100 + 1, 46)
ax.hist(roll_mkt*100, bins=bins, color=STEEL, alpha=0.62, label="Market", zorder=3)
ax.hist(roll_sv*100, bins=bins, color=GOLD, alpha=0.62, label="Small-Cap Value", zorder=3)
ax.axvline(0, color=INK, linewidth=1)
ax.set_xlabel("10-year annualized return")
ax.set_ylabel("Number of rolling windows")
ax.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
style_ax(ax)
ax.legend(frameon=False, loc="upper right", fontsize=10)
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\chart4_dist_levels.png")
plt.close()

# =============================================================================
# CHART 5: distribution of SCV-Market difference (historical), highlight negative
# =============================================================================
fig, ax = plt.subplots(figsize=(9.5, 4.4), dpi=170)
bins = np.linspace(roll_diff.min()*100 - 0.5, roll_diff.max()*100 + 0.5, 46)
counts, edges, patches = ax.hist(roll_diff*100, bins=bins, zorder=3)
for c, p in zip(edges[:-1], patches):
    p.set_facecolor(DANGER if c < 0 else GOOD)
    p.set_alpha(0.75)
ax.axvline(0, color=INK, linewidth=1.2)
pct_neg = (roll_diff < 0).mean() * 100
ax.set_xlabel("SCV minus Market, 10-year annualized return")
ax.set_ylabel("Number of rolling windows")
ax.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
style_ax(ax)
ax.text(0.02, 0.94, f"SCV underperformed in {pct_neg:.1f}% of\nhistorical 10-year windows",
        transform=ax.transAxes, fontsize=10, color=DANGER, va="top",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor=DANGER, linewidth=0.8, alpha=0.9))
legend_els = [Patch(facecolor=GOOD, alpha=0.75, label="SCV outperformed"),
              Patch(facecolor=DANGER, alpha=0.75, label="SCV underperformed")]
ax.legend(handles=legend_els, frameon=False, loc="upper right", fontsize=9.5)
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\chart5_dist_diff_hist.png")
plt.close()

# =============================================================================
# CHART 6: Monte Carlo distribution of SCV-Market annualized difference
# =============================================================================
fig, ax = plt.subplots(figsize=(9.5, 4.4), dpi=170)
bins = np.linspace(np.percentile(mc_diff,0.1)*100, np.percentile(mc_diff,99.9)*100, 70)
counts, edges, patches = ax.hist(mc_diff*100, bins=bins, zorder=3)
for c, p in zip(edges[:-1], patches):
    p.set_facecolor(DANGER if c < 0 else GOLD)
    p.set_alpha(0.75)
ax.axvline(0, color=INK, linewidth=1.2)
pct_neg_mc = (mc_diff < 0).mean() * 100
ax.set_xlabel("SCV minus Market, 10-year annualized return")
ax.set_ylabel("Number of simulated paths")
ax.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
style_ax(ax)
ax.text(0.02, 0.94, f"SCV underperformed in {pct_neg_mc:.1f}% of\n100,000 simulated 10-year paths",
        transform=ax.transAxes, fontsize=10, color=DANGER, va="top",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor=DANGER, linewidth=0.8, alpha=0.9))
legend_els = [Patch(facecolor=GOLD, alpha=0.75, label="SCV outperformed"),
              Patch(facecolor=DANGER, alpha=0.75, label="SCV underperformed")]
ax.legend(handles=legend_els, frameon=False, loc="upper right", fontsize=9.5)
plt.tight_layout()
plt.savefig(rf"{SCRATCH}\chart6_dist_diff_mc.png")
plt.close()

print("All charts saved.")
