"""
ec_analysis.py -- the empirical core of the study.

Sections, matching the brief:
  1  windows and panels (what is measured over what period, stated up front)
  2  Table 1: return and risk for every strategy
  3  annualised return comparison across explicitly labelled windows
  4  why leveraged bonds can work at all -- the algebra, then the measurement
  5  Table 3: financing-cost sensitivity, both historical and forward-looking
  6  sensitivity to bond returns, equity returns, correlation and volatility
  7  rolling analysis
  8  drawdown analysis, including the named crises
  9  market-regime analysis
 10  robustness of the modelling choices

Everything is written to output/ as CSV/JSON for the charts and the report.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

import ec_bonds as B
import ec_data as D
from common import leverage as LV
from common import metrics as M
import ec_portfolios as P

OUT = D.OUT
pd.set_option("display.width", 250)

RULE = "=" * 92


def head(n, title):
    print(f"\n{RULE}\n{n}. {title}\n{RULE}")


# ===========================================================================
# 1. panels
# ===========================================================================
def build_panels():
    g = P.global_panel()
    px = D.load_prices(["NTSG.L", "ACWI", "VT", "URTH", "NTSX", "SPY"])

    g["acwi"] = px["ACWI"].reindex(g.index).ffill().pct_change()
    g["ntsg"] = px["NTSG.L"].reindex(g.index).ffill().pct_change()
    g["equity_dm_exc"] = g["equity_dm"] - g["rf"]
    return g, px


# ===========================================================================
# 4. the algebra of the 90/60 trade
# ===========================================================================
def leverage_algebra(g: pd.DataFrame):
    head(4, "WHY LEVERAGED BONDS CAN WORK AT ALL -- the identity, then the data")

    print("""
The fund holds, per 1.00 of NAV:  0.90 equity + 0.10 cash + 0.60 bond futures.
A futures position needs no funded capital and returns the bond's return minus
the local short rate, so:

    r(90/60) = 0.90*E + 0.10*C + 0.60*(Bd - C) - costs

Subtracting a 100% equity portfolio, r = E:

    r(90/60) - E = 0.60*(Bd - C) - 0.10*(E - C) - costs
                 = 0.60 * BOND TERM PREMIUM - 0.10 * EQUITY RISK PREMIUM - costs

That is the whole trade.  The 90/60 structure does NOT bet that bonds beat
equities.  It gives up one tenth of the equity risk premium to buy six tenths
of the bond term premium.  It wins on expected return whenever

    bond term premium  >  (1/6) * equity risk premium  +  (costs / 0.6)

Because the multiplier is 6:1, a bond term premium that looks trivially small
still clears the bar.  With a 5% equity risk premium and 0.27% of costs, the
break-even term premium is only 0.83% + 0.45% = 1.28% a year.
""")

    # geometric premia over the sample
    yrs = M.years_of(g.index)
    eq_c = M.cagr(g["equity_dm"])
    cash_c = M.cagr(g["cash"])
    btp_c = M.cagr(g["futures"])           # already an excess return
    print(f"Measured over the reconstruction window "
          f"{g.index[0].date()}..{g.index[-1].date()} ({yrs:.1f} years):")
    print(f"    developed equity total return          {eq_c * 100:6.2f}% p.a.")
    print(f"    four-currency cash (the funding rate)  {cash_c * 100:6.2f}% p.a.")
    print(f"    equity risk premium  E - C             {(eq_c - cash_c) * 100:6.2f}% p.a.")
    print(f"    bond term premium    Bd - C (measured) {btp_c * 100:6.2f}% p.a.")
    print(f"    break-even term premium needed         "
          f"{((eq_c - cash_c) / 6 + P.TOTAL_COSTS / 0.6) * 100:6.2f}% p.a.")
    contrib_b = 0.60 * btp_c
    contrib_e = 0.10 * (eq_c - cash_c)
    print(f"\n    +0.60 x bond term premium              {contrib_b * 100:+6.2f} pp")
    print(f"    -0.10 x equity risk premium            {-contrib_e * 100:+6.2f} pp")
    print(f"    -costs                                 {-P.TOTAL_COSTS * 100:+6.2f} pp")
    print(f"    {'-' * 38} {'-' * 6}")
    print(f"    predicted edge over 100% equities      "
          f"{(contrib_b - contrib_e - P.TOTAL_COSTS) * 100:+6.2f} pp")
    print(f"    actually realised (CAGR difference)    "
          f"{(M.cagr(g['rec9060']) - eq_c) * 100:+6.2f} pp")
    print("    (the two differ only by rebalancing and compounding effects)")

    # break-even grid
    head("4b", "BREAK-EVEN: at what term premium does the bond leg stop paying?")
    erps = [0.02, 0.03, 0.04, 0.05, 0.06, 0.07]
    print("\n  Break-even bond term premium (bond return minus financing cost)")
    print("  needed for 90/60 to match 100% equities, per equity risk premium:\n")
    print("     equity risk premium :  " + "  ".join(f"{e * 100:5.1f}%" for e in erps))
    for c in [0.0, 0.0027, 0.0050]:
        be = [(e / 6 + c / 0.6) for e in erps]
        print(f"     costs {c * 100:4.2f}%/yr      :  "
              + "  ".join(f"{b * 100:5.2f}%" for b in be))
    print("\n  Contribution of the bond leg at various term premia (0.60x):")
    for tp in [-0.01, -0.005, 0.0, 0.005, 0.01, 0.015, 0.02, 0.025, 0.03]:
        net = 0.60 * tp - 0.10 * 0.05 - P.TOTAL_COSTS
        verdict = ("NEGATIVE" if net < -0.002 else
                   "roughly neutral" if net < 0.002 else "POSITIVE")
        print(f"     term premium {tp * 100:+5.2f}%  ->  0.60x = "
              f"{0.60 * tp * 100:+5.2f} pp,  net vs equities "
              f"{net * 100:+5.2f} pp  {verdict}")
    print("  (net column assumes a 5% equity risk premium and 0.27%/yr of costs)")

    return {"equity_cagr": eq_c, "cash_cagr": cash_c,
            "erp": eq_c - cash_c, "btp": btp_c}


# ===========================================================================
# 5. financing sensitivity
# ===========================================================================
def financing_sensitivity(g: pd.DataFrame, stats: dict):
    head(5, "TABLE 3 -- FINANCING-COST SENSITIVITY")

    print("""
