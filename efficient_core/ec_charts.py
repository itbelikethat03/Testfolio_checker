"""
ec_charts.py -- the nine charts the brief asks for.

PALETTE.  Categorical hues are the dataviz reference palette, used verbatim in
its documented fixed order (blue, orange, aqua, yellow, magenta, violet), which
is the configuration validated for the adjacent pairlist that line and bar
charts use.  Colour is assigned to an ENTITY once and never re-cycled: the
reconstructed 90/60 is blue in every chart it appears in, developed equities
orange, and so on.  Positive/negative differences use the diverging blue<->red
pair with a neutral gap, never a rainbow.  Every chart has a CSV table view in
output/, which is also the relief for the two light-mode slots that sit below
3:1 contrast on this surface.

Charts
  c1  cumulative wealth
  c2  rolling 3-year CAGR
  c3  rolling 5-year CAGR
  c4  rolling 10-year CAGR
  c5  drawdown
  c6  Monte Carlo terminal wealth distribution
  c7  probability of 90/60 beating All World, by horizon
  c8  financing-cost sensitivity
  c9  actual WisdomTree ETFs vs the reconstructed model
"""
from __future__ import annotations

import os
import warnings

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

import ec_bonds as B
import ec_data as D
from common import metrics as M
import ec_portfolios as P

OUT = D.OUT
CH = rf"{OUT}\charts"
os.makedirs(CH, exist_ok=True)

# --- reference palette, light mode -----------------------------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

C = {
    "p9060": "#2a78d6",     # slot 1  blue
    "equity": "#eb6834",    # slot 2  orange
    "lev15": "#1baf7a",     # slot 3  aqua
    "scv": "#eda100",       # slot 4  yellow
    "acwi": "#e87ba4",      # slot 5  magenta
    "ntsg": "#4a3aa7",      # slot 6  violet
}
POS, NEG = "#2a78d6", "#e34948"          # diverging pair
NEUTRAL = "#f0efec"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "legend.frameon": False,
    "axes.titlesize": 11.5, "axes.titleweight": "bold",
    "figure.dpi": 110,
})


def style(ax, grid="y"):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def pct(ax, dec=0, axis="y"):
    f = mticker.FuncFormatter(lambda v, p: f"{v * 100:.{dec}f}%")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(f)


def save(fig, name, note=None):
    if note:
        fig.text(0.008, 0.005, note, fontsize=7.6, color=MUTED, va="bottom")
    fig.savefig(rf"{CH}\{name}", bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote charts\\{name}")


SRC = ("Reconstruction from WisdomTree index rules + Ken French Developed, "
       "FRED, ECB, Bank of England and Japan MoF data.  "
       "Synthetic history -- not fund history.")


# ===========================================================================
def load_panel():
    return pd.read_csv(rf"{OUT}\panel_global_daily.csv", index_col=0,
                       parse_dates=True)


# --- c1 --------------------------------------------------------------------
def c1_cumulative(g):
    """Two panels because the five series do not share a start date.  Splicing
    them onto one axis would make ACWI look like a catastrophe when it simply
    starts eighteen years later, so each panel rebases only series that share
    its window."""
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 5.8),
                             gridspec_kw={"width_ratios": [1.55, 1],
                                          "wspace": 0.17})
    long_set = [("p9060", "Reconstructed 90/60", g["rec9060"]),
                ("equity", "Developed equities 100%", g["equity_dm"]),
                ("lev15", "Developed equities 1.5x", g["lev15"]),
                ("scv", "Developed small-cap value", g["scv_dm"])]
    ax = axes[0]
    for key, lbl, s in long_set:
        n = M.nav(s.dropna())
        ax.plot(n.index, n.values, color=C[key],
                lw=2.0 if key == "p9060" else 1.2,
                label=f"{lbl}  ({M.cagr(s.dropna()) * 100:.2f}%/yr)")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v:,.0f}x"))
    ax.set_yticks([1, 2, 5, 10, 20, 40])
    ax.minorticks_off()
    style(ax)
    ax.set_title("1990-2026, common start (log scale)")
    ax.set_ylabel("multiple of starting capital")
    ax.legend(loc="upper left", fontsize=9)

    ax = axes[1]
    sub = g.loc["2008-03-31":]
    for key, lbl, col in [("p9060", "Reconstructed 90/60", "rec9060"),
                          ("equity", "Developed equities 100%", "equity_dm"),
                          ("lev15", "Developed equities 1.5x", "lev15"),
                          ("scv", "Developed small-cap value", "scv_dm"),
                          ("acwi", "All World (ACWI)", "acwi")]:
        s = sub[col].dropna()
        n = M.nav(s)
        ax.plot(n.index, n.values, color=C[key],
                lw=2.0 if key == "p9060" else 1.2,
                label=f"{lbl}  ({M.cagr(s) * 100:.2f}%/yr)")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v:,.0f}x"))
    ax.set_yticks([1, 2, 3, 5, 8])
    ax.minorticks_off()
    ax.xaxis.set_major_locator(matplotlib.dates.YearLocator(4))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
    style(ax)
    ax.set_title("2008-2026, all five comparable (log scale)")
    ax.legend(loc="upper left", fontsize=8.6)
    fig.suptitle("Growth of 1 unit, total return", fontsize=12.5,
                 fontweight="bold", y=1.0)
    save(fig, "c1_cumulative_wealth.png", SRC)


