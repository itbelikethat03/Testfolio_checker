"""
backtest.py -- a testfolio-style portfolio engine: any mix of legs, drifting
weights, calendar and band rebalancing, unfunded (futures) legs, borrowing at a
spread, and a fund-level expense ratio.

THE ACCOUNTING
--------------
Each leg is either
  funded    capital is invested in it; its value drifts with its return
            (a negative weight is a loan: its return is the borrowing rate)
  unfunded  a futures / swap overlay: no capital, notional N earns N * r where
            r is already an EXCESS return (asset minus financing)

Per period of length dt years:

  V_i   <- V_i * (1 + r_i) - |V_i| * spread_i * dt          funded legs
  pnl    = sum_j N_j * (r_j - spread_j * dt)                 unfunded legs
  NAV'   = (sum_i V_i + pnl) * (1 - ter * dt)
  V_res <- NAV' - sum_{i != res} V_i                         P&L and costs settle
                                                             in the residual leg

`spread` is a per-leg financing charge: on a loan (negative V) it raises the
borrowing rate, on a futures leg it lowers the excess return. Weights are the
DRIFTED weights, reported before any rebalance on that day. A rebalance resets
every leg to target * NAV and happens on the calendar schedule OR whenever a
non-residual leg drifts more than `band` from its target.

This is the machine behind the NTSG/NTSX/NTSD reconstructions (efficient_core)
and every fund in reconstructions/. `simulate_efficient_core` and
`levered_equity` in ec_portfolios.py are thin wrappers over it.

CLI
---
    python -m common.backtest "US_MKT:0.9,UST_LADDER:0.6u,CASH:0.1" --rebal quarterly --band 0.05
    python -m common.backtest "US_MKT:1.5,CASH:-0.5" --financing broker --rebal monthly

`name:weight` is a funded leg; a trailing `u` marks it unfunded. Asset names
come from common/assets.py (`python -m common.backtest --list`).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Leg:
    returns: pd.Series            # simple return per period (excess, if unfunded)
    weight: float                 # target weight (notional / NAV if unfunded)
    funded: bool = True
    spread: float = 0.0           # annual financing charge, see module docstring


def on_calendar(r: pd.Series, cal: pd.DatetimeIndex) -> pd.Series:
    """Re-express returns on another trading calendar by carrying the LEVEL
    forward, so compounding stays exact. Needed because the bond market (FRED)
    and the stock market close on different days (Columbus Day, Veterans Day):
    intersecting the two calendars would silently delete stock-market days."""
    r = r.dropna()
    lv = (1 + r).cumprod()
    lv = lv.reindex(lv.index.union(cal)).ffill().reindex(cal)
    return lv.pct_change().loc[r.index[0]:]


# --------------------------------------------------------------------------
# rebalance calendars
# --------------------------------------------------------------------------
SCHEDULES = {
    "monthly": tuple(range(1, 13)),
    "quarterly": (3, 6, 9, 12),
    "semiannual": (6, 12),
    "annual": (12,),
}


def month_ends(idx: pd.DatetimeIndex, months) -> set:
    """Last available trading day of each of `months` (1..12)."""
    s = pd.Series(idx, index=idx)
    grp = s.groupby([idx.year, idx.month]).max()
    return {d for (y, m), d in grp.items() if m in months}


def rebalance_dates(idx: pd.DatetimeIndex, rebalance) -> tuple[set, bool]:
    """(set of calendar rebalance dates, daily?) for a schedule spec:
    'daily' | 'never' | 'monthly' | 'quarterly' | 'semiannual' | 'annual' |
    a tuple of month numbers | an explicit set/list of dates."""
    if isinstance(rebalance, str):
        if rebalance == "daily":
            return set(), True
        if rebalance == "never":
            return set(), False
        return month_ends(idx, SCHEDULES[rebalance]), False
    if isinstance(rebalance, tuple) and all(isinstance(m, int) for m in rebalance):
        return month_ends(idx, rebalance), False
    return set(rebalance), False


# --------------------------------------------------------------------------
# the engine
# --------------------------------------------------------------------------
def backtest(legs: dict[str, Leg], residual: str | None = None,
             rebalance="quarterly", band: float | None = None,
             ter: float = 0.0, index: pd.DatetimeIndex | None = None,
             floor: float | None = None) -> pd.DataFrame:
    """Simulate the portfolio. Returns a frame indexed by date with `nav`,
    `ret` and `w_<leg>` (drifted weight before any rebalance that day).

    residual  the funded leg that absorbs P&L and costs. Defaults to a leg
              named "cash" if there is one; without a residual, P&L and costs
              are spread pro rata over the funded legs.
    index     the calendar; defaults to the dates on which every leg has data.
    floor     lowest NAV allowed (a levered book that is wiped out stays at
              `floor` instead of going negative)."""
    names = list(legs)
    if residual is None and "cash" in legs:
        residual = "cash"
    if residual is not None and not legs[residual].funded:
        raise ValueError("the residual leg must be funded")

    if index is None:
        index = None
        for leg in legs.values():
            i = leg.returns.dropna().index
            index = i if index is None else index.intersection(i)
    idx = pd.DatetimeIndex(index).sort_values()

    R = np.column_stack([legs[k].returns.reindex(idx).to_numpy(float) for k in names])
    tgt = np.array([legs[k].weight for k in names], float)
    funded = np.array([legs[k].funded for k in names], bool)
    spread = np.array([legs[k].spread for k in names], float)
    res = names.index(residual) if residual is not None else -1
    others = [i for i in range(len(names)) if i != res]
    dt = pd.Series(idx, index=idx).diff().dt.days.fillna(1).to_numpy() / 365.0
    cal, daily = rebalance_dates(idx, rebalance)
    band_on = band is not None and not daily
    has_spread = bool(np.any(spread != 0.0))

    n, k = len(idx), len(names)
    navs, rets = np.empty(n), np.empty(n)
    W = np.empty((n, k))
    V = tgt.copy()                      # funded: value; unfunded: notional
    NAV = float(tgt[funded].sum())
    if not np.isclose(NAV, 1.0):
        raise ValueError(f"funded weights must sum to 1 (got {NAV:.6f})")

    for t in range(n):
        r = R[t]
        Vn = V.copy()
        if has_spread:
            Vn[funded] = V[funded] * (1 + r[funded]) - np.abs(V[funded]) * spread[funded] * dt[t]
            pnl = float(np.sum(V[~funded] * (r[~funded] - spread[~funded] * dt[t])))
        else:
            Vn[funded] = V[funded] * (1 + r[funded])
            pnl = float(np.sum(V[~funded] * r[~funded]))

        if res >= 0:
            fund_sum = 0.0
            for i in others:
                if funded[i]:
                    fund_sum += Vn[i]
            NAVn = (fund_sum + Vn[res] + pnl) * (1 - ter * dt[t])
        else:
            NAVn = (float(Vn[funded].sum()) + pnl) * (1 - ter * dt[t])
        if floor is not None:
            NAVn = max(NAVn, floor)

        rets[t] = NAVn / NAV - 1.0
        if res >= 0:
            Vn[res] = NAVn - fund_sum
        else:
            s = float(Vn[funded].sum())
            if s != 0:
                Vn[funded] *= NAVn / s
        NAV = NAVn
        V = Vn
        W[t] = V / NAV
        navs[t] = NAV

        need = daily or idx[t] in cal
        if not need and band_on:
            for i in others:
                if abs(W[t, i] - tgt[i]) > band:
                    need = True
                    break
        if need:
            V = tgt * NAV

    out = pd.DataFrame({"nav": navs, "ret": rets}, index=idx)
    for j, name in enumerate(names):
        out[f"w_{name}"] = W[:, j]
    return out


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _parse_spec(spec: str) -> list[tuple[str, float, bool]]:
    legs = []
    for part in spec.split(","):
        name, w = part.strip().split(":")
        unfunded = w.endswith("u")
        legs.append((name.strip(), float(w.rstrip("u")), not unfunded))
    return legs


def main(argv=None):
    import argparse
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from common import assets, leverage, metrics

    ap = argparse.ArgumentParser(description="testfolio-style backtest")
    ap.add_argument("spec", nargs="?", help='e.g. "US_MKT:0.9,UST_LADDER:0.6u,CASH:0.1"')
    ap.add_argument("--rebal", default="quarterly")
    ap.add_argument("--band", type=float, default=None)
    ap.add_argument("--ter", type=float, default=0.0)
    ap.add_argument("--financing", default="frictionless",
                    help="spread on a negative CASH leg: " + ", ".join(leverage.PRESETS))
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--csv", help="write the daily result here")
    ap.add_argument("--list", action="store_true", help="list asset names")
    a = ap.parse_args(argv)

    if a.list or not a.spec:
        for name, (desc, _) in assets.REGISTRY.items():
            print(f"  {name:<14} {desc}")
        return

    fin = leverage.get(a.financing)
    spec = _parse_spec(a.spec)
    # Every leg goes onto the FIRST leg's trading calendar (see on_calendar);
    # cash accrues per calendar day on that calendar.
    cal = assets.load(spec[0][0]).dropna().index
    legs = {}
    for name, w, is_funded in spec:
        if name == "CASH" and w < 0 and fin.over_fed_funds:
            # a loan: fed funds (common/leverage.py) + the preset's spread
            r = leverage.benchmark_on(cal, assets.bill_on(cal), "bill_3m")
        elif name == "CASH":
            r = assets.bill_on(cal)
        else:
            r = on_calendar(assets.load(name), cal)
        sp = fin.spread if (name == "CASH" and w < 0) else 0.0
        legs[name.lower() if name == "CASH" else name] = Leg(r, w, is_funded, sp)
    rf = assets.bill_on(cal)
    res = backtest(legs, rebalance=a.rebal, band=a.band, ter=a.ter + fin.ter)
    r = res["ret"].loc[a.start:a.end]
    tbl = metrics.testfolio_table(r, rf)
    print(f"\n{a.spec}   rebalance={a.rebal} band={a.band} financing={fin.name}")
    pct = {"cagr", "max_dd", "avg_dd", "vol"}
    for k, v in tbl.items():
        s = (f"{v*100:.2f}%" if k in pct else f"${v:,.0f}" if k == "ending_value"
             else f"{v:.2f}y" if k == "longest_dd_y" else f"{v:.2f}" if isinstance(v, float) else v)
        print(f"  {k:<14} {s}")
    if a.csv:
        res.loc[a.start:a.end].to_csv(a.csv)
        print(f"wrote {a.csv}")


if __name__ == "__main__":
    main()