A word on what "financing cost" means here.  The 90/60 fund does not borrow at
a quoted rate; it holds futures, whose price already embeds the local money
market rate.  So the financing cost is not a free parameter -- it is whatever
short rates are.  What IS a free parameter is the SPREAD the fund pays over
that rate through the futures basis and the roll.  Both are shown.
""")

    print("5a. HISTORICAL -- an extra financing spread on the 0.60 notional,")
    print("    applied to the actual 1990-2026 path.\n")
    base_cagr = M.cagr(g["rec9060"])
    eq_cagr = M.cagr(g["equity_dm"])
    rows = []
    for spread in [0.0, 0.0025, 0.005, 0.01, 0.02]:
        fut = g["futures"] - spread * (
            pd.Series(g.index, index=g.index).diff().dt.days.fillna(1) / 365.0)
        r = P.simulate_efficient_core(g["equity_dm"], g["cash"], fut,
                                      costs=P.TOTAL_COSTS)["ret"]
        rows.append({"spread_over_short_rate": spread, "cagr_9060": M.cagr(r),
                     "vol": M.vol(r), "sharpe": M.sharpe(r, g["rf"]),
                     "vs_equities_pp": (M.cagr(r) - eq_cagr) * 100})
    hist = pd.DataFrame(rows)
    print(f"    {'spread':>8s} {'90/60 CAGR':>11s} {'vol':>7s} {'Sharpe':>7s} "
          f"{'vs 100% equities':>18s}")
    for _, r in hist.iterrows():
        print(f"    {r['spread_over_short_rate'] * 100:7.2f}% "
              f"{r['cagr_9060'] * 100:10.2f}% {r['vol'] * 100:6.2f}% "
              f"{r['sharpe']:7.2f} {r['vs_equities_pp']:+17.2f} pp")
    print(f"\n    100% developed equities over the same window: "
          f"{eq_cagr * 100:.2f}% CAGR, {M.vol(g['equity_dm']) * 100:.2f}% vol, "
          f"Sharpe {M.sharpe(g['equity_dm'], g['rf']):.2f}")
    print("    A 1pp financing spread costs 0.60pp of return -- it is levied on")
    print("    the full 0.60 notional, not on the 0.50 of net leverage.")

    # ---- forward-looking version, the one the brief asks for ----
    print("\n5b. FORWARD-LOOKING -- absolute financing cost 2% to 6%.\n")
    cur = B.build_curves().ffill().iloc[-1]
    ladder_y, ladder_w = [], []
    for ccy, tenors in B.LADDER.items():
        w = B.CCY_WEIGHTS[ccy]
        pts = B.CURVE_POINTS[ccy]
        mats = np.array(sorted(pts))
        vals = np.array([cur[pts[m]] for m in sorted(pts)])
        for t in tenors:
            ladder_y.append(float(np.interp(t, mats, vals)))
            ladder_w.append(w / len(tenors))
    ladder_w = np.array(ladder_w) / np.sum(ladder_w)
    fwd_bond_yield = float(np.dot(ladder_y, ladder_w))
    short = float(np.dot([cur[B.FINANCING_COL[c]] for c in B.LADDER],
                         [B.CCY_WEIGHTS[c] for c in B.LADDER])
                  / sum(B.CCY_WEIGHTS[c] for c in B.LADDER))
    print(f"    Anchor from today's curves ({cur.name.date()}):")
    print(f"      weighted ladder yield          {fwd_bond_yield * 100:5.2f}%"
          f"   <- the forward bond return estimate")
    print(f"      weighted short rate            {short * 100:5.2f}%"
          f"   <- today's actual financing cost")
    print(f"      implied term premium           "
          f"{(fwd_bond_yield - short) * 100:5.2f}%\n")

    E_ASSUMED = 0.075
    print(f"    Assumptions: equity total return {E_ASSUMED * 100:.1f}%/yr "
          f"(ESTIMATE), bond return = ladder yield {fwd_bond_yield * 100:.2f}% "
          f"(held fixed),\n    costs {P.TOTAL_COSTS * 100:.2f}%/yr (documented).")
    print(f"\n    {'financing cost':>15s} {'90/60 CAGR':>11s} "
          f"{'vs All World':>13s}")
    fwd = []
    for f in [0.02, 0.03, 0.04, 0.05, 0.06]:
        r = (P.W_EQUITY * E_ASSUMED + P.W_CASH * f
             + P.W_BOND * (fwd_bond_yield - f) - P.TOTAL_COSTS)
        fwd.append({"financing": f, "cagr_9060": r,
                    "vs_equity_pp": (r - E_ASSUMED) * 100})
        print(f"    {f * 100:14.1f}% {r * 100:10.2f}% "
              f"{(r - E_ASSUMED) * 100:+12.2f} pp")
    print("\n    d(return)/d(financing) = 0.10 - 0.60 = -0.50: every extra 1pp of")
    print("    financing cost costs 0.50pp, because the fund is 50% net levered.")
    print("    The level of rates only matters through the SPREAD between the")
    print("    ladder yield and the short rate; a parallel rise in both is neutral.")

    hist.to_csv(rf"{OUT}\financing_sensitivity_historical.csv", index=False)
    pd.DataFrame(fwd).to_csv(rf"{OUT}\financing_sensitivity_forward.csv",
                             index=False)
    return hist, pd.DataFrame(fwd), fwd_bond_yield, short


# ===========================================================================
# 6. bond / equity / correlation / vol sensitivity
# ===========================================================================
def parameter_sensitivity(g: pd.DataFrame, fwd_bond_yield: float, short: float):
    head(6, "SENSITIVITY TO BOND RETURNS, EQUITY RETURNS, CORRELATION, VOL")

    print("\n6a. Expected-return grid: 90/60 minus 100% equities, in pp per year.")
    print("    rows = bond total return, cols = equity total return, "
          f"financing fixed at {short * 100:.2f}%, costs {P.TOTAL_COSTS * 100:.2f}%\n")
    eqs = [0.04, 0.055, 0.07, 0.085, 0.10]
    bds = [0.00, 0.015, 0.03, 0.045, 0.06]
    print("            " + "".join(f"E={e * 100:5.1f}% " for e in eqs))
    grid = []
    for b in bds:
        row = []
        for e in eqs:
            d = (P.W_BOND * (b - short) - (1 - P.W_EQUITY) * (e - short)
                 - P.TOTAL_COSTS)
            row.append(d * 100)
        grid.append(row)
        print(f"    B={b * 100:4.1f}%  " + "".join(f"{v:+7.2f} " for v in row))
    pd.DataFrame(grid, index=[f"bond_{b}" for b in bds],
                 columns=[f"eq_{e}" for e in eqs]).to_csv(
        rf"{OUT}\sensitivity_return_grid.csv")
    print("\n    Read it as: the 90/60 edge is almost entirely a function of the")
    print("    BOND row.  Moving equities from 4% to 10% changes the edge by only")
    print(f"    {(0.10 - 0.04) * 0.10 * 100:.1f}pp, because only 0.10 of equity "
          f"exposure was given up.")

    print("\n6b. Correlation: what it does and does not change.\n")
    se = M.vol(g["equity_dm"])
    sb = M.vol(g["futures"])
    rho_actual = float(g["equity_dm"].corr(g["futures"]))
    print(f"    measured: equity vol {se * 100:.2f}%, bond-futures vol "
          f"{sb * 100:.2f}%, correlation {rho_actual:+.3f}")
    print(f"\n    {'correlation':>12s} {'90/60 vol':>10s} {'vs equity vol':>14s} "
          f"{'Sharpe ratio 90/60':>19s}")
    edge = 0.60 * M.cagr(g["futures"]) - 0.10 * (M.cagr(g["equity_dm"])
                                                 - M.cagr(g["cash"]))
    sharpe_eq = M.sharpe(g["equity_dm"], g["rf"])
    exc_9060 = M.cagr(g["equity_dm"]) - M.cagr(g["cash"]) + edge
    rows = []
    for rho in [-0.6, -0.3, 0.0, 0.3, 0.6, 0.9]:
        v = np.sqrt((0.9 * se) ** 2 + (0.6 * sb) ** 2
                    + 2 * 0.9 * 0.6 * rho * se * sb)
        rows.append({"rho": rho, "vol_9060": v, "sharpe_9060": exc_9060 / v})
        print(f"    {rho:+11.2f} {v * 100:9.2f}% {(v - se) * 100:+13.2f} pp "
              f"{exc_9060 / v:18.2f}")
    print(f"    (100% equities: vol {se * 100:.2f}%, Sharpe {sharpe_eq:.2f})")
    print("\n    Correlation does NOT enter the expected-return identity at all.")
    print("    It decides only whether the extra 0.60 of bond exposure is bought")
    print("    cheaply in risk terms.  At rho = +0.9 the 90/60 portfolio is")
    print("    riskier than 100% equities and the structure loses its point;")
    print("    at rho <= 0 it is less risky AND higher returning.")
    pd.DataFrame(rows).to_csv(rf"{OUT}\sensitivity_correlation.csv", index=False)

    print("\n6c. Rolling 3-year stock/bond correlation -- is the diversification")
    print("    benefit stable?\n")
    roll = g["equity_dm"].rolling(756).corr(g["futures"]).dropna()
    yr = roll.groupby(roll.index.year).mean()
    line = "    "
    for y, v in yr.items():
        line += f"{y}:{v:+.2f}  "
        if len(line) > 96:
            print(line)
            line = "    "
    print(line)
    roll.to_frame("corr_3y").to_csv(rf"{OUT}\rolling_correlation.csv")

    print("\n6d. Volatility drag.  Arithmetic mean return is not what compounds.\n")
    for lbl, s in [("100% equities", g["equity_dm"]),
                   ("1.5x equities", g["lev15"]),
                   ("90/60", g["rec9060"])]:
        ppy = M.periods_per_year(s.index)
        arith = s.mean() * ppy
        geo = M.cagr(s)
        print(f"    {lbl:16s} arithmetic {arith * 100:5.2f}%  "
              f"geometric {geo * 100:5.2f}%  drag {(arith - geo) * 100:5.2f} pp")
    print("\n    The 1.5x equity portfolio loses the most to drag: same premium,")
    print("    much more variance.  That is the case against levering equity, and")
    print("    the case for levering a low-volatility, low-correlation asset.")
    return rho_actual


# ===========================================================================
# 7. rolling analysis
# ===========================================================================
def rolling_analysis(g: pd.DataFrame):
    head(7, "ROLLING ANALYSIS -- is the edge persistent or concentrated?")
    out = {}
    print(f"\n    {'window':>8s} {'periods':>8s} {'90/60 wins':>11s} "
          f"{'median diff':>12s} {'5th pct':>9s} {'95th pct':>9s} "
          f"{'worst':>8s} {'best':>8s}")
    for yrs in [1, 3, 5, 10]:
        a = M.rolling_cagr(g["rec9060"], yrs)
        b = M.rolling_cagr(g["equity_dm"], yrs)
        idx = a.index.intersection(b.index)
        d = (a.reindex(idx) - b.reindex(idx)).dropna()
        if d.empty:
            continue
        out[yrs] = d
        print(f"    {yrs:6d}yr {len(d):8,d} {(d > 0).mean() * 100:10.1f}% "
              f"{d.median() * 100:+11.2f}pp {d.quantile(.05) * 100:+8.2f}pp "
              f"{d.quantile(.95) * 100:+8.2f}pp {d.min() * 100:+7.2f}pp "
              f"{d.max() * 100:+7.2f}pp")

    print("\n    Sustained spells (3 months or more of consecutive rolling")
    print("    windows) in which 90/60 UNDERPERFORMED over the trailing 5 years.")
    print("    The date is when the 5-year window ENDS.\n")
    d5 = out.get(5)
    if d5 is not None:
        under = d5 < 0
        runs, start = [], None
        for dt, u in under.items():
            if u and start is None:
                start = dt
            elif not u and start is not None:
                runs.append((start, dt))
                start = None
        if start is not None:
            runs.append((start, under.index[-1]))
        runs = [(s, e) for s, e in runs if (e - s).days >= 90]
        for s, e in runs:
            seg = d5.loc[s:e]
            print(f"      {s.date()} .. {e.date()}  "
                  f"({(e - s).days / 365.25:4.1f}y, worst {seg.min() * 100:+.2f}pp/yr)")
        if not runs:
            print("      none")
        frac = float(under.mean())
        print(f"\n      In total 90/60 trailed on {frac * 100:.1f}% of all 5-year")
        print(f"      windows, and those windows are heavily clustered rather")
        print(f"      than spread evenly -- note the 2021-2026 block, which is")
        print(f"      the 2022 bond crash working through the trailing window.")

    pd.DataFrame({f"diff_{k}y": v for k, v in out.items()}).to_csv(
        rf"{OUT}\rolling_differences.csv")
    return out


# ===========================================================================
# 8. drawdowns
# ===========================================================================
CRISES = [
    ("Dot-com bust", "2000-03-01", "2002-10-31"),
    ("Global Financial Crisis", "2007-10-01", "2009-03-31"),
    ("Euro crisis", "2011-05-01", "2011-10-31"),
    ("COVID crash", "2020-02-19", "2020-03-23"),
    ("2022 stocks-and-bonds selloff", "2022-01-01", "2022-10-31"),
    ("2025 tariff shock", "2025-02-19", "2025-04-30"),
]


def drawdown_analysis(g: pd.DataFrame):
    head(8, "DRAWDOWN ANALYSIS")

    names = {"100% developed equities": g["equity_dm"],
             "1.5x developed equities": g["lev15"],
             "Reconstructed 90/60": g["rec9060"],
             "Developed small-cap value": g["scv_dm"]}

    print(f"\n    {'episode':32s} {'window':24s} "
          + "".join(f"{k.split()[0][:9]:>10s}" for k in names))
    rows = []
    for label, a, b in CRISES:
        seg = {k: v.loc[a:b].dropna() for k, v in names.items()}
        if any(len(v) == 0 for v in seg.values()):
            continue
        vals = {k: float((1 + v).prod() - 1) for k, v in seg.items()}
        rows.append({"episode": label, "start": a, "end": b, **vals})
        print(f"    {label:32s} {a[:7]}..{b[:7]:12s} "
              + "".join(f"{vals[k] * 100:9.1f}%" for k in names))

    print(f"\n    {'full-sample max drawdown':32s} {'':24s}"
          + "".join(f"{M.max_drawdown(v) * 100:9.1f}%" for v in names.values()))
    pd.DataFrame(rows).to_csv(rf"{OUT}\crisis_returns.csv", index=False)

    print("\n    Deepest drawdown episodes, 100% equities vs 90/60:\n")
    for lbl in ["100% developed equities", "Reconstructed 90/60"]:
        ep = M.drawdown_episodes(names[lbl], threshold=-0.15).head(4)
        print(f"    {lbl}")
        for _, r in ep.iterrows():
            rec = ("still under water" if pd.isna(r["recovered"])
                   else f"{r['months_to_recover']:5.1f} months to recover")
            print(f"      {r['start'].date()} -> {r['trough'].date()} "
                  f"{r['depth'] * 100:7.2f}%   {rec}")
    return rows


# ===========================================================================
# 9. regimes
# ===========================================================================
def regime_analysis(g: pd.DataFrame):
    head(9, "MARKET REGIMES -- when does 90/60 beat 100% equities?")

    m = pd.DataFrame({
        "eq": (1 + g["equity_dm"]).resample("ME").prod() - 1,
        "p9060": (1 + g["rec9060"]).resample("ME").prod() - 1,
        "fut": (1 + g["futures"]).resample("ME").prod() - 1,
        "cash": (1 + g["cash"]).resample("ME").prod() - 1,
    }).dropna()

    us10 = B.build_curves()["us_10y"].resample("ME").last().reindex(m.index)
    m["d_yield"] = us10.diff()

    cpi = D.fred("CPIAUCSL")
    infl = (cpi / cpi.shift(12) - 1).resample("ME").last().reindex(m.index).ffill()
    m["infl"] = infl
    m = m.dropna()
    m["diff"] = m["p9060"] - m["eq"]

    def bucket(name, mask):
        s = m[mask]
        if len(s) < 6:
            return None
        return {
            "regime": name, "months": len(s),
            "eq_ann": (1 + s["eq"]).prod() ** (12 / len(s)) - 1,
            "p9060_ann": (1 + s["p9060"]).prod() ** (12 / len(s)) - 1,
            "bond_ann": (1 + s["fut"]).prod() ** (12 / len(s)) - 1,
            "diff_pp_per_month": float(s["diff"].mean() * 100),
            "win_rate": float((s["diff"] > 0).mean()),
        }

    hi_infl = m["infl"].quantile(0.80)
    regs = [
        ("A  Equities up (bull months)", m["eq"] > 0),
        ("B  Equities down + yields falling", (m["eq"] < 0) & (m["d_yield"] < 0)),
        ("C  Equities down + yields rising", (m["eq"] < 0) & (m["d_yield"] > 0)),
        ("D  Inflation high (top quintile)", m["infl"] >= hi_infl),
        ("E  Deflation/disinflation + falling yields",
         (m["infl"] < m["infl"].median()) & (m["d_yield"] < 0)),
        ("F  Strong equity bull (top-quartile months)",
         m["eq"] >= m["eq"].quantile(0.75)),
        ("G  Stagflation: high inflation + equities down",
         (m["infl"] >= hi_infl) & (m["eq"] < 0)),
    ]
    print(f"\n    {'regime':46s} {'months':>7s} {'equities':>9s} "
          f"{'90/60':>8s} {'bond leg':>9s} {'diff':>9s} {'90/60 wins':>11s}")
    rows = []
    for name, mask in regs:
        r = bucket(name, mask)
        if r is None:
            continue
        rows.append(r)
        print(f"    {name:46s} {r['months']:7d} {r['eq_ann'] * 100:8.2f}% "
              f"{r['p9060_ann'] * 100:7.2f}% {r['bond_ann'] * 100:8.2f}% "
              f"{r['diff_pp_per_month']:+8.2f}pp {r['win_rate'] * 100:10.1f}%")
    print("\n    The first three return columns are annualised WITHIN each bucket:")
    print("    they describe the pace of returns while that state holds, not a")
    print("    holding-period result.  'diff' is the average monthly difference")
    print("    in percentage points, which is the directly interpretable number.")
    print("\n    This 1990-2026 sample contains no true stagflation -- regime G is")
    print("    built from high-inflation months inside a disinflationary era.")
    print("    Section 10's 98-year US sample is the authority on stagflation.")
    pd.DataFrame(rows).to_csv(rf"{OUT}\regimes.csv", index=False)
    return pd.DataFrame(rows), m


# ===========================================================================
# 10. long US lab, 1928-2025
# ===========================================================================
def long_us_lab():
    head(10, "LONG-RUN US LABORATORY, 1928-2025 (98 years, annual data)")
    print("""