# --- c2/c3/c4 --------------------------------------------------------------
def rolling_chart(g, years, name):
    a = M.rolling_cagr(g["rec9060"], years)
    b = M.rolling_cagr(g["equity_dm"], years)
    idx = a.index.intersection(b.index)
    a, b = a.reindex(idx), b.reindex(idx)
    d = a - b

    fig, axes = plt.subplots(2, 1, figsize=(11, 6.6), sharex=True,
                             gridspec_kw={"height_ratios": [2, 1.15],
                                          "hspace": 0.18})
    ax = axes[0]
    ax.plot(a.index, a.values, color=C["p9060"], lw=1.5,
            label="Reconstructed 90/60")
    ax.plot(b.index, b.values, color=C["equity"], lw=1.5,
            label="Developed equities 100%")
    ax.axhline(0, color=AXIS, lw=0.9)
    pct(ax)
    style(ax)
    ax.set_title(f"Rolling {years}-year annualised return")
    ax.legend(loc="upper right", fontsize=9.5)

    ax = axes[1]
    ax.fill_between(d.index, 0, d.values, where=(d.values >= 0),
                    color=POS, alpha=0.75, lw=0, interpolate=True)
    ax.fill_between(d.index, 0, d.values, where=(d.values < 0),
                    color=NEG, alpha=0.75, lw=0, interpolate=True)
    ax.axhline(0, color=INK2, lw=1.0)
    pct(ax, 1)
    style(ax)
    win = float((d > 0).mean())
    ax.set_title(f"90/60 minus equities   "
                 f"(90/60 ahead in {win * 100:.0f}% of windows, "
                 f"median {d.median() * 100:+.2f}pp)", fontsize=10.5)
    ax.set_ylabel("pp per year", fontsize=9)
    save(fig, name, SRC + "  Dates mark the END of each window.")


# --- c5 --------------------------------------------------------------------
def c5_drawdown(g):
    fig, ax = plt.subplots(figsize=(11, 5.6))
    for key, lbl, s in [("equity", "Developed equities 100%", g["equity_dm"]),
                        ("lev15", "Developed equities 1.5x", g["lev15"]),
                        ("p9060", "Reconstructed 90/60", g["rec9060"])]:
        dd = M.drawdown(s.dropna())
        ax.plot(dd.index, dd.values, color=C[key], lw=1.3,
                label=f"{lbl}  (worst {dd.min() * 100:.1f}%)")
    ax.axhline(0, color=AXIS, lw=0.9)
    pct(ax)
    style(ax)
    ax.set_title("Drawdown from previous peak")
    ax.set_ylim(-0.80, 0.10)
    ax.legend(loc="lower left", fontsize=9.5)
    for when, txt, yy, ha in [("2002-10-09", "dot-com", 0.085, "center"),
                              ("2009-03-09", "GFC", 0.085, "center"),
                              ("2020-03-23", "COVID", 0.085, "right"),
                              ("2022-10-14", "2022 stocks + bonds",
                               0.035, "left")]:
        t = pd.Timestamp(when)
        ax.axvline(t, color=AXIS, lw=0.8, ls=":", zorder=0)
        ax.annotate(txt, xy=(t, yy), fontsize=8.4, color=INK2, ha=ha,
                    va="top")
    save(fig, "c5_drawdown.png", SRC)


