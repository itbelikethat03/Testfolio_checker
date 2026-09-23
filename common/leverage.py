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
letf          1.107 x fed funds + 0.43%, 0.91% TER, daily reset
                                        -- a 2x/3x S&P 500 ETF (SSO / UPRO);
                                           rate_beta and spread are FITTED to the
                                           live funds by common/validate_leverage.py
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from functools import lru_cache

import numpy as np
import pandas as pd

from common import paths

# Fitted by common/validate_leverage.py, jointly on live SSO and UPRO per-regime
# CAGR errors: the swap financing rate is LETF_RATE_BETA x fed funds + LETF_SPREAD.
# Every regime except 2020-21 is then matched within +-0.12pp/yr, including both
# 4%-rate windows (2006-08, 2022+). 2020-21 is excluded from the fit: the COVID
# crash raised swap/rebalancing costs at ~0% rates (a crisis cost, not a rate
# effect), which leaves this model +0.09 (SSO) / +0.26 (UPRO) pp/yr generous over
# the funds' whole lives. A constant spread fits 0.69% but runs +0.2-0.4pp
# generous at 4% rates, which is what matters for pre-2009 history.
LETF_SPREAD = 0.0043
LETF_RATE_BETA = 1.107

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
    rate_beta: float = 1.0         # borrowing rate = rate_beta * fed funds + spread
    note: str = ""

    def with_spread(self, spread: float) -> "Financing":
        return replace(self, name=f"{self.name}@{spread:.2%}", spread=spread)

    def borrow_premium(self, dt, gap=0.0, ff_acc=0.0):
        """What each borrowed unit costs over rf, per period: fed funds minus rf
        (`gap`), plus (rate_beta - 1) x fed funds (`ff_acc`, the fed-funds
        accrual), plus the spread. Zero gap/beta terms for `frictionless`."""
        if not self.over_fed_funds:
            return self.spread * dt
        extra = (self.rate_beta - 1.0) * ff_acc if self.rate_beta != 1.0 else 0.0
        return gap + extra + self.spread * dt

    def cost(self, leverage: float, dt, gap=0.0, ff_acc=0.0):
        """Cost per period, as a positive return. `dt` is the period length in
        years; `gap` and `ff_acc` per-period accruals (see gap_on / ff_accrual_on)."""
        return (max(leverage - 1.0, 0.0) * self.borrow_premium(dt, gap, ff_acc)
                + self.ter * dt)


PRESETS = {
    "frictionless": Financing("frictionless", over_fed_funds=False,
                              note="borrow at the bill rate"),
    "futures": Financing("futures", spread=0.0030,
                         note="equity-index futures, fed funds + 0.30%"),
    "broker": Financing("broker", spread=0.0100,
                        note="retail margin loan, fed funds + 1.0%"),
    "letf": Financing("letf", spread=LETF_SPREAD, ter=0.0091, daily_reset=True,
                      rate_beta=LETF_RATE_BETA,
                      note=f"2x/3x S&P 500 ETF, swap at {LETF_RATE_BETA:.2f} x fed funds "
                           f"+ {LETF_SPREAD:.2%}, fitted to SSO/UPRO"),
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


def ff_accrual_on(cal: pd.DatetimeIndex, rf: pd.Series, rf_kind: str) -> pd.Series:
    """Fed-funds accrual per period on `cal` (the same as benchmark_on), named
    for the rate_beta term of Financing.cost."""
    return benchmark_on(cal, rf, rf_kind).rename("ff_acc")


def borrow_on(cal: pd.DatetimeIndex, rf: pd.Series, rf_kind: str,
              fin: "Financing | str") -> pd.Series:
    """The full per-period borrowing rate of preset `fin` on `cal`
    (rate_beta x fed funds + spread), for use as a loan leg's return."""
    fin = get(fin)
    ffa = benchmark_on(cal, rf, rf_kind)
    days = pd.Series(cal, index=cal).diff().dt.days
    return fin.rate_beta * ffa + fin.spread * days / 365.0


def gap_on(cal: pd.DatetimeIndex, rf: pd.Series, rf_kind: str) -> pd.Series:
    """Benchmark minus rf, per period: what borrowing costs over lending,
    before any spread. Series on `cal`."""
    return (benchmark_on(cal, rf, rf_kind) - rf.reindex(cal)).rename("borrow_gap")


def levered_returns(x, rf, leverage: float, fin: "Financing | str | None" = None,
                    dt=None, ppy: float | None = None, gap=0.0, ff_acc=0.0):
    """Daily-reset levered return: rf + L*x - costs.

    `x` excess returns and `rf` bill returns per period (arrays or Series).
    Give the period length either as `dt` (year fractions, per period) or as
    `ppy` (periods per year, constant); `gap` as from gap_on()."""
    fin = get(fin)
    if dt is None:
        if ppy is None:
            raise ValueError("pass dt or ppy")
        dt = 1.0 / ppy
    return rf + leverage * x - fin.cost(leverage, dt, gap, ff_acc)
