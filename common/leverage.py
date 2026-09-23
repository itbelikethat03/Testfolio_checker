"""
leverage.py -- one model of what leverage costs, used by every study.

A position levered L times on a risky asset with excess return x earns, per
period of length dt years,

    r = rf + L * x  -  max(L - 1, 0) * (gap + spread * dt)  -  ter * dt

* rf + L * x is the frictionless part: the whole NAV earns the bill rate, and
  L units of exposure earn the excess return (borrowing at rf is inside
  x = r_asset - rf).
* gap is the per-period difference between the BORROWING BENCHMARK and rf.
  Money is lent (cash, collateral) at the T-bill rate but borrowed against
  the effective FED FUNDS rate: Interactive Brokers' benchmark is fed funds,
  and leveraged-ETF swaps and equity-index futures financing key off
  overnight rates (fed funds / LIBOR / SOFR), not T-bills. The two were close
  after 2009 but not before it: fed funds averaged 0.33pp/yr above the 3-month
  bill over 1955-2008 (0.6-0.8pp in the 1970s-80s) and 0.53pp above Ken
  French's 1-month bill. Charging borrowing at the bill rate therefore
  flattered every pre-2009 levered history by ~0.3-0.5pp x (L - 1) a year.
* spread is what the borrower pays OVER fed funds, on the borrowed part only.
* ter is a fund's expense ratio, charged on NAV.

The `frictionless` preset keeps the textbook case: borrow at rf, gap = 0.

`daily_reset` records HOW the leverage is held (a leveraged ETF resets to L
every day; a futures overlay or a margin account drifts and is rebalanced on a
schedule). For periodic rebalancing use common.backtest.

PRESETS (spreads over fed funds)
--------------------------------
frictionless  borrow at rf, no gap, no spread
futures       +0.30%                    -- equity-index futures implied financing
broker        +1.00%                    -- retail margin loan (Interactive Brokers
                                           Pro: fed funds + 1.5% below $100k, +1.0%
                                           to $1M, +0.5% to $50M); `with_spread`
letf          +LETF_SPREAD, 0.91% TER, daily reset
                                        -- a 2x/3x S&P 500 ETF (SSO / UPRO);
                                           LETF_SPREAD is FITTED to the live funds
                                           by common/validate_leverage.py
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from functools import lru_cache

import numpy as np
import pandas as pd

from common import paths

# Fitted by common/validate_leverage.py: the swap spread over effective fed funds
# that makes a modelled SSO / UPRO match the live funds' total return
# (SSO 2006-2026: 0.69%, UPRO 2009-2026: 0.69%).
LETF_SPREAD = 0.0069

# Before FRED's daily fed funds series starts (1954-07), the benchmark is taken
# as the bill rate plus the average 1955-2008 gap between fed funds and the
# bill in question (measured by validate_leverage.py). Only the Kelly study
# (1926+) reaches back that far.
PRE_DFF_GAP = {"kf_1m": 0.0053, "bill_3m": 0.0033}


@dataclass(frozen=True)
class Financing:
    name: str
    spread: float = 0.0            # annual, over the benchmark, on the borrowed notional
    ter: float = 0.0               # annual, on NAV
    daily_reset: bool = False
    over_fed_funds: bool = True    # False: borrow at rf (the frictionless case)
    note: str = ""

    def with_spread(self, spread: float) -> "Financing":
        return replace(self, name=f"{self.name}@{spread:.2%}", spread=spread)

    def cost(self, leverage: float, dt, gap=0.0):
        """Cost per period, as a positive return. `dt` is the period length in
        years; `gap` the per-period benchmark-minus-rf accrual (see gap_on)."""
        g = gap if self.over_fed_funds else 0.0
        return max(leverage - 1.0, 0.0) * (g + self.spread * dt) + self.ter * dt


PRESETS = {
    "frictionless": Financing("frictionless", over_fed_funds=False,
                              note="borrow at the bill rate"),
    "futures": Financing("futures", spread=0.0030,
                         note="equity-index futures, fed funds + 0.30%"),
    "broker": Financing("broker", spread=0.0100,
                        note="retail margin loan, fed funds + 1.0%"),
    "letf": Financing("letf", spread=LETF_SPREAD, ter=0.0091, daily_reset=True,
                      note="2x/3x S&P 500 ETF, swap spread over fed funds fitted to SSO/UPRO"),
}

SPREAD_GRID = (0.0, 0.003, 0.005, 0.010, 0.015)


def get(fin: "Financing | str | None") -> Financing:
    if fin is None:
        return PRESETS["frictionless"]
    return PRESETS[fin] if isinstance(fin, str) else fin


# --------------------------------------------------------------------------
# the borrowing benchmark
# --------------------------------------------------------------------------
@lru_cache(maxsize=None)
def fed_funds() -> pd.Series:
    """Effective fed funds rate, daily, annual decimal (FRED DFF, 1954-07+)."""
    sys.path.insert(0, str(paths.EC))
    import ec_data
    return (ec_data.fred("DFF") / 100.0).dropna()


def benchmark_on(cal: pd.DatetimeIndex, rf: pd.Series, rf_kind: str) -> pd.Series:
    """Per-period accrual of the borrowing benchmark on trading calendar `cal`:
    yesterday's fed funds rate over the calendar days since (act/360, the
    money-market convention). Before fed funds exists: rf + the average gap for
    that kind of bill (PRE_DFF_GAP[rf_kind])."""
    ffr = fed_funds()
    lvl = ffr.reindex(ffr.index.union(cal)).ffill(limit=10).reindex(cal)
    days = pd.Series(cal, index=cal).diff().dt.days
    acc = lvl.shift(1) * days / 360.0
    rf = rf.reindex(cal)
    early = acc.isna() & (cal < ffr.index[0] + pd.Timedelta(days=10))
    acc[early] = rf[early] + PRE_DFF_GAP[rf_kind] * days[early].fillna(1) / 365.25
    return acc


def gap_on(cal: pd.DatetimeIndex, rf: pd.Series, rf_kind: str) -> pd.Series:
    """Benchmark minus rf, per period: what borrowing costs over lending,
    before any spread. Series on `cal`."""
    return (benchmark_on(cal, rf, rf_kind) - rf.reindex(cal)).rename("borrow_gap")


def levered_returns(x, rf, leverage: float, fin: "Financing | str | None" = None,
                    dt=None, ppy: float | None = None, gap=0.0):
    """Daily-reset levered return: rf + L*x - costs.

    `x` excess returns and `rf` bill returns per period (arrays or Series).
    Give the period length either as `dt` (year fractions, per period) or as
    `ppy` (periods per year, constant); `gap` as from gap_on()."""
    fin = get(fin)
    if dt is None:
        if ppy is None:
            raise ValueError("pass dt or ppy")
        dt = 1.0 / ppy
    return rf + leverage * x - fin.cost(leverage, dt, gap)