# --- c6 --------------------------------------------------------------------
def c6_mc_terminal():
    z = np.load(rf"{OUT}\montecarlo_paths.npz")
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.2))
    panels = [("A_global_monthly", "Sample A: global 1990-2026\n"
                                   "(bond bull-market era)"),
              ("B_us_annual", "Sample B: US 1928-2025\n"
                              "(includes stagflation)")]
    for ax, (tag, title) in zip(axes, panels):
        t9, te = z[f"{tag}_30_t9"], z[f"{tag}_30_te"]
        bins = np.logspace(np.log10(max(min(t9.min(), te.min()), 0.2)),
                           np.log10(max(t9.max(), te.max())), 70)
        ax.hist(te, bins=bins, histtype="step", lw=1.6, color=C["equity"],
                label=f"Equities  (median {np.median(te):.1f}x)")
        ax.hist(t9, bins=bins, histtype="step", lw=1.6, color=C["p9060"],
                label=f"90/60  (median {np.median(t9):.1f}x)")
        ax.axvline(np.median(te), color=C["equity"], lw=1.0, ls=":")
        ax.axvline(np.median(t9), color=C["p9060"], lw=1.0, ls=":")
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(
            lambda v, p: f"{v:,.0f}x" if v >= 1 else f"{v:.1f}x"))
        style(ax, grid=None)
        ax.set_title(title, fontsize=10.5)
        ax.set_xlabel("terminal wealth after 30 years, log scale")
        ax.set_ylabel("paths")
        ax.legend(loc="upper left", fontsize=9)
    fig.suptitle("Monte Carlo terminal wealth, 30-year horizon, "
                 "20,000 paired block-bootstrap paths",
                 fontsize=12, fontweight="bold", y=1.02)
    save(fig, "c6_mc_terminal_wealth.png",
         "Paired draws: both strategies see the same resampled history.")


# --- c7 --------------------------------------------------------------------
def c7_mc_probability():
    a = pd.read_csv(rf"{OUT}\montecarlo_A_global_monthly.csv")
    b = pd.read_csv(rf"{OUT}\montecarlo_B_us_annual.csv")
    s = pd.read_csv(rf"{OUT}\montecarlo_sensitivity.csv")

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.2))
    ax = axes[0]
    ax.plot(a["horizon"], a["p_outperform"], color=C["p9060"], lw=2,
            marker="o", ms=8, label="Sample A: global 1990-2026")
    ax.plot(b["horizon"], b["p_outperform"], color=C["equity"], lw=2,
            marker="s", ms=8, label="Sample B: US 1928-2025")
    for df, col in [(a, C["p9060"]), (b, C["equity"])]:
        for _, r in df.iterrows():
            ax.annotate(f"{r['p_outperform'] * 100:.0f}%",
                        (r["horizon"], r["p_outperform"]), textcoords="offset points",
                        xytext=(0, 11), ha="center", fontsize=9, color=col)
    ax.axhline(0.5, color=INK2, lw=1.0, ls="--")
    ax.text(10.4, 0.455, "coin flip", ha="left", fontsize=8.6, color=INK2)
    ax.set_ylim(0.15, 1.0)
    pct(ax)
    style(ax)
    ax.set_xticks([10, 20, 30, 40])
    ax.set_xlabel("investment horizon (years)")
    ax.set_title("P(90/60 beats 100% All World)")
    ax.legend(loc="lower left", fontsize=9)

    ax = axes[1]
    ramp = ["#86b6ef", "#3987e5", "#256abf", "#0d366b"]
    for col, h in zip(ramp, [10, 20, 30, 40]):
        ax.plot(s["term_premium"], s[f"p_win_{h}y"], color=col, lw=1.8,
                marker="o", ms=5, label=f"{h}-year horizon")
    ax.axhline(0.5, color=INK2, lw=1.0, ls="--")
    ax.axvline(0.0128, color=NEG, lw=1.2, ls=":")
    ax.annotate("analytic break-even\n1.28%/yr", xy=(0.0128, 0.22),
                xytext=(0.019, 0.20), fontsize=8.6, color=NEG,
                arrowprops=dict(arrowstyle="->", color=NEG, lw=0.9))
    pct(ax)
    pct(ax, 1, axis="x")
    style(ax)
    ax.set_xlabel("assumed bond term premium (bond return minus financing cost)")
    ax.set_title("The whole answer turns on the bond term premium")
    ax.legend(loc="lower right", fontsize=9)
    save(fig, "c7_prob_outperform.png",
         "Right panel: sample A resampled with the bond leg shifted up/down.")


