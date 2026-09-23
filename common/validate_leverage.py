"""
validate_leverage.py -- are we charging leverage correctly? Checked against
real leveraged funds.

SSO (2x S&P 500, 2006+) and UPRO (3x, 2009+) are daily-reset swap/futures
funds. If the cost model in common/leverage.py is right, then

    r_model = bill + L * (r_index - bill) - (L - 1) * (fedfunds - bill + spread) dt - ter dt

with r_index = SPY's total return plus SPY's own expense ratio added back (the
funds track the index, not SPY), bill = the 3-month T-bill (bond-equivalent),
fedfunds = effective fed funds (act/360) and ter = the fund's expense ratio,
must reproduce the live funds' total return for ONE constant `spread`.

WHICH BENCHMARK. The spread is fitted per rate regime twice -- over the bill
and over fed funds. The right benchmark is the one whose fitted spread stays
put when rates move; that choice matters for every pre-2009 levered history,
because fed funds ran 0.3-0.8pp above bills for most of 1955-2008 but not
after. The regime table is written out with the fit.

Writes reconstructions/output/leverage_validation.json.

    python common/validate_leverage.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq

SUITE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SUITE))
sys.path.insert(0, str(SUITE / "efficient_core"))

import ec_data as D                                   # noqa: E402
from common import leverage as LV, manifest, paths    # noqa: E402

SPY_ER = 0.000945
FUNDS = {"SSO": dict(L=2.0, ter=0.0091), "UPRO": dict(L=3.0, ter=0.0091)}
REGIMES = [("2006-2008", "2006-07-01", "2008-12-31"), ("2009-2015 ZIRP", "2009-01-01", "2015-12-31"),
           ("2016-2019", "2016-01-01", "2019-12-31"), ("2020-2021 ZIRP", "2020-01-01", "2021-12-31"),
           ("2022+", "2022-01-01", "2100-01-01")]


def accruals(cal: pd.DatetimeIndex) -> pd.DataFrame:
    """bill (act/365, bond-equivalent) and fed funds (act/360) accrued over
    each gap in `cal`, at yesterday's rate."""
    days = pd.Series(cal, index=cal).diff().dt.days
    bill = D.load_us_curve()["us_3m"]
    bill = bill.reindex(bill.index.union(cal)).ffill(limit=7).reindex(cal)
    ffr = LV.fed_funds()
    ffr = ffr.reindex(ffr.index.union(cal)).ffill(limit=10).reindex(cal)
    return pd.DataFrame({"bill": bill.shift(1) * days / 365.0,
                         "ff": ffr.shift(1) * days / 360.0,
                         "dt": days / 365.0}, index=cal)


def model(d: pd.DataFrame, L, ter, spread, base="ff"):
    r_idx = d["spy"] + SPY_ER * d["dt"]
    borrow = d[base] + spread * d["dt"]
    return d["bill"] + L * (r_idx - d["bill"]) - (L - 1) * (borrow - d["bill"]) - ter * d["dt"]


def cagr(r: pd.Series) -> float:
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    return float((1 + r).prod() ** (1 / yrs) - 1)


def fit(d, L, ter, base) -> float:
    live = cagr(d["fund"])
    return float(brentq(lambda s: cagr(model(d, L, ter, s, base)) - live, -0.10, 0.20))


def main():
    px = D.load_prices(["SPY", "SSO", "UPRO"], start="2006-06-01")
    rets = px.pct_change(fill_method=None)
    out = {}
    print("Leveraged ETFs: live vs modelled from SPY, borrowing at fed funds + spread\n")
    print(f"{'fund':<5} {'window':<25} {'live':>7} {'@0 spread':>10} {'fitted spread':>14} "
          f"{'TE':>6} {'corr':>7}")
    for tic, spec in FUNDS.items():
        d = pd.DataFrame({"spy": rets["SPY"], "fund": rets[tic]}).dropna().iloc[1:]
        d = d.join(accruals(d.index)).dropna()
        s_fit = fit(d, spec["L"], spec["ter"], "ff")
        m0 = model(d, spec["L"], spec["ter"], 0.0)
        mf = model(d, spec["L"], spec["ter"], s_fit)
        regimes = {}
        for lab, a, z in REGIMES:
            sub = d.loc[a:z]
            if len(sub) > 100:
                regimes[lab] = {b: fit(sub, spec["L"], spec["ter"], b) for b in ("bill", "ff")}
        sd = {b: float(np.std([v[b] for v in regimes.values()], ddof=1)) for b in ("bill", "ff")}
        out[tic] = dict(L=spec["L"], ter=spec["ter"], start=str(d.index[0].date()),
                        end=str(d.index[-1].date()), live_cagr=cagr(d["fund"]),
                        model_cagr_zero_spread=cagr(m0), fitted_spread=s_fit,
                        tracking_error=float((d["fund"] - mf).std(ddof=1) * np.sqrt(252)),
                        corr=float(d["fund"].corr(mf)), spread_by_regime=regimes,
                        spread_sd_across_regimes=sd)
        print(f"{tic:<5} {str(d.index[0].date()) + '..' + str(d.index[-1].date()):<25} "
              f"{out[tic]['live_cagr']*100:6.2f}% {cagr(m0)*100:9.2f}% {s_fit*100:13.2f}% "
              f"{out[tic]['tracking_error']*100:5.2f}% {out[tic]['corr']:7.4f}")
        for lab, v in regimes.items():
            print(f"      {lab:<16} spread over bill {v['bill']*100:5.2f}%   over fed funds {v['ff']*100:5.2f}%")
        print(f"      sd across regimes: bill {sd['bill']*100:.2f}   fed funds {sd['ff']*100:.2f}")

    avg = float(np.mean([v["fitted_spread"] for v in out.values() if isinstance(v, dict)]))
    out["benchmark"] = "effective fed funds (FRED DFF), act/360"
    out["letf_spread_used"] = LV.LETF_SPREAD
    out["fitted_mean"] = avg
    print(f"\nmean fitted swap spread {avg*100:.2f}%/yr over fed funds "
          f"(LETF preset uses {LV.LETF_SPREAD*100:.2f}%)")
    if abs(avg - LV.LETF_SPREAD) > 0.0005:
        print("  -> update LETF_SPREAD in common/leverage.py to the fitted value")

    # the pre-2009 gap the benchmark choice is about
    ffr, bill = LV.fed_funds(), D.load_us_curve()["us_3m"]
    g = (pd.DataFrame({"ff": ffr, "bill": bill}).dropna().resample("YE").mean())
    gap = (g["ff"] - g["bill"])
    out["fedfunds_minus_bill3"] = {"1955-2008": float(gap.loc["1955":"2008"].mean()),
                                   "2009+": float(gap.loc["2009":].mean())}
    print(f"fed funds - 3m bill: 1955-2008 {gap.loc['1955':'2008'].mean()*100:+.2f}pp,"
          f" 2009+ {gap.loc['2009':].mean()*100:+.2f}pp")

    paths.RECON_OUT.mkdir(parents=True, exist_ok=True)
    (paths.RECON_OUT / "leverage_validation.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    manifest.record(paths.RECON_OUT, "validate_leverage.py", fitted_spread=avg,
                    benchmark="fed funds")


if __name__ == "__main__":
    main()
