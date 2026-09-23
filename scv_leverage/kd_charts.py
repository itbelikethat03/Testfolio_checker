"""
PHASE 10 -- visualisations. Matches the house style already used by
make_charts_lev25.py / make_charts_div.py.

Palette notes (all machine-checked, not eyeballed):
  * 2-series categorical (market / small-cap value): #3c6b8f, #a8792f
    -> CVD dE 17.3, normal dE 20.8, contrast pass.
  * 4-series categorical (best / worst / both / random scenarios):
    #5b8db3, #a8792f, #8f2f2f, #6b4f8f
    -> CVD dE 13.8, normal dE 15.8, contrast pass.
    (The project's original 4-colour set failed: red vs green CVD dE 4.7.)
  * Kelly fraction and X are ORDINAL, so they use a single-hue sequential ramp
    (monotone OKLCH lightness, min delta-L 0.076, lightest step contrast 2.24).
The CSVs in kelly_bestdays/ are the table view for every chart here.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D
import os
from kd_data import OUTDIR

CH = rf"{OUTDIR}\charts"
os.makedirs(CH, exist_ok=True)

INK = "#171a1f"; INK700 = "#3b3f47"; INK500 = "#6b6f78"; LINE = "#dcd6c8"
PAPER = "#fffdf9"
MKT, SCV = "#3c6b8f", "#a8792f"
SC4 = {"best": "#8f2f2f", "worst": "#5b8db3", "both": "#6b4f8f", "random": "#a8792f"}
RAMP = ["#8fb0c9", "#6d96b3", "#4b7d9d", "#316685", "#1f4f6c", "#123852"]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "axes.edgecolor": LINE, "axes.labelcolor": INK700,
    "text.color": INK, "xtick.color": INK500, "ytick.color": INK500,
    "axes.facecolor": PAPER, "figure.facecolor": PAPER,
    "savefig.facecolor": PAPER, "font.size": 10.5,
})


def style_ax(ax, grid_axis="y"):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.grid(axis=grid_axis, color=LINE, linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def pct(ax, dec=0):
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v*100:.{dec}f}%"))


rem = pd.read_csv(rf"{OUTDIR}\phase346_removal.csv")
ctl = pd.read_csv(rf"{OUTDIR}\phase5_random_control.csv")
draws = pd.read_csv(rf"{OUTDIR}\phase5_random_draws.csv")
XS = sorted(rem.X.unique())
POS = np.arange(len(XS))
SER = [("mkt", "Broad market", MKT), ("scv", "Small-cap value", SCV)]


def xaxis_X(ax):
    ax.set_xticks(POS)
    ax.set_xticklabels([str(x) for x in XS])
    ax.set_xlabel("Number of best trading days removed (out of 26,233)")


# ============================================================ CHART 1 =======
fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.7), dpi=170)
for ax, (metric, ylab, title) in zip(axes, [
        ("kelly_emp", "Full Kelly f* (x leverage)", "Optimal Kelly allocation"),
        ("pct", "f* as % of full-sample f*", "Relative to the untouched sample")]):
    for key, lbl, col in SER:
        s = rem[(rem.series == key) & (rem["mode"] == "best")].set_index("X").loc[XS]
        y = s["kelly_emp"].to_numpy()
        y = y if metric == "kelly_emp" else y / y[0]
        ax.plot(POS, y, color=col, lw=2, marker="o", ms=6,
                mec=PAPER, mew=1.5, label=lbl, zorder=3)
        # direct-label at X=100, where the two lines are well separated --
        # not at the right edge where they converge on zero and collide
        j = XS.index(100)
        ax.annotate(lbl, xy=(POS[j], y[j]),
                    xytext=(0, 9 if key == "scv" else -18),
                    textcoords="offset points", color=INK700, fontsize=9,
                    ha="center", fontweight="bold")
    ax.set_ylabel(ylab)
    ax.set_title(title, fontsize=11.5, color=INK, loc="left", pad=10)
    ax.axhline(0, color=INK500, lw=0.8, ls=(0, (4, 3)))
    style_ax(ax)
    xaxis_X(ax)
    if metric == "pct":
        pct(ax)
axes[0].legend(frameon=False, fontsize=9.5, loc="upper right")
fig.suptitle("Kelly criterion vs. number of best trading days removed",
             fontsize=13.5, color=INK, x=0.008, ha="left", y=0.985)
plt.tight_layout(rect=(0, 0, 1, 0.94))
plt.savefig(rf"{CH}\c1_kelly_vs_bestdays.png"); plt.close()

# ============================================================ CHART 2 =======
fig, axes = plt.subplots(2, 2, figsize=(11.5, 8), dpi=170)
panels = [("ann_arith_total", "Annualised arithmetic mean return", 1),
          ("ann_vol", "Annualised volatility", 1),
          ("cagr", "CAGR (geometric mean)", 1),
          ("max_dd", "Maximum drawdown", 0)]
for ax, (col, title, dec) in zip(axes.ravel(), panels):
    for key, lbl, c in SER:
        s = rem[(rem.series == key) & (rem["mode"] == "best")].set_index("X").loc[XS]
        ax.plot(POS, s[col], color=c, lw=2, marker="o", ms=5.5,
                mec=PAPER, mew=1.4, label=lbl, zorder=3)
    ax.set_title(title, fontsize=11, color=INK, loc="left", pad=8)
    ax.axhline(0, color=INK500, lw=0.8, ls=(0, (4, 3)))
    style_ax(ax); xaxis_X(ax); pct(ax, dec)
    ax.set_xlabel("Best days removed", fontsize=9.5)
axes[0, 0].legend(frameon=False, fontsize=9.5, loc="lower left")
fig.suptitle("What removing the best days does to each statistic",
             fontsize=13.5, color=INK, x=0.008, ha="left", y=0.99)
plt.tight_layout(rect=(0, 0, 1, 0.955))
plt.savefig(rf"{CH}\c2_metrics_vs_bestdays.png"); plt.close()

# ============================================================ CHART 3 =======
# random-removal null distribution vs the deliberate best-day removal
XS5 = sorted(ctl.X.unique())
P5 = np.arange(len(XS5))
fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.9), dpi=170, sharey=True)
for ax, (key, lbl, col) in zip(axes, SER):
    d = draws[draws.series == key]
    parts = [d[d.X == x]["kelly_emp"].to_numpy() for x in XS5]
    vp = ax.violinplot(parts, positions=P5, widths=0.72, showextrema=False)
    for b in vp["bodies"]:
        b.set_facecolor(INK500); b.set_alpha(0.30); b.set_edgecolor("none")
    c = ctl[ctl.series == key].set_index("X").loc[XS5]
    ax.plot(P5, c["treat_best_kelly_emp"], color=col, lw=2, marker="o", ms=7,
            mec=PAPER, mew=1.6, zorder=4)
    ax.axhline(c["base_kelly_emp"].iloc[0], color=INK500, lw=1, ls=(0, (4, 3)))
    ax.annotate(f"full-sample f* = {c['base_kelly_emp'].iloc[0]:.2f}x",
                xy=(0, c["base_kelly_emp"].iloc[0]), xytext=(2, 6),
                textcoords="offset points", color=INK500, fontsize=8.5)
    ax.set_title(lbl, fontsize=11.5, color=INK, loc="left", pad=8)
    ax.set_xticks(P5); ax.set_xticklabels([str(x) for x in XS5])
    ax.set_xlabel("X days removed")
    style_ax(ax)
axes[0].set_ylabel("Full Kelly f* (x leverage)")
axes[0].legend(handles=[
    Line2D([], [], color=INK500, lw=7, alpha=0.35, label="X RANDOM days removed (2,000 draws)"),
    Line2D([], [], color=INK700, lw=2, marker="o", ms=7, label="X BEST days removed")],
    frameon=False, fontsize=9.5, loc="lower left")
fig.suptitle("The effect is the positive tail, not sample size: random removal barely moves f*",
             fontsize=13, color=INK, x=0.008, ha="left", y=0.985)
plt.tight_layout(rect=(0, 0, 1, 0.93))
plt.savefig(rf"{CH}\c3_random_control.png"); plt.close()

# ============================================================ CHART 4 =======
fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.9), dpi=170, sharey=True)
for ax, (key, lbl, _) in zip(axes, SER):
    for mode, name in [("best", "Remove X best days"), ("worst", "Remove X worst days"),
                       ("both", "Remove X best + X worst")]:
        s = rem[(rem.series == key) & (rem["mode"] == mode)].set_index("X").loc[XS]
        ax.plot(POS, s["kelly_emp"], color=SC4[mode], lw=2, marker="o", ms=5.5,
                mec=PAPER, mew=1.4, label=name, zorder=3)
    c = ctl[ctl.series == key].set_index("X")
    ry = [rem[(rem.series == key) & (rem["mode"] == "best") & (rem.X == 0)]["kelly_emp"].iloc[0]] + \
         [c.loc[x, "rand_mean"] for x in XS[1:]]
    ax.plot(POS, ry, color=SC4["random"], lw=2, ls=(0, (5, 2)), marker="o", ms=5.5,
            mec=PAPER, mew=1.4, label="Remove X random days (mean)", zorder=3)
    ax.set_title(lbl, fontsize=11.5, color=INK, loc="left", pad=8)
    style_ax(ax); xaxis_X(ax)
    ax.set_xlabel("X days removed")
axes[0].set_ylabel("Full Kelly f* (x leverage)")
axes[0].legend(frameon=False, fontsize=9, loc="upper left")
fig.suptitle("Kelly is more sensitive to the negative tail than the positive tail",
             fontsize=13.5, color=INK, x=0.008, ha="left", y=0.985)
plt.tight_layout(rect=(0, 0, 1, 0.93))
plt.savefig(rf"{CH}\c4_tail_scenarios.png"); plt.close()
print(f"Historical charts written to {CH}")

# ============================================================ PHASE 14 ======
# Fractional Kelly vs best-day removal. Two ORDINAL families, so two
# single-hue ramps: fractions in the blue RAMP, removals in a red ramp.
p14 = rf"{OUTDIR}\phase14_scenarios.csv"
if os.path.exists(p14):
    sc = pd.read_csv(p14)
    g14 = pd.read_csv(rf"{OUTDIR}\phase14_grid.csv")
    pth = pd.read_csv(rf"{OUTDIR}\phase14_paths.csv", parse_dates=["date"])
    shr = pd.read_csv(rf"{OUTDIR}\phase14_growth_share.csv")
    sim = pd.read_csv(rf"{OUTDIR}\phase14_similarity.csv")
    hst = pd.read_csv(rf"{OUTDIR}\phase14_distribution.csv")
    X14 = [0, 10, 25, 100]
    FR14 = [("full", "Full Kelly"), ("half", "Half Kelly"), ("quarter", "Quarter Kelly")]
    FCOL = {"full": RAMP[5], "half": RAMP[3], "quarter": RAMP[0], "unlev": INK500}
    XCOL = {0: INK700, 10: "#d9a3a3", 25: "#b86565", 100: "#7a2323"}
    XMK = {0: "o", 10: "s", 25: "^", 100: "D"}
    fstar = {k: sc[(sc.series == k) & (sc.frac == "full")]["leverage"].iloc[0] for k, _, _ in SER}

    def logy(ax):
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(
            lambda v, p: f"${v:,.0f}" if v >= 1 else f"${v:g}"))

    def save(name, title, bottom=0.0):
        plt.gcf().suptitle(title, fontsize=13, color=INK, x=0.008, ha="left", y=0.985)
        plt.tight_layout(rect=(0, bottom, 1, 0.93))
        plt.savefig(rf"{CH}\{name}.png"); plt.close()

    # ---- c10: equity curves by fraction ------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.9), dpi=170)
    for ax, (key, lbl, _) in zip(axes, SER):
        p = pth[pth.series == key]
        for frac, name in FR14:
            ax.plot(p["date"], p[f"nav_{frac}_x0"], color=FCOL[frac], lw=1.8,
                    label=f"{name} ({fstar[key] * dict(full=1, half=.5, quarter=.25)[frac]:.2f}x)")
        logy(ax); style_ax(ax)
        ax.set_title(lbl, fontsize=11.5, color=INK, loc="left", pad=8)
    axes[0].set_ylabel("Growth of $1 (log)")
    axes[0].legend(frameon=False, fontsize=9, loc="upper left")
    save("c10_p14_equity_fractions", "Full, Half and Quarter Kelly on the untouched history")

    # ---- c11: Full Kelly equity curves after removal -----------------------
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.9), dpi=170)
    for ax, (key, lbl, _) in zip(axes, SER):
        p = pth[pth.series == key]
        for X in X14:
            ax.plot(p["date"], p[f"nav_full_x{X}"], color=XCOL[X], lw=1.8,
                    label="original" if X == 0 else f"-{X} best days")
        ax.plot(p["date"], p["nav_quarter_x0"], color=FCOL["quarter"], lw=1.6,
                ls=(0, (5, 2)), label="Quarter Kelly, original")
        logy(ax); style_ax(ax)
        ax.set_title(lbl, fontsize=11.5, color=INK, loc="left", pad=8)
    axes[0].set_ylabel("Growth of $1 (log)")
    axes[0].legend(frameon=False, fontsize=8.5, loc="upper left", title="Full Kelly",
                   title_fontsize=9)
    save("c11_p14_equity_removal",
         "Full Kelly with its best days removed (retained days in date order)")

    # ---- c12: drawdown curves ----------------------------------------------
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.6), dpi=170, sharey=True)
    for col, (key, lbl, _) in enumerate(SER):
        p = pth[pth.series == key]
        ax = axes[0, col]
        for frac, name in FR14:
            ax.plot(p["date"], p[f"dd_{frac}_x0"], color=FCOL[frac], lw=1.2, label=name)
        ax.set_title(f"{lbl} -- by Kelly fraction", fontsize=11, color=INK, loc="left", pad=8)
        ax = axes[1, col]
        for X in X14:
            ax.plot(p["date"], p[f"dd_full_x{X}"], color=XCOL[X], lw=1.2,
                    label="original" if X == 0 else f"-{X} best days")
        ax.set_title(f"{lbl} -- Full Kelly, best days removed", fontsize=11, color=INK,
                     loc="left", pad=8)
    for ax in axes.ravel():
        style_ax(ax); pct(ax)
    axes[0, 0].legend(frameon=False, fontsize=8.5, loc="lower right")
    axes[1, 0].legend(frameon=False, fontsize=8.5, loc="lower right")
    axes[0, 0].set_ylabel("Drawdown (monthly worst)"); axes[1, 0].set_ylabel("Drawdown (monthly worst)")
    save("c12_p14_drawdowns", "Drawdown from previous peak: leverage moves depth, removal moves duration")

    # ---- c13 / c14: CAGR and Sharpe against max drawdown --------------------
    for fname, ycol, ylab, title in [
            ("c13_p14_cagr_vs_dd", "cagr", "CAGR", "CAGR against maximum drawdown"),
            ("c14_p14_sharpe_vs_dd", "sharpe", "Sharpe ratio", "Sharpe against maximum drawdown")]:
        fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.1), dpi=170)
        for ax, (key, lbl, _) in zip(axes, SER):
            s = sc[sc.series == key]
            gf = g14[(g14.series == key) & (g14.frac == "full") & (g14.X <= 100)].sort_values("X")
            ax.plot(gf["max_dd"], gf[ycol], color=XCOL[100], lw=0.9, alpha=.6, zorder=2,
                    label="Full Kelly, X = 0..100 (fine grid)")
            for frac, name in FR14:
                for X in X14:
                    r = s[(s.frac == frac) & (s.X == X)].iloc[0]
                    ax.scatter(r["max_dd"], r[ycol], s=60, marker=XMK[X], color=FCOL[frac],
                               edgecolor=PAPER, linewidth=1.2, zorder=4)
            ax.axhline(0, color=INK500, lw=0.8, ls=(0, (4, 3)))
            ax.set_title(lbl, fontsize=11.5, color=INK, loc="left", pad=8)
            ax.set_xlabel("Maximum drawdown")
            ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v*100:.0f}%"))
            style_ax(ax, "both")
            if ycol == "cagr":
                pct(ax)
        axes[0].set_ylabel(ylab)
        handles = [Line2D([], [], ls="", marker="o", ms=8, color=FCOL[f], label=n) for f, n in FR14] + \
                  [Line2D([], [], ls="", marker=XMK[X], ms=7, color=INK500,
                          label="original" if X == 0 else f"-{X} best days") for X in X14] + \
                  [Line2D([], [], color=XCOL[100], lw=1, label="Full Kelly, fine X grid")]
        axes[0].legend(handles=handles, frameon=False, fontsize=8, loc="lower right", ncol=2,
                       numpoints=1)
        save(fname, title + " -- colour = Kelly fraction, shape = best days removed")

    # ---- c15: share of log wealth creation from the best days --------------
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.7), dpi=170, sharey=True)
    fams = FR14 + [("unlev", "Unlevered 1.00x")]
    w = 0.2
    for ax, (key, lbl, _) in zip(axes, SER):
        s = shr[shr.series == key]
        for i, (frac, name) in enumerate(fams):
            v = [s[(s.frac == frac) & (s.X == X)]["share_of_log_growth"].iloc[0] for X in (10, 25, 100)]
            xs = np.arange(3) + (i - 1.5) * w
            ax.bar(xs, v, width=w * .92, color=FCOL[frac], label=name, zorder=3)
            for x, y in zip(xs, v):
                ax.annotate(f"{y*100:.0f}%", xy=(x, y), xytext=(0, 3), textcoords="offset points",
                            ha="center", fontsize=7.5, color=INK700)
        ax.axhline(1.0, color=INK500, lw=0.9, ls=(0, (4, 3)))
        ax.set_xticks(range(3)); ax.set_xticklabels(["best 10 days", "best 25 days", "best 100 days"])
        ax.set_title(lbl, fontsize=11.5, color=INK, loc="left", pad=8)
        style_ax(ax); pct(ax)
    axes[0].set_ylabel("Share of total log wealth creation")
    axes[0].legend(frameon=False, fontsize=8.5, loc="upper left")
    save("c15_p14_growth_share",
         "How much of all compounded growth the best days supplied (100% = all of it)")

    # ---- c16: similarity heatmap -------------------------------------------
    order16 = [f"{f}_x{X}" for f, _ in FR14 for X in X14]
    short = {f"{f}_x{X}": f"{f[0].upper()}{'' if X == 0 else f' -{X}'}" for f, _ in FR14 for X in X14}
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.9), dpi=170)
    for ax, (key, lbl, _) in zip(axes, SER):
        s = sim[(sim.series == key) & (sim.variant == "primary")]
        M = s.pivot(index="from_id", columns="to_id", values="dist_all").loc[order16, order16]
        im = ax.imshow(M.to_numpy(), cmap="Blues_r", vmin=0, vmax=float(M.to_numpy().max()))
        for i in range(len(order16)):
            for j in range(len(order16)):
                v = M.iloc[i, j]
                ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=6.5,
                        color=PAPER if v < M.to_numpy().max() * .45 else INK)
        ax.set_xticks(range(12)); ax.set_xticklabels([short[c] for c in order16], fontsize=7.5, rotation=90)
        ax.set_yticks(range(12)); ax.set_yticklabels([short[c] for c in order16], fontsize=7.5)
        for v in (3.5, 7.5):
            ax.axhline(v, color=PAPER, lw=2); ax.axvline(v, color=PAPER, lw=2)
        ax.set_title(lbl, fontsize=11.5, color=INK, loc="left", pad=8)
        ax.tick_params(length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
    fig.text(0.01, 0.015, "F/H/Q = Full/Half/Quarter Kelly, -X = X best days removed. Cell = RMS "
             "z-scored gap over CAGR, vol, Sharpe, Sortino, max DD, Calmar, max-DD duration, "
             "log final wealth. 0 = identical.", fontsize=8, color=INK500)
    save("c16_p14_similarity", "How alike is each pair of scenarios? (lower = more similar)",
         bottom=0.04)

    # ---- c17: return distributions -----------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.7), dpi=170, sharey=True)
    for ax, (key, lbl, _) in zip(axes, SER):
        h = hst[hst.series == key]
        for scn, name, c, ls in [("full_x0", "Full Kelly", FCOL["full"], "-"),
                                 ("half_x0", "Half Kelly", FCOL["half"], "-"),
                                 ("quarter_x0", "Quarter Kelly", FCOL["quarter"], "-"),
                                 ("full_x100", "Full Kelly, -100 best days", XCOL[100], (0, (4, 2)))]:
            d = h[h.scenario == scn]
            ax.step((d["bin_lo"] + d["bin_hi"]) / 2, d["share"].clip(lower=1e-6), where="mid",
                    color=c, lw=1.5, ls=ls, label=name)
        ax.set_yscale("log"); ax.set_ylim(1e-5, 1)
        ax.set_title(lbl, fontsize=11.5, color=INK, loc="left", pad=8)
        ax.set_xlabel("Daily portfolio return (tails pooled into the end bins at +/-20%)")
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v*100:.0f}%"))
        style_ax(ax)
    axes[0].set_ylabel("Share of days (log)")
    axes[0].legend(frameon=False, fontsize=8.5, loc="upper left")
    save("c17_p14_distributions",
         "Leverage rescales the whole distribution; removal trims only the right tail")

    # ---- c18: walk-forward leverage through time ---------------------------
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.7), dpi=170, sharey=True)
    for ax, (key, lbl, _) in zip(axes, SER):
        p = pth[pth.series == key].dropna(subset=["wf_f_x0"])
        for X in X14:
            ax.plot(p["date"], p[f"wf_f_x{X}"], color=XCOL[X], lw=1.4,
                    label="original" if X == 0 else f"-{X} best days")
        ax.axhline(fstar[key], color=FCOL["full"], lw=1, ls=(0, (4, 3)))
        ax.annotate(f"fixed full-sample f* = {fstar[key]:.2f}x", xy=(p["date"].iloc[0], fstar[key]),
                    xytext=(2, 5), textcoords="offset points", fontsize=8.5, color=FCOL["full"])
        ax.set_title(lbl, fontsize=11.5, color=INK, loc="left", pad=8)
        style_ax(ax)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v:g}x"))
    axes[0].set_ylabel("Full-Kelly leverage (walk-forward)")
    axes[0].legend(frameon=False, fontsize=8.5, loc="lower right")
    save("c18_p14_walkforward_leverage",
         "Walk-forward Full Kelly: month-end expanding-window f*, clipped to 0-4x")

    # ---- c19: fingerprint -- which metrics each transformation moves ------
    # direction: +1 if a rise is better. Max DD and worst month are negative
    # numbers, so a NEGATIVE % change (shallower) is the improvement there.
    fp_metrics = [("cagr", "CAGR", 1), ("ann_vol", "Vol", -1), ("sharpe", "Sharpe", 1),
                  ("max_dd", "Max DD", -1), ("worst_month", "Worst mo.", -1),
                  ("mdd_duration_days", "DD length", -1), ("log_final_wealth", "log wealth", 1)]
    rows19 = [("half", 0, "Half Kelly"), ("quarter", 0, "Quarter Kelly"),
              ("full", 10, "Full -10 days"), ("full", 25, "Full -25 days"),
              ("full", 100, "Full -100 days")]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2), dpi=170)
    for ax, (key, lbl, _) in zip(axes, SER):
        s = sc[sc.series == key]
        b0 = s[(s.frac == "full") & (s.X == 0)].iloc[0]
        # log final wealth: a % change of $1M-scale endpoints is always ~-100%
        # and says nothing; the change in log wealth is proportional to CAGR*years
        M = np.array([[s[(s.frac == f) & (s.X == X)][m].iloc[0] / b0[m] - 1.0
                       for m, _, _ in fp_metrics] for f, X, _ in rows19])
        better = M * np.array([d for *_, d in fp_metrics])[None, :]
        ax.imshow(np.clip(better, -1, 1), cmap="RdBu", vmin=-1, vmax=1, aspect="auto")
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                ax.text(j, i, f"{M[i, j]*100:+.0f}%", ha="center", va="center", fontsize=7.5,
                        color=PAPER if abs(M[i, j]) > .6 else INK)
        ax.set_xticks(range(len(fp_metrics))); ax.set_xticklabels([n for _, n, _ in fp_metrics], fontsize=8.5)
        ax.set_yticks(range(len(rows19))); ax.set_yticklabels([n for *_, n in rows19], fontsize=8.5)
        ax.set_title(lbl, fontsize=11.5, color=INK, loc="left", pad=8)
        ax.tick_params(length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
    save("c19_p14_fingerprint",
         "% change vs Full Kelly on the original history -- blue = better, red = worse")
    print("  + Phase 14 charts c10-c19")

# ============================================================ MONTE CARLO ===
mc_path = rf"{OUTDIR}\phase79_montecarlo.csv"
if not os.path.exists(mc_path):
    print("Monte Carlo output not present -- skipping MC charts.")
    raise SystemExit(0)

mc = pd.read_csv(mc_path)
main = mc[mc.scheme == "block20"]
X_MC = sorted(main.X.unique())
FR = sorted(main[main.regime == "full"].frac.unique())
cmap = {x: RAMP[i * 2] for i, x in enumerate(X_MC)} if len(X_MC) <= 3 else \
       dict(zip(X_MC, [RAMP[0], RAMP[2], RAMP[4], RAMP[5]]))

# ---- C5: terminal-wealth distributions -------------------------------------
tw = np.load(rf"{OUTDIR}\phase79_terminal_wealth.npz")
fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.9), dpi=170)
bins = np.logspace(-2, 6, 110)   # wide enough not to clip the right tail
for ax, (key, lbl, _) in zip(axes, SER):
    for x in X_MC:
        k = f"{key}|{x}|full_1.00"
        if k not in tw:
            continue
        v = np.clip(tw[k], 1e-3, None)
        ax.hist(v, bins=bins, histtype="step", lw=2, color=cmap[x],
                label=f"X = {x} best days removed")
    ax.set_xscale("log")
    ax.axvline(1.0, color=INK500, lw=1, ls=(0, (4, 3)))
    ax.set_title(lbl, fontsize=11.5, color=INK, loc="left", pad=8)
    ax.set_xlabel("Terminal wealth after 25 years (start = $1, log scale)")
    ax.set_xticks([1e-2, 1e0, 1e2, 1e4, 1e6])   # sparse: full decades collide
    ax.xaxis.set_minor_locator(mticker.NullLocator())
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, p: f"${v:,.0f}" if v >= 1 else f"${v:.2f}"))
    style_ax(ax)
axes[0].set_ylabel("Simulated paths")
axes[0].legend(frameon=False, fontsize=8.5, loc="upper right")
fig.suptitle("Terminal wealth at FULL Kelly sized on the untouched history, "
             "under the stressed return distribution",
             fontsize=12.5, color=INK, x=0.008, ha="left", y=0.985)
plt.tight_layout(rect=(0, 0, 1, 0.93))
plt.savefig(rf"{CH}\c5_mc_terminal_wealth.png"); plt.close()

# ---- C6/C7/C8: metric vs Kelly fraction ------------------------------------
for fname, col, title, ylab, dec, kind in [
        ("c6_mc_cagr", "cagr_median", "Median 25-year CAGR", "CAGR", 1, "pct"),
        ("c6b_mc_cagr_p5", "cagr_p5", "5th-percentile 25-year CAGR (bad-luck case)",
         "CAGR", 1, "pct"),
        ("c7_mc_drawdown", "mdd_median", "Median maximum drawdown",
         "Max drawdown", 0, "pct"),
        ("c7b_mc_pdd50", "p_dd_50", "Probability of a >50% drawdown",
         "P(max DD <= -50%)", 0, "pct")]:
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.7), dpi=170, sharey=True)
    for ax, (key, lbl, _) in zip(axes, SER):
        for x in X_MC:
            s = main[(main.series == key) & (main.X == x) &
                     (main.regime == "full")].sort_values("frac")
            ax.plot(s["frac"], s[col], color=cmap[x], lw=2, marker="o", ms=6,
                    mec=PAPER, mew=1.5, label=f"X = {x}", zorder=3)
        ax.set_title(lbl, fontsize=11.5, color=INK, loc="left", pad=8)
        ax.set_xlabel("Multiple of full-sample Kelly")
        ax.set_xticks(FR)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v:g}x"))
        style_ax(ax)
        if kind == "pct":
            pct(ax, dec)
    axes[0].set_ylabel(ylab)
    axes[0].legend(frameon=False, fontsize=9, loc="best",
                   title="best days removed", title_fontsize=9)
    fig.suptitle(title + "  --  25-year block-bootstrap paths",
                 fontsize=13, color=INK, x=0.008, ha="left", y=0.985)
    plt.tight_layout(rect=(0, 0, 1, 0.93))
    plt.savefig(rf"{CH}\{fname}.png"); plt.close()

# ---- C8: risk/return trade-off ---------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.9), dpi=170)
for ax, (key, lbl, _) in zip(axes, SER):
    for x in X_MC:
        s = main[(main.series == key) & (main.X == x) &
                 (main.regime == "full")].sort_values("frac")
        ax.plot(s["mdd_median"], s["cagr_median"], color=cmap[x], lw=1.6,
                marker="o", ms=6, mec=PAPER, mew=1.4, label=f"X = {x}", zorder=3)
        for _, r in s.iterrows():
            if r["frac"] in (0.25, 1.0, 1.5):
                ax.annotate(f"{r['frac']:g}x", xy=(r["mdd_median"], r["cagr_median"]),
                            xytext=(5, 4), textcoords="offset points",
                            fontsize=8, color=INK500)
    ax.axhline(0, color=INK500, lw=0.8, ls=(0, (4, 3)))
    ax.set_title(lbl, fontsize=11.5, color=INK, loc="left", pad=8)
    ax.set_xlabel("Median maximum drawdown")
    style_ax(ax); pct(ax, 1)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v*100:.0f}%"))
axes[0].set_ylabel("Median 25-year CAGR")
axes[0].legend(frameon=False, fontsize=9, loc="lower right",
               title="best days removed", title_fontsize=9)
fig.suptitle("Risk / return trade-off along the Kelly ladder (0.25x -> 1.5x)",
             fontsize=13.5, color=INK, x=0.008, ha="left", y=0.985)
plt.tight_layout(rect=(0, 0, 1, 0.93))
plt.savefig(rf"{CH}\c8_mc_risk_return.png"); plt.close()

# ---- C9: optimal leverage vs X, four definitions ---------------------------
opt_path = rf"{OUTDIR}\phase13_optimal_leverage.csv"
if os.path.exists(opt_path):
    optd = pd.read_csv(opt_path)
    XO = sorted(optd.X.unique())
    PO = np.arange(len(XO))
    defs = [("f_kelly", "Kelly (daily distribution)", SC4["worst"], "-"),
            ("f_growth", "Max median 25y CAGR (MC)", SC4["both"], "-"),
            ("f_p5", "Max 5th-percentile CAGR (MC)", SC4["random"], "-"),
            ("f_budget", "Risk budget: P(DD<-50%) <= 25%", SC4["best"], "-")]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.9), dpi=170, sharey=True)
    for ax, (key, lbl, _) in zip(axes, SER):
        s = optd[optd.series == key].set_index("X").loc[XO]
        for col, name, c, ls in defs:
            ax.plot(PO, s[col], color=c, lw=2, ls=ls, marker="o", ms=6,
                    mec=PAPER, mew=1.5, label=name, zorder=3)
        ax.axhline(1.0, color=INK500, lw=0.9, ls=(0, (4, 3)))
        ax.annotate("unlevered", xy=(PO[-1], 1.0), xytext=(-2, 6),
                    textcoords="offset points", color=INK500, fontsize=8.5, ha="right")
        ax.set_title(lbl, fontsize=11.5, color=INK, loc="left", pad=8)
        ax.set_xticks(PO); ax.set_xticklabels([str(x) for x in XO])
        ax.set_xlabel("Best trading days removed")
        style_ax(ax)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v:g}x"))
    axes[0].set_ylabel("Optimal leverage f")
    axes[0].legend(frameon=False, fontsize=8.5, loc="lower left")
    fig.suptitle("Growth-optimal leverage collapses with X; risk-adjusted leverage barely moves",
                 fontsize=13, color=INK, x=0.008, ha="left", y=0.985)
    plt.tight_layout(rect=(0, 0, 1, 0.93))
    plt.savefig(rf"{CH}\c9_optimal_leverage.png"); plt.close()
    print("  + c9_optimal_leverage.png")

print(f"All charts written to {CH}")