# --- c8 --------------------------------------------------------------------
def c8_financing():
    h = pd.read_csv(rf"{OUT}\financing_sensitivity_historical.csv")
    f = pd.read_csv(rf"{OUT}\financing_sensitivity_forward.csv")
    import json
    with open(rf"{OUT}\headline_stats.json") as fh:
        js = json.load(fh)

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 5.2),
                             gridspec_kw={"wspace": 0.26})
    ax = axes[0]
    x = h["spread_over_short_rate"] * 100
    ax.plot(x, h["cagr_9060"], color=C["p9060"], lw=2, marker="o", ms=8,
            label="Reconstructed 90/60")
    ax.axhline(js["equity_cagr"], color=C["equity"], lw=1.8, ls="--",
               label="Developed equities 100%")
    # exact crossover, interpolated rather than snapped to a sampled point
    d = h["vs_equities_pp"].values
    cross = None
    for i in range(len(d) - 1):
        if d[i] >= 0 > d[i + 1]:
            t = d[i] / (d[i] - d[i + 1])
            cross = float(x.iloc[i] + t * (x.iloc[i + 1] - x.iloc[i]))
            break
    if cross is not None:
        ax.axvspan(cross, float(x.max()), color=NEG, alpha=0.09, lw=0)
        ax.axvline(cross, color=NEG, lw=1.0, ls=":")
        ax.annotate(f"break-even spread {cross:.2f}%/yr\n"
                    f"-- beyond this the 90/60\nstructure adds nothing",
                    xy=(cross, js["equity_cagr"]),
                    xytext=(cross - 0.9, h["cagr_9060"].min() + 0.0012),
                    fontsize=8.6, color=NEG,
                    arrowprops=dict(arrowstyle="->", color=NEG, lw=0.9))
    pct(ax, 1)
    ax.set_xticks([0, 0.5, 1.0, 1.5, 2.0])
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v:.1f}%"))
    style(ax)
    ax.set_xlabel("extra financing spread on the 0.60 notional (%/yr)")
    ax.set_ylabel("realised CAGR, 1990-2026")
    ax.set_title("Historical path, extra financing spread", fontsize=10.5)
    ax.legend(loc="upper right", fontsize=9)

    ax = axes[1]
    colors = [POS if v > 0 else NEG for v in f["vs_equity_pp"]]
    ax.bar(f["financing"] * 100, f["vs_equity_pp"], width=0.55, color=colors,
           edgecolor=SURFACE, linewidth=2)
    for _, r in f.iterrows():
        off = 4 if r["vs_equity_pp"] >= 0 else -13
        ax.annotate(f"{r['vs_equity_pp']:+.2f}pp",
                    (r["financing"] * 100, r["vs_equity_pp"]),
                    textcoords="offset points", xytext=(0, off), ha="center",
                    fontsize=9, color=INK2)
    ax.axhline(0, color=INK2, lw=1.1)
    style(ax)
    ax.set_xlabel("absolute financing cost (%/yr)")
    ax.set_ylabel("90/60 minus All World (pp/yr)")
    ax.set_title(f"Forward-looking, bond return fixed at today's "
                 f"{js['fwd_ladder_yield'] * 100:.2f}% ladder yield",
                 fontsize=10.5)
    fig.suptitle("Financing-cost sensitivity", fontsize=12.5,
                 fontweight="bold", y=1.02)
    save(fig, "c8_financing_sensitivity.png",
         "Right panel holds the bond return fixed, so rising financing cost "
         "means a shrinking term premium.  A parallel rise in both is neutral.")


