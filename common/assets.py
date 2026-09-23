"""
assets.py -- every return series the backtester can use, by name.

Each entry returns DAILY SIMPLE returns (decimal), indexed by date. Names
ending in _FUT are EXCESS returns (asset minus its financing rate), i.e. what a
futures position earns: use them as UNFUNDED legs. Everything else is a total
return: use it as a funded leg.

Any name not in the registry is treated as a Yahoo ticker (split- and
dividend-adjusted close, cached in efficient_core/data_cache/).

    from common import assets
    r = assets.load("US_MKT")
    python -m common.backtest --list
"""
from __future__ import annotations

import sys
from functools import lru_cache

import pandas as pd

from common import paths

sys.path.insert(0, str(paths.EC))
sys.path.insert(0, str(paths.KD))


def _D():
    import ec_data
    return ec_data


def _B():
    import ec_bonds
    return ec_bonds


# --------------------------------------------------------------------------
# cash
# --------------------------------------------------------------------------
@lru_cache(maxsize=None)
def bill_daily() -> pd.Series:
    """Daily T-bill return. Ken French's 1-month bill where it exists (1926 ->
    its last date), then the 3-month bill (FRED DTB3, bond-equivalent)
    accrued per calendar day. Both are T-bill rates, so the join is a
    continuation of the same thing, not a change of asset."""
    from common import ff
    kf = ff.us_market_daily()["rf"]
    b3 = _D().load_us_curve()["us_3m"].dropna()
    dt = b3.index.to_series().diff().dt.days / 365.0
    tail = (b3.shift(1) * dt).dropna()
    tail = tail[tail.index > kf.index[-1]]
    return pd.concat([kf, tail]).rename("CASH")


def bill_on(cal: pd.DatetimeIndex) -> pd.Series:
    """The bill return on an arbitrary trading calendar, accrued over each gap."""
    b3 = _D().load_us_curve()["us_3m"]
    b3 = b3.reindex(b3.index.union(cal)).ffill(limit=7).reindex(cal)
    dt = pd.Series(cal, index=cal).diff().dt.days / 365.0
    return (b3.shift(1) * dt).rename("CASH")


# --------------------------------------------------------------------------
# equities
# --------------------------------------------------------------------------
def _us_mkt():
    from common import ff
    return ff.us_market_daily()["mkt_total"]


def _us_scv():
    from common import ff
    return ff.us_small_value_daily()


def _dm_mkt():
    return _D().load_ff_developed_daily()["dm_total"]


def _dm_exus():
    return _D().load_ff_developed_ex_us_daily()["exus_total"]


def _dm_scv():
    return _D().load_ff_developed_scv_daily()["dm_scv_total"]


# --------------------------------------------------------------------------
# bonds (synthetic, from the yield curves in ec_bonds)
# --------------------------------------------------------------------------
def _ust(m: float):
    def f():
        B = _B()
        r = B.cm_bond_returns(B.build_curves(), B.CURVE_POINTS["usd"], m, B.COUPON_FREQ["usd"])
        return r["tr"]
    return f


def _ust_ladder_fut(tenors=(2, 5, 10, 30)):
    def f():
        B = _B()
        cal = _D().load_us_curve().dropna(subset=["us_3m"]).index
        return B.us_only_sleeve(B.build_curves(), cal, tenors)["sleeve"].dropna()
    return f


def _global_bond_fut():
    B = _B()
    cal = _D().load_us_curve().dropna(subset=["us_3m"]).index
    return B.futures_sleeve(B.build_curves(), cal)["sleeve"].dropna()


# --------------------------------------------------------------------------
# testfolio exports
# --------------------------------------------------------------------------
def _tf(name: str):
    def f():
        df = pd.read_csv(paths.TESTFOLIO_DATA / f"{name}_daily.csv", parse_dates=["date"])
        return df.set_index("date")["value"].sort_index().pct_change().dropna()
    return f


REGISTRY = {
    "CASH": ("T-bill: KF 1-month to 2026-04, then 3-month DTB3 (bond-equivalent)", bill_daily),
    "US_MKT": ("US total market, CRSP value-weighted (Ken French), 1926+", _us_mkt),
    "US_SCV": ("US small-cap value, Ken French SMALL HiBM (VW), 1926+", _us_scv),
    "DM_MKT": ("Developed markets (Ken French Developed), USD, 1990+", _dm_mkt),
    "DM_EXUS": ("Developed ex-US (Ken French), USD, 1990+", _dm_exus),
    "DM_SCV": ("Developed small-cap value (Ken French), USD, 1990+", _dm_scv),
    "UST_2Y": ("Synthetic constant-maturity 2y Treasury, total return, 1976+", _ust(2)),
    "UST_5Y": ("Synthetic constant-maturity 5y Treasury, total return, 1962+", _ust(5)),
    "UST_10Y": ("Synthetic constant-maturity 10y Treasury, total return, 1962+", _ust(10)),
    "UST_20Y": ("Synthetic constant-maturity 20y Treasury, total return, 1977+", _ust(20)),
    "UST_LADDER_FUT": ("Equal-weight 2/5/10/30y UST futures ladder (NTSX's), EXCESS", _ust_ladder_fut()),
    "GLOBAL_BOND_FUT": ("NTSG 4-currency bond futures sleeve, EXCESS, 1990+", _global_bond_fut),
    "TF_VEASIM": ("testfolio VEASIM (developed ex-US), 1970+", _tf("VEASIM")),
    "TF_TLTSIM": ("testfolio TLTSIM (long Treasuries), 1962+", _tf("TLTSIM")),
    "TF_DBMFSIM": ("testfolio DBMFSIM (managed futures), 2000+", _tf("DBMFSIM")),
    "TF_FFSCV": ("testfolio FFSCV (small value, not KF SMALL HiBM), 1926-2025", _tf("FFSCV")),
}


@lru_cache(maxsize=None)
def load(name: str) -> pd.Series:
    """Daily returns for a registry name, or a Yahoo ticker."""
    if name in REGISTRY:
        return REGISTRY[name][1]().rename(name)
    px = _D().load_prices([name])[name].dropna()
    return px.pct_change(fill_method=None).dropna().rename(name)
