"""
ec_portfolios.py -- the reconstruction of the WisdomTree Global Efficient Core
index, plus the comparison strategies.

THE STRUCTURE, AS DOCUMENTED
----------------------------
Per 1.00 of NAV the index holds
    0.90  physical developed-market large-cap equity
    0.10  cash, spread over USD / EUR / GBP / JPY
    0.60  NOTIONAL government bond futures (no capital required)
and rebalances back to those targets on the last business day of Feb, May, Aug
and Nov, with an extra rebalance whenever the equity or bond weight has drifted
more than 5 percentage points.

So the daily NAV return is

    r = w_e * r_equity  +  w_c * r_cash  +  w_b * r_futures  -  costs

where w_e, w_c, w_b are the DRIFTED weights (not the constant 0.90/0.10/0.60),
r_futures is already an excess return, and costs = 0.27%/yr (0.25% TER + 0.02%
transaction costs, both from the KID dated 07/11/2025).

WHY THE ARITHMETIC MATTERS
--------------------------
Substituting r_futures = r_bond - r_cash and holding weights at target:

    r(90/60) - r(100% equity)  =  0.60 * (bond - cash)  -  0.10 * (equity - cash)

The 90/60 structure beats 100% equities exactly when six units of BOND term
premium beat one unit of EQUITY risk premium.  Everything else in this study is
an empirical measurement of those two quantities.  See ec_analysis.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import ec_bonds as B
import ec_data as D
from common import backtest as BT
from common import leverage as LV

# Costs, from the NTSG KID (07/11/2025) and factsheet (31/07/2026).
TER = 0.0025
TXN_COSTS = 0.0002
TOTAL_COSTS = TER + TXN_COSTS          # 0.27%/yr

W_EQUITY, W_CASH, W_BOND = 0.90, 0.10, 0.60
REBAL_MONTHS = (2, 5, 8, 11)           # last business day of these months
DRIFT_TRIGGER = 0.05                   # percentage points of NAV

# How the 1.5x-equity comparison strategy borrows (common/leverage.py).
LEV15_FINANCING = LV.PRESETS["futures"]


# ---------------------------------------------------------------------------
# building blocks
# ---------------------------------------------------------------------------
def rebalance_dates(idx: pd.DatetimeIndex) -> set:
    """Last available trading day of February, May, August and November."""
    return BT.month_ends(idx, REBAL_MONTHS)


def cash_blend(curves: pd.DataFrame, calendar: pd.DatetimeIndex,
               ccy_weights: dict | None = None,
               unhedged_fx: bool = True) -> pd.Series:
    """Return of the 10% collateral sleeve: local short rates in four
    currencies, with the FX move on the non-USD part (the index holds the
    collateral unhedged, matching the bond currency weights)."""
    ccy_weights = ccy_weights or B.CCY_WEIGHTS
    cur = curves.reindex(curves.index.union(calendar)).ffill(limit=7).reindex(calendar)
    dt = pd.Series(calendar, index=calendar).diff().dt.days / 365.0

    fx = D.load_fx()
    fx = fx.reindex(fx.index.union(calendar)).ffill(limit=7).reindex(calendar)
    fx_ret = {
        "usd": pd.Series(0.0, index=calendar),
        "eur": fx["usd_per_eur"].pct_change(),
        "gbp": fx["usd_per_gbp"].pct_change(),
        "jpy": fx["usd_per_jpy"].pct_change(),
    }

    legs, weights = {}, {}
    for ccy, w in ccy_weights.items():
        if w == 0:
            continue
        r_local = cur[B.FINANCING_COL[ccy]] * dt
        legs[ccy] = ((1 + r_local)
                     * (1 + (fx_ret[ccy].fillna(0.0) if unhedged_fx else 0.0))
                     - 1)
        weights[ccy] = w

    df = pd.DataFrame(legs)
    # Renormalise over the currencies that actually have a rate on each date,
    # so a missing euro rate before 2004 does not silently count as a 0% leg.
    wmat = df.notna().mul(pd.Series(weights, dtype=float), axis=1)
    wsum = wmat.sum(axis=1).replace(0.0, np.nan)
    return (df.fillna(0.0) * wmat).sum(axis=1) / wsum


def simulate_efficient_core(r_equity: pd.Series, r_cash: pd.Series,
                            r_futures: pd.Series,
                            w_equity: float = W_EQUITY,
                            w_cash: float = W_CASH,
                            w_bond: float = W_BOND,
                            costs: float = TOTAL_COSTS,
                            drift_trigger: float = DRIFT_TRIGGER,
                            rebal: set | None = None) -> pd.DataFrame:
    """Full path simulation with drifting weights and the documented rebalance
    rules.  Returns a frame with the NAV, the daily return, and the realised
    equity / bond weights so the drift can be inspected.

    Futures P&L and costs settle in the cash leg (common.backtest)."""
    idx = r_equity.dropna().index
    idx = idx.intersection(r_cash.dropna().index).intersection(
        r_futures.dropna().index).sort_values()
    rebal = rebalance_dates(idx) if rebal is None else rebal
    res = BT.backtest({"equity": BT.Leg(r_equity, w_equity),
                       "bond": BT.Leg(r_futures, w_bond, funded=False),
                       "cash": BT.Leg(r_cash, w_cash)},
                      residual="cash", rebalance=rebal, band=drift_trigger,
                      ter=costs, index=idx)
    return res[["nav", "ret", "w_equity", "w_bond"]]


def levered_equity(r_equity: pd.Series, r_financing: pd.Series, leverage: float,
                   costs: float = 0.0, spread: float = 0.0,
                   rebal: set | None = None, band: float = 0.10) -> pd.DataFrame:
    """L times equity, borrowing (L - 1) at `r_financing` plus `spread`,
    rebalanced back to L on the same schedule as the 90/60 fund or whenever
    the exposure drifts more than `band` from L."""
    idx = r_equity.dropna().index.intersection(r_financing.dropna().index).sort_values()
    rebal = rebalance_dates(idx) if rebal is None else rebal
    res = BT.backtest({"equity": BT.Leg(r_equity, leverage),
                       "debt": BT.Leg(r_financing, 1.0 - leverage, spread=spread)},
                      residual="debt", rebalance=rebal, band=band, ter=costs,
                      index=idx, floor=1e-12)
    return res[["nav", "ret"]]


# ---------------------------------------------------------------------------
# assembled panels
# ---------------------------------------------------------------------------
def global_panel(start: str | None = None, end: str | None = None,
                 ccy_weights: dict | None = None, ladder: dict | None = None,
                 costs: float = TOTAL_COSTS) -> pd.DataFrame:
    """Daily returns of every global strategy on one calendar.

    Columns
        equity_dm   developed-market equities, total return, USD  (FF Developed)
        rf          USD 1-month T-bill
        cash        the fund's 4-currency collateral sleeve
        futures     return on 1.0 notional of the bond futures ladder
        rec9060     reconstructed 90/60 fund, net of 0.27%/yr costs
        lev15       1.5x developed equities, borrowing USD at fed funds + 0.30%
                    (the "futures" financing preset)
        scv_dm      developed-market small-cap value
    """
    ff = D.load_ff_developed_daily()
    scv = D.load_ff_developed_scv_daily()
    curves = B.build_curves()

    cal = ff.index
    fut = B.futures_sleeve(curves, cal, ccy_weights, ladder)
    cash = cash_blend(curves, cal, ccy_weights)

    df = pd.DataFrame(index=cal)
    df["equity_dm"] = ff["dm_total"]
    df["rf"] = ff["rf"]
    df["cash"] = cash
    df["futures"] = fut["sleeve"]
    df["duration"] = fut["duration"]
    df["n_ccy"] = fut["n_ccy"]
    df["scv_dm"] = scv["dm_scv_total"]
    df = df.dropna(subset=["equity_dm", "cash", "futures"])
    if start:
        df = df.loc[start:]
    if end:
        df = df.loc[:end]

    rec = simulate_efficient_core(df["equity_dm"], df["cash"], df["futures"],
                                  costs=costs)
    df["rec9060"] = rec["ret"]
    df["w_equity"] = rec["w_equity"]
    df["w_bond"] = rec["w_bond"]
    # 1.5x equity the way a fund would hold it: equity futures, i.e. borrowing
    # in USD at fed funds plus the futures preset's spread (common/leverage.py).
    # (Not the collateral sleeve: that basket carries unhedged EUR/GBP/JPY
    # moves, which a USD borrower does not.)
    borrow = LV.benchmark_on(df.index, df["rf"], "kf_1m")
    df["lev15"] = levered_equity(df["equity_dm"], borrow, 1.5,
                                 spread=LEV15_FINANCING.spread)["ret"]
    return df.dropna(subset=["rec9060"])


def us_panel(start: str | None = None, end: str | None = None,
             tenors=(2, 5, 10, 30), costs: float = 0.0020) -> pd.DataFrame:
    """The same machine applied to the US-only spec, i.e. NTSX.
    NTSX's expense ratio is 0.20%."""
    ff = D.load_ff_us_daily()
    curves = B.build_curves()
    cal = ff.index
    fut = B.us_only_sleeve(curves, cal, tenors)

    df = pd.DataFrame(index=cal)
    df["equity_us"] = ff["us_total"]
    df["rf"] = ff["rf"]
    df["cash"] = ff["rf"]                      # USD-only collateral
    df["futures"] = fut["sleeve"]
    df["duration"] = fut["duration"]
    df = df.dropna(subset=["equity_us", "futures"])
    if start:
        df = df.loc[start:]
    if end:
        df = df.loc[:end]
    df["rec9060_us"] = simulate_efficient_core(
        df["equity_us"], df["cash"], df["futures"], costs=costs)["ret"]
    return df.dropna(subset=["rec9060_us"])


if __name__ == "__main__":
    from common import metrics as M

    pd.set_option("display.width", 220)
    g = global_panel()
    print(f"Global panel: {g.index.min().date()} -> {g.index.max().date()}  n={len(g):,}")
    print(f"bond-sleeve duration: mean {g['duration'].mean():.2f}y")
    print(f"weight drift: equity {g['w_equity'].min():.3f}..{g['w_equity'].max():.3f}"
          f"   bond {g['w_bond'].min():.3f}..{g['w_bond'].max():.3f}")

    series = {
        "Developed equities (100%)": g["equity_dm"],
        "Developed equities 1.5x": g["lev15"],
        "Reconstructed 90/60": g["rec9060"],
        "Developed small-cap value": g["scv_dm"].dropna(),
    }
    print("\n" + M.fmt_table(M.summary_table(series, g["rf"])))

    u = us_panel(start="2018-08-01")
    print(f"\nUS panel since NTSX launch: {u.index.min().date()} -> "
          f"{u.index.max().date()}  n={len(u):,}")
    print(M.fmt_table(M.summary_table(
        {"US equities": u["equity_us"], "US 90/60 recon": u["rec9060_us"]},
        u["rf"])))