# --- c9 --------------------------------------------------------------------
def c9_actual_vs_model():
    px = D.load_prices(["NTSG.L", "URTH", "NTSX", "SPY"])
    curves = B.build_curves()
    ff = D.load_ff_us_daily()

    ntsg = px["NTSG.L"].dropna().pct_change().dropna()
    urth = px["URTH"].dropna().pct_change().dropna()
    cal = ntsg.index.intersection(urth.index)
    fut = B.futures_sleeve(curves, cal)
    cash = P.cash_blend(curves, cal)
    m_ntsg = P.simulate_efficient_core(urth.reindex(cal), cash.reindex(cal),
                                       fut["sleeve"].reindex(cal),
                                       costs=P.TOTAL_COSTS)["ret"]

    ntsx = px["NTSX"].dropna().pct_change().dropna()
    spy = px["SPY"].dropna().pct_change().dropna()
    cal2 = ntsx.index.intersection(spy.index)
    fut2 = B.us_only_sleeve(curves, cal2, (2, 4.5, 7, 18))
    m_ntsx = P.simulate_efficient_core(spy.reindex(cal2),
                                       ff["rf"].reindex(cal2).ffill(),
                                       fut2["sleeve"].reindex(cal2),
                                       costs=0.0020)["ret"]

    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.6),
                             gridspec_kw={"height_ratios": [2, 1],
                                          "hspace": 0.32, "wspace": 0.22})
    panels = [
        (axes[0, 0], axes[1, 0], ntsx.reindex(cal2), m_ntsx,
         "NTSX -- U.S. Efficient Core, live since Aug 2018",
         "8.1 years, includes 2022"),
        (axes[0, 1], axes[1, 1], ntsg.reindex(cal), m_ntsg,
         "NTSG -- Global Efficient Core, live since Nov 2024",
         "1.8 years"),
    ]
    for ax, axd, act, mod, title, sub in panels:
        na, nm = M.nav(act), M.nav(mod)
        ax.plot(na.index, na.values, color=C["ntsg"], lw=1.8,
                label=f"Actual fund  ({M.cagr(act) * 100:.2f}%/yr)")
        ax.plot(nm.index, nm.values, color=C["p9060"], lw=1.5, ls="--",
                label=f"Reconstruction  ({M.cagr(mod) * 100:.2f}%/yr)")
        style(ax)
        ax.set_title(f"{title}\n{sub}", fontsize=10.5)
        ax.set_ylabel("growth of 1")
        ax.legend(loc="upper left", fontsize=9)

        gap = (nm / na - 1)
        axd.fill_between(gap.index, 0, gap.values,
                         where=(gap.values >= 0), color=POS, alpha=0.7, lw=0)
        axd.fill_between(gap.index, 0, gap.values,
                         where=(gap.values < 0), color=NEG, alpha=0.7, lw=0)
        axd.axhline(0, color=INK2, lw=1.0)
        pct(axd, 1)
        style(axd)
        axd.set_title(f"cumulative gap, model minus actual "
                      f"(ends {gap.iloc[-1] * 100:+.2f}%)", fontsize=9.5)
        for a in (ax, axd):
            a.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %Y"))
            a.xaxis.set_major_locator(matplotlib.dates.AutoDateLocator(
                minticks=3, maxticks=6))
            for lab in a.get_xticklabels():
                lab.set_fontsize(8.6)
    fig.suptitle("Can public data reproduce the real funds?",
                 fontsize=12.5, fontweight="bold", y=0.99)
    save(fig, "c9_actual_vs_model.png",
         "NTSX is the real test: same construction, 8 years, unambiguous inputs. "
         "NTSG's 1.8 years cannot separate model error from noise.")


# ===========================================================================
if __name__ == "__main__":
    g = load_panel()
    print("Rendering charts ...")
    c1_cumulative(g)
    rolling_chart(g, 3, "c2_rolling_3y.png")
    rolling_chart(g, 5, "c3_rolling_5y.png")
    rolling_chart(g, 10, "c4_rolling_10y.png")
    c5_drawdown(g)
    c6_mc_terminal()
    c7_mc_probability()
    c8_financing()
    c9_actual_vs_model()
    print(f"\nAll charts in {CH}")