The global reconstruction starts in 1990 and the euro curve in 2004, so neither
covers the 1970s.  Damodaran's annual US series does, and it is the only sample
here that contains a genuine stagflation.  This is a US-only, annual-frequency
approximation of the same structure:

    r = 0.90*stocks + 0.10*bills + 0.60*(10y T-bond - bills) - 0.27% costs

It ignores intra-year rebalancing, so it is a check on the ECONOMICS, not a
substitute for the daily reconstruction.
""")
    d = D.load_damodaran_annual().copy()
    d["p9060"] = (0.90 * d["stocks"] + 0.10 * d["bills"]
                  + 0.60 * (d["bonds"] - d["bills"]) - P.TOTAL_COSTS)
    # borrow 0.5 at fed funds + spread: the yearly average fed-funds-minus-bill
    # gap where fed funds exists (1955+), the 1955-2008 average before that
    ffr = LV.fed_funds().resample("YE").mean()
    ffr.index = ffr.index.year
    gap = (ffr.reindex(d.index) - d["bills"]).fillna(LV.PRE_DFF_GAP["bill_3m"])
    d["lev15"] = (1.5 * d["stocks"] - 0.5 * d["bills"]
                  - 0.5 * (gap + P.LEV15_FINANCING.spread))
    d["diff"] = d["p9060"] - d["stocks"]
    d["term_premium"] = d["bonds"] - d["bills"]
    d["erp"] = d["stocks"] - d["bills"]

    cpi = D.fred("CPIAUCSL")
    ann_infl = cpi.resample("YE").last().pct_change()
    ann_infl.index = ann_infl.index.year
    d["infl"] = ann_infl.reindex(d.index)

    def _mdd(rets):
        nav = (1 + rets).cumprod()
        return float((nav / nav.cummax() - 1).min())

    def stats(sub, label):
        n = len(sub)
        g9 = (1 + sub["p9060"]).prod() ** (1 / n) - 1
        ge = (1 + sub["stocks"]).prod() ** (1 / n) - 1
        v9, ve = sub["p9060"].std(ddof=1), sub["stocks"].std(ddof=1)
        rf = sub["bills"]
        s9 = (sub["p9060"] - rf).mean() / (sub["p9060"] - rf).std(ddof=1)
        se = (sub["stocks"] - rf).mean() / (sub["stocks"] - rf).std(ddof=1)
        return {"period": label, "years": n,
                "equities": ge, "p9060": g9, "diff_pp": (g9 - ge) * 100,
                "vol_eq": ve, "vol_9060": v9,
                "sharpe_eq": se, "sharpe_9060": s9,
                "mdd_eq": _mdd(sub["stocks"]), "mdd_9060": _mdd(sub["p9060"]),
                "term_premium": sub["term_premium"].mean(),
                "win_rate": float((sub["diff"] > 0).mean())}

    periods = [("1928-2025 full", 1928, 2025), ("1928-1949", 1928, 1949),
               ("1950-1969", 1950, 1969),
               ("1970-1981 stagflation & rate spike", 1970, 1981),
               ("1982-1999 disinflation bull", 1982, 1999),
               ("2000-2019", 2000, 2019), ("2020-2025", 2020, 2025)]
    print(f"    {'period':36s} {'yrs':>4s} {'equities':>9s} {'90/60':>8s} "
          f"{'diff':>9s} {'avg term prem':>14s} {'90/60 wins':>11s}")
    rows = []
    for lbl, a, b in periods:
        sub = d.loc[a:b]
        r = stats(sub, lbl)
        rows.append(r)
        print(f"    {lbl:36s} {r['years']:4d} {r['equities'] * 100:8.2f}% "
              f"{r['p9060'] * 100:7.2f}% {r['diff_pp']:+8.2f}pp "
              f"{r['term_premium'] * 100:13.2f}% {r['win_rate'] * 100:10.1f}%")

    full = rows[0]
    print(f"\n    RISK over the full 98 years -- the return race is a dead heat,")
    print(f"    so the whole case rests on this half of the table:")
    print(f"      {'':22s} {'equities':>10s} {'90/60':>10s}")
    print(f"      {'CAGR':22s} {full['equities'] * 100:9.2f}% "
          f"{full['p9060'] * 100:9.2f}%")
    print(f"      {'annual vol':22s} {full['vol_eq'] * 100:9.2f}% "
          f"{full['vol_9060'] * 100:9.2f}%")
    print(f"      {'Sharpe (annual data)':22s} {full['sharpe_eq']:10.3f} "
          f"{full['sharpe_9060']:10.3f}")
    print(f"      {'max drawdown':22s} {full['mdd_eq'] * 100:9.2f}% "
          f"{full['mdd_9060'] * 100:9.2f}%")
    print(f"      {'worst year':22s} {d['stocks'].min() * 100:9.2f}% "
          f"{d['p9060'].min() * 100:9.2f}%")

    hi = d["infl"].quantile(0.8)
    print("\n    Inflation regimes (US CPI, 1948-2025):")
    for lbl, mask in [("inflation in the top quintile", d["infl"] >= hi),
                      ("inflation below median",
                       d["infl"] < d["infl"].median()),
                      ("stagflation: high inflation AND equities down",
                       (d["infl"] >= hi) & (d["stocks"] < 0))]:
        sub = d[mask.fillna(False)]
        if len(sub) < 3:
            continue
        r = stats(sub, lbl)
        print(f"    {lbl:36s} {r['years']:4d} {r['equities'] * 100:8.2f}% "
              f"{r['p9060'] * 100:7.2f}% {r['diff_pp']:+8.2f}pp "
              f"{r['term_premium'] * 100:13.2f}% {r['win_rate'] * 100:10.1f}%")

    print("\n    Worst single years for the 90/60 structure:")
    for yr, row in d.nsmallest(5, "p9060").iterrows():
        print(f"      {yr}  90/60 {row['p9060'] * 100:7.2f}%   "
              f"equities {row['stocks'] * 100:7.2f}%   "
              f"bonds {row['bonds'] * 100:6.2f}%   "
              f"bills {row['bills'] * 100:5.2f}%   "
              f"diff {row['diff'] * 100:+6.2f}pp")

    d.to_csv(rf"{OUT}\long_us_annual.csv")
    pd.DataFrame(rows).to_csv(rf"{OUT}\long_us_periods.csv", index=False)
    return d, pd.DataFrame(rows)


# ===========================================================================
# 11. robustness of modelling choices
# ===========================================================================
def robustness(g: pd.DataFrame):
    head(11, "ROBUSTNESS OF THE MODELLING CHOICES")
    eq = M.cagr(g["equity_dm"])
    rows = []

    print(f"\n    {'variant':44s} {'90/60 CAGR':>11s} {'vol':>7s} "
          f"{'Sharpe':>7s} {'vs equities':>12s}")

    def add(label, panel_kwargs):
        p = P.global_panel(**panel_kwargs)
        p = p.loc[g.index[0]:g.index[-1]]
        c, v = M.cagr(p["rec9060"]), M.vol(p["rec9060"])
        s = M.sharpe(p["rec9060"], p["rf"])
        rows.append({"variant": label, "cagr": c, "vol": v, "sharpe": s,
                     "vs_equities_pp": (c - eq) * 100})
        print(f"    {label:44s} {c * 100:10.2f}% {v * 100:6.2f}% {s:7.2f} "
              f"{(c - eq) * 100:+11.2f} pp")

    add("base case (CTD ladder, fund currency weights)", {})
    add("nominal 2/5/10/30 ladder", {"ladder": B.LADDER_NOMINAL})
    for name, w in B.CCY_ALTS.items():
        add(f"currency weights: {name}", {"ccy_weights": w})
    add("zero costs (index, not fund)", {"costs": 0.0})
    add("costs doubled to 0.54%/yr", {"costs": 2 * P.TOTAL_COSTS})

    print(f"\n    100% developed equities: {eq * 100:.2f}% CAGR, "
          f"{M.vol(g['equity_dm']) * 100:.2f}% vol, "
          f"Sharpe {M.sharpe(g['equity_dm'], g['rf']):.2f}")

    print(f"\n    Bond-sleeve currency coverage grows with the source curves")
    print(f"    (BoE gilt par yields start 1993, the ECB euro curve 2004):")
    for a, b in [("1990-07-03", "1993-10-31"), ("1993-11-01", "2004-09-06"),
                 ("2004-09-07", "2026-07-31")]:
        seg = g.loc[a:b]
        print(f"      {a} .. {b}: {seg['n_ccy'].mode().iloc[0]:.0f} currencies, "
              f"sleeve excess return {M.cagr(seg['futures']) * 100:+.2f}% p.a.")
    post = g.loc["2004-09-07":]
    p_us = P.global_panel(ccy_weights=B.CCY_ALTS["US only"]).loc["2004-09-07":]
    print(f"      over 2004-2026 a US-only sleeve returns "
          f"{M.cagr(p_us['futures']) * 100:+.2f}% p.a., i.e. the currency mix is")
    print(f"      worth {(M.cagr(post['futures']) - M.cagr(p_us['futures'])) * 100:+.2f}pp")
    print(f"      on the sleeve, {0.6 * (M.cagr(post['futures']) - M.cagr(p_us['futures'])) * 100:+.2f}pp at the fund level.")

    pd.DataFrame(rows).to_csv(rf"{OUT}\robustness.csv", index=False)
    return pd.DataFrame(rows)


# ===========================================================================
def main():
    g, px = build_panels()

    head(1, "WINDOWS AND DATA PROVENANCE")
    print(f"""
    Reconstruction window   {g.index[0].date()} .. {g.index[-1].date()}
                            ({M.years_of(g.index):.1f} years, {len(g):,} trading days)
    Actual NTSG history     2024-11-08 .. {px['NTSG.L'].dropna().index[-1].date()}
                            (1.8 years -- SYNTHETIC history before that)
    Actual NTSX history     2018-08-02 .. {px['NTSX'].dropna().index[-1].date()}
                            (same construction, US-only; the replication test)

    Everything below the NTSG row is a RECONSTRUCTION built from index rules
    plus primary market data.  It is not fund history and is labelled as such
    in every table.  Bond-sleeve currencies: 3 (USD/GBP/JPY) before 2004-09,
    4 afterwards, because the ECB euro curve starts then.
    """)

    head(2, "TABLE 1 -- RETURN AND RISK, COMMON WINDOW")
    series = {
        "Global equities, All World (ACWI)": g["acwi"].dropna(),
        "Developed equities (index NTSG tracks)": g["equity_dm"],
        "Developed equities, 1.5x levered": g["lev15"],
        "Developed small-cap value": g["scv_dm"].dropna(),
        "Reconstructed 90/60": g["rec9060"],
    }
    common = None
    for s in series.values():
        common = s.dropna().index if common is None else common.intersection(
            s.dropna().index)
    print(f"\n  (a) COMMON window to all five: {common[0].date()} .. "
          f"{common[-1].date()} ({M.years_of(common):.1f} years)")
    tbl_common = M.summary_table({k: v.reindex(common) for k, v in series.items()},
                                 g["rf"])
    print(M.fmt_table(tbl_common.drop(columns=["worst_year_when",
                                               "best_year_when"])))

    print(f"\n  (b) LONGEST window available to each series (NOT comparable "
          f"across rows -- windows differ)")
    tbl_own = M.summary_table(series, g["rf"])
    print(M.fmt_table(tbl_own.drop(columns=["worst_year_when",
                                            "best_year_when"])))

    print("\n  (c) The actual fund, over its own short life "
          "(1.8 years -- NOT comparable to the rows above)")
    n = g["ntsg"].dropna()
    tbl_ntsg = M.summary_table(
        {"Actual NTSG (live)": n,
         "Reconstructed 90/60, same window": g["rec9060"].reindex(n.index),
         "Developed equities, same window": g["equity_dm"].reindex(n.index)},
        g["rf"])
    print(M.fmt_table(tbl_ntsg.drop(columns=["worst_year_when",
                                             "best_year_when",
                                             "worst_year", "best_year"])))

    tbl_common.to_csv(rf"{OUT}\table1_common_window.csv", index=False)
    tbl_own.to_csv(rf"{OUT}\table1_own_windows.csv", index=False)
    tbl_ntsg.to_csv(rf"{OUT}\table1_ntsg_window.csv", index=False)

    head(3, "ANNUALISED RETURN COMPARISON ACROSS EXPLICIT WINDOWS")
    windows = [("full reconstruction 1990-2026", g.index[0], g.index[-1]),
               ("since ACWI exists (2008-2026)", pd.Timestamp("2008-03-28"),
                g.index[-1]),
               ("since NTSX exists (2018-2026)", pd.Timestamp("2018-08-02"),
                g.index[-1]),
               ("since NTSG exists (2024-2026)", pd.Timestamp("2024-11-08"),
                g.index[-1])]
    print(f"\n    {'window':32s} " + "".join(f"{k[:14]:>16s}" for k in
                                             list(series) + ["Actual NTSG"]))
    rows = []
    for lbl, a, b in windows:
        vals = {}
        for k, s in list(series.items()) + [("Actual NTSG", g["ntsg"].dropna())]:
            seg = s.loc[a:b].dropna()
            # only report a series that actually spans the window -- otherwise
            # the cell would silently be a different, shorter period
            covers = len(seg) > 20 and (seg.index[0] - a).days <= 45
            vals[k] = M.cagr(seg) if covers else np.nan
        rows.append({"window": lbl, **vals})
        print(f"    {lbl:32s} " + "".join(
            f"{vals[k] * 100:15.2f}%" if pd.notna(vals[k]) else f"{'n/a':>16s}"
            for k in list(series) + ["Actual NTSG"]))
    pd.DataFrame(rows).to_csv(rf"{OUT}\table_annualised_windows.csv", index=False)
    print("\n    Rows use DIFFERENT windows and must not be compared vertically.")
    print("    'n/a' means the series does not span that window at all -- it is")
    print("    never silently replaced by a shorter period.")

    print("\n  Sub-periods of the reconstruction, so the 36-year average is not")
    print("  mistaken for a stable result:\n")
    print(f"    {'sub-period':22s} {'equities':>10s} {'90/60':>9s} {'diff':>9s} "
          f"{'bond leg':>10s} {'90/60 vol':>10s} {'eq vol':>8s}")
    subs = [("1990-1999", "1990-07-03", "1999-12-31"),
            ("2000-2009", "2000-01-01", "2009-12-31"),
            ("2010-2019", "2010-01-01", "2019-12-31"),
            ("2020-2026", "2020-01-01", "2026-07-31")]
    sub_rows = []
    for lbl, a, b in subs:
        s = g.loc[a:b]
        r = {"sub_period": lbl, "equities": M.cagr(s["equity_dm"]),
             "p9060": M.cagr(s["rec9060"]), "bond_leg": M.cagr(s["futures"]),
             "vol_9060": M.vol(s["rec9060"]), "vol_eq": M.vol(s["equity_dm"])}
        r["diff_pp"] = (r["p9060"] - r["equities"]) * 100
        sub_rows.append(r)
        print(f"    {lbl:22s} {r['equities'] * 100:9.2f}% {r['p9060'] * 100:8.2f}% "
              f"{r['diff_pp']:+8.2f}pp {r['bond_leg'] * 100:9.2f}% "
              f"{r['vol_9060'] * 100:9.2f}% {r['vol_eq'] * 100:7.2f}%")
    pd.DataFrame(sub_rows).to_csv(rf"{OUT}\table_subperiods.csv", index=False)
    print("\n    The bond leg column is the excess return on 1.0 of notional; it")
    print("    is the single variable that decides the sign of the 'diff' column.")

    stats = leverage_algebra(g)
    hist_fin, fwd_fin, fwd_bond, short = financing_sensitivity(g, stats)
    rho = parameter_sensitivity(g, fwd_bond, short)
    roll = rolling_analysis(g)
    drawdown_analysis(g)
    regime_analysis(g)
    long_us_lab()
    robustness(g)

    g.to_csv(rf"{OUT}\panel_global_daily.csv")
    with open(rf"{OUT}\headline_stats.json", "w") as fh:
        json.dump({
            "window_start": str(g.index[0].date()),
            "window_end": str(g.index[-1].date()),
            "years": M.years_of(g.index),
            "equity_cagr": stats["equity_cagr"], "cash_cagr": stats["cash_cagr"],
            "erp": stats["erp"], "bond_term_premium": stats["btp"],
            "rec9060_cagr": M.cagr(g["rec9060"]),
            "rec9060_vol": M.vol(g["rec9060"]),
            "rec9060_sharpe": M.sharpe(g["rec9060"], g["rf"]),
            "equity_vol": M.vol(g["equity_dm"]),
            "equity_sharpe": M.sharpe(g["equity_dm"], g["rf"]),
            "stock_bond_corr": rho,
            "fwd_ladder_yield": fwd_bond, "fwd_short_rate": short,
        }, fh, indent=2)
    D.write_manifest("ec_analysis.py")
    print(f"\n\nWrote CSV/JSON outputs to {OUT}")


if __name__ == "__main__":
    main()
