"""
ec_ntsd.py -- synthetic WisdomTree NTSD (Efficient U.S. Plus International Equity).

THE STRUCTURE
-------------
Per 1.00 of NAV the fund holds
    0.90  physical US large-cap equity
    0.10  T-bills (futures collateral)
    0.60  NOTIONAL developed ex-US equity index futures (MSCI EAFE)
and rebalances quarterly, plus whenever an exposure drifts > 5pp from target.
Same machine as the NTSG reconstruction, with the bond sleeve swapped for an
equity-futures sleeve:

    r = w_us * r_us  +  w_c * rf  +  w_fut * (r_intl - fedfunds - spread)  -  TER - txn

(the collateral earns the bill; the futures embed financing at an overnight
rate, taken as effective fed funds -- see common/leverage.py)

with DRIFTED weights.  At target this is 0.90 us + 0.60 intl - 0.50 rf: the
fund borrows 0.50 of NAV implicitly through the futures, which is exactly the
testfolio LETF term  SW*(L-1)*(FR+SP)  with L = 1.5, SW = 1.  The difference
from the testfolio LETF model is the reset: NTSD is NOT a daily-reset fund.

Inputs
------
historical   Ken French US market (daily, 1926+) for the US leg,
             testfolio VEASIM (daily, 1970+) for the international leg,
             Ken French 1-month T-bill for cash and financing.
             Ends where the FF US file ends (2026-04-30).
live check   SPY + EFA / VEA ETF prices + 3m T-bill, since NTSD's launch,
             compared with the real NTSD price (the testfolio "slippage" test).
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

import ec_data as D
import ec_portfolios as P
from common import leverage as LV
from common import metrics as M
from common import paths

TESTFOLIO = str(paths.TESTFOLIO_DATA)
OUTDIR = os.path.join(D.OUT, "ntsd")
os.makedirs(OUTDIR, exist_ok=True)

W_US, W_CASH, W_INTL = 0.90, 0.10, 0.60
DRIFT_TRIGGER = 0.05

TER = 0.0035           # NTSD prospectus
TXN = 0.0002           # ASSUMED: NTSG's KID figure; NTSD publishes none yet
SPREAD = 0.0030        # ASSUMED: equity-futures implied financing over fed funds
SPREAD_GRID = (0.0, 0.0015, 0.0030, 0.0060, 0.0100)

# Expense ratios backed out of ETF-based underlyings: the fund holds the US
# stocks itself and the futures carry no ETF fee, so neither is paid by NTSD.
ER = {"SPY": 0.000945, "EFA": 0.0032, "VEA": 0.0003, "VEASIM": 0.0003}

HIST_START = "1969-12-31"


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------
def load_testfolio(name: str) -> pd.Series:
    df = pd.read_csv(os.path.join(TESTFOLIO, f"{name}_daily.csv"), parse_dates=["date"])
    return df.set_index("date")["value"].sort_index()


def returns_on(levels: pd.Series, calendar: pd.DatetimeIndex) -> pd.Series:
    """Level series -> simple returns on `calendar`.  Levels are carried
    forward over a missing day so the compounding stays exact."""
    lv = levels.reindex(levels.index.union(calendar)).ffill().reindex(calendar)
    return lv.pct_change()


def year_fraction(idx: pd.DatetimeIndex) -> pd.Series:
    return pd.Series(idx, index=idx).diff().dt.days.fillna(1) / 365.0


def quarter_ends(idx: pd.DatetimeIndex) -> set:
    s = pd.Series(idx, index=idx)
    grp = s.groupby([idx.year, idx.month]).max()
    return {d for (y, m), d in grp.items() if m in (3, 6, 9, 12)}


# --------------------------------------------------------------------------
# the model
# --------------------------------------------------------------------------
def simulate_ntsd(r_us: pd.Series, r_intl: pd.Series, rf: pd.Series,
                  spread: float = SPREAD, ter: float = TER, txn: float = TXN,
                  us_er: float = 0.0, intl_er: float = 0.0,
                  gap: pd.Series | None = None) -> pd.DataFrame:
    """`gap` is the per-period fed-funds-minus-rf accrual (common.leverage.gap_on):
    the futures embed financing at an overnight rate, not at the bill the
    collateral earns. None = finance at rf (the "structure alone" run)."""
    idx = r_us.dropna().index.intersection(r_intl.dropna().index) \
                             .intersection(rf.dropna().index).sort_values()
    dt = year_fraction(idx)
    us = r_us.reindex(idx) + us_er * dt
    g = 0.0 if gap is None else gap.reindex(idx).fillna(0.0)
    fut = r_intl.reindex(idx) + intl_er * dt - rf.reindex(idx) - g - spread * dt
    return P.simulate_efficient_core(us, rf.reindex(idx), fut,
                                     w_equity=W_US, w_cash=W_CASH, w_bond=W_INTL,
                                     costs=ter + txn, drift_trigger=DRIFT_TRIGGER,
                                     rebal=quarter_ends(idx))


def ols(y: pd.Series, X: pd.DataFrame) -> dict:
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    A = np.column_stack([np.ones(len(d)), d[X.columns].to_numpy()])
    b, *_ = np.linalg.lstsq(A, d["y"].to_numpy(), rcond=None)
    resid = d["y"].to_numpy() - A @ b
    s2 = resid @ resid / (len(d) - A.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.inv(A.T @ A)))
    r2 = 1 - (resid @ resid) / ((d["y"] - d["y"].mean()) ** 2).sum()
    names = ["const"] + list(X.columns)
    return {"n": len(d), "r2": float(r2),
            "coef": dict(zip(names, map(float, b))),
            "se": dict(zip(names, map(float, se)))}


def gap_stats(real: pd.Series, synth: pd.Series, ppy: float = 252.0) -> dict:
    g = (real - synth).dropna()
    return {"n_days": int(len(g)),
            "mean_gap_ann": float(g.mean() * ppy),
            "mean_gap_ann_se": float(g.std(ddof=1) / np.sqrt(len(g)) * ppy),
            "tracking_error_ann": float(g.std(ddof=1) * np.sqrt(ppy)),
            "corr": float(real.reindex(g.index).corr(synth.reindex(g.index))),
            "cum_real": float((1 + real.reindex(g.index)).prod() - 1),
            "cum_synth": float((1 + synth.reindex(g.index)).prod() - 1)}


# --------------------------------------------------------------------------
# 1. historical synthetic, 1970 -> FF US end
# --------------------------------------------------------------------------
def historical():
    ff = D.load_ff_us_daily().loc[HIST_START:]
    cal = ff.index
    veasim = returns_on(load_testfolio("VEASIM"), cal)
    ntsdsim_lv = load_testfolio("NTSDSIM")
    ntsdsim = returns_on(ntsdsim_lv, cal).loc[:ntsdsim_lv.index[-1]]

    gap = LV.gap_on(cal, ff["rf"], "kf_1m")
    base = simulate_ntsd(ff["us_total"], veasim, ff["rf"], intl_er=ER["VEASIM"], gap=gap)
    pure = simulate_ntsd(ff["us_total"], veasim, ff["rf"], spread=0, ter=0, txn=0)

    panel = pd.DataFrame({"us_mkt": ff["us_total"], "veasim": veasim, "rf": ff["rf"],
                          "ntsd_synth": base["ret"], "ntsd_pure": pure["ret"],
                          "ntsdsim_testfolio": ntsdsim,
                          "w_us": base["w_equity"], "w_fut": base["w_bond"]}).iloc[1:]
    panel.index.name = "date"
    panel.to_csv(os.path.join(OUTDIR, "ntsd_synthetic_daily.csv"))

    common = panel.dropna(subset=["ntsd_synth", "ntsdsim_testfolio"]).index
    rf = panel["rf"]
    tbl = M.summary_table({
        "NTSD synthetic (net)": panel.loc[common, "ntsd_synth"],
        "NTSD pure (no costs)": panel.loc[common, "ntsd_pure"],
        "testfolio NTSDSIM": panel.loc[common, "ntsdsim_testfolio"],
        "US market (FF)": panel.loc[common, "us_mkt"],
        "VEASIM": panel.loc[common, "veasim"],
    }, rf)
    tbl.to_csv(os.path.join(OUTDIR, "ntsd_summary.csv"), index=False)

    # What is NTSDSIM made of?  Regress it on its presumed ingredients.
    X = pd.DataFrame({"us": panel["us_mkt"], "intl": panel["veasim"], "rf": rf})
    decomp = ols(panel["ntsdsim_testfolio"], X.loc[common])

    # Gap between testfolio and our cost-free construction: the constant is
    # testfolio's fixed annual cost, the rf slope its financing convention.
    tf_gap = panel.loc[common, "ntsdsim_testfolio"] - panel.loc[common, "ntsd_pure"]
    gap_fit = ols(tf_gap, pd.DataFrame({"rf": rf.loc[common]}))

    sens = []
    for sp in SPREAD_GRID:
        r = simulate_ntsd(ff["us_total"], veasim, ff["rf"], spread=sp,
                          intl_er=ER["VEASIM"], gap=gap)["ret"]
        sens.append({"spread": sp, "CAGR": M.cagr(r), "vol": M.vol(r),
                     "MaxDD": M.max_drawdown(r)})
    sens = pd.DataFrame(sens)
    sens.to_csv(os.path.join(OUTDIR, "ntsd_spread_sensitivity.csv"), index=False)

    # The testfolio LETF form: one 0.6/0.4 blend at L = 1.5, reset every day.
    p = panel.dropna(subset=["ntsd_synth"])
    dt = year_fraction(p.index)
    g = gap.reindex(p.index).fillna(0.0)
    daily = (W_US * p["us_mkt"] + W_INTL * (p["veasim"] + ER["VEASIM"] * dt)
             + W_CASH * p["rf"] - W_INTL * (p["rf"] + g + SPREAD * dt) - (TER + TXN) * dt)
    r5 = M.rolling_cagr(p["ntsd_synth"], 5) - M.rolling_cagr(daily, 5)
    reset = {"cagr_drift": M.cagr(p["ntsd_synth"]), "cagr_daily_reset": M.cagr(daily),
             "vol_daily_reset": M.vol(daily), "maxdd_daily_reset": M.max_drawdown(daily),
             "rolling5y_gap_min": float(r5.min()), "rolling5y_gap_max": float(r5.max())}

    return panel, tbl, decomp, gap_fit, tf_gap, sens, reset


# --------------------------------------------------------------------------
# 2. source cross-check: Ken French Developed ex US vs VEASIM, 1990+
# --------------------------------------------------------------------------
def source_check(panel: pd.DataFrame) -> dict:
    ex = D.load_ff_developed_ex_us_daily()["exus_total"]
    d = pd.concat([ex, panel["veasim"]], axis=1, join="inner").dropna()
    mo = (1 + d).resample("ME").prod() - 1
    alt = simulate_ntsd(panel["us_mkt"], ex, panel["rf"],
                        gap=LV.gap_on(panel.index, panel["rf"], "kf_1m"))["ret"]
    ours = panel["ntsd_synth"].reindex(alt.index)
    return {"window": [str(d.index[0].date()), str(d.index[-1].date())],
            "corr_daily": float(d.corr().iloc[0, 1]),
            "corr_monthly": float(mo.corr().iloc[0, 1]),
            "cagr_ff_exus": M.cagr(d["exus_total"]),
            "cagr_veasim": M.cagr(d["veasim"]),
            "ntsd_cagr_with_ff_exus": M.cagr(alt),
            "ntsd_cagr_with_veasim": M.cagr(ours)}


# --------------------------------------------------------------------------
# 3. live slippage: real NTSD vs an ETF-built synthetic
# --------------------------------------------------------------------------
def live():
    px = D.load_prices(["NTSD", "SPY", "EFA", "VEA"], start="2026-01-01")
    px = px.dropna(subset=["NTSD"])
    r = px.pct_change().iloc[1:]
    cal = r.index
    bill = D.load_us_curve()["us_3m"]
    bill = bill.reindex(bill.index.union(cal)).ffill(limit=7).reindex(cal)
    rf = bill * year_fraction(cal)
    gap = LV.gap_on(cal, rf, "bill_3m")

    out, synths = {}, {}
    for intl in ("EFA", "VEA"):
        s = simulate_ntsd(r["SPY"], r[intl], rf,
                          us_er=ER["SPY"], intl_er=ER[intl], gap=gap)["ret"]
        synths[intl] = s
        st = gap_stats(r["NTSD"], s)
        blend = W_US * r["SPY"] + W_INTL * r[intl]
        st["gap_vs_underlying"] = ols(r["NTSD"] - s, pd.DataFrame({"blend": blend}))
        st["beta_fit"] = ols(r["NTSD"], pd.DataFrame({"us": r["SPY"], "intl": r[intl]}))
        out[intl] = st

    live_df = pd.DataFrame({"ntsd_real": r["NTSD"], "synth_efa": synths["EFA"],
                            "synth_vea": synths["VEA"], "rf": rf})
    live_df.index.name = "date"
    live_df.to_csv(os.path.join(OUTDIR, "ntsd_live_vs_synthetic.csv"))
    out["window"] = [str(cal[0].date()), str(cal[-1].date())]
    return out


# --------------------------------------------------------------------------
def main():
    pd.set_option("display.width", 200)
    panel, tbl, decomp, gap_fit, gap, sens, reset = historical()
    print(f"[hist] {panel.index[0].date()} -> {panel.index[-1].date()}  n={len(panel):,}")
    print(f"       weight drift: us {panel['w_us'].min():.3f}..{panel['w_us'].max():.3f}"
          f"  fut {panel['w_fut'].min():.3f}..{panel['w_fut'].max():.3f}\n")
    print(M.fmt_table(tbl))

    c = decomp["coef"]
    print(f"\n[NTSDSIM decomposition]  R2={decomp['r2']:.4f}  n={decomp['n']:,}")
    print(f"   us {c['us']:.3f}   intl {c['intl']:.3f}   rf {c['rf']:.3f}   "
          f"const {c['const'] * 252 * 100:+.2f}%/yr")
    g = gap_fit["coef"]
    print(f"[testfolio - ours (cost-free)]  mean {gap.mean() * 252 * 100:+.2f}%/yr   "
          f"TE {gap.std() * np.sqrt(252) * 100:.2f}%   "
          f"fit: const {g['const'] * 252 * 100:+.2f}%/yr, rf slope {g['rf']:+.3f}")

    print(f"[daily reset vs quarterly drift]  {reset['cagr_daily_reset'] * 100:.2f}% vs "
          f"{reset['cagr_drift'] * 100:.2f}%   rolling 5y gap "
          f"{reset['rolling5y_gap_min'] * 100:+.2f}..{reset['rolling5y_gap_max'] * 100:+.2f}pp")

    print("\n[spread sensitivity, 1970 -> 2026-04]")
    for _, s in sens.iterrows():
        print(f"   spread {s['spread'] * 100:4.2f}%   CAGR {s['CAGR'] * 100:6.2f}%   "
              f"vol {s['vol'] * 100:5.2f}%   maxDD {s['MaxDD'] * 100:6.2f}%")

    sc = source_check(panel)
    print(f"\n[FF Developed ex US vs VEASIM]  {sc['window'][0]} -> {sc['window'][1]}")
    print(f"   corr daily {sc['corr_daily']:.3f}  monthly {sc['corr_monthly']:.3f}   "
          f"CAGR ff {sc['cagr_ff_exus'] * 100:.2f}%  veasim {sc['cagr_veasim'] * 100:.2f}%")
    print(f"   NTSD synthetic CAGR: with FF ex-US {sc['ntsd_cagr_with_ff_exus'] * 100:.2f}%"
          f"  with VEASIM {sc['ntsd_cagr_with_veasim'] * 100:.2f}%")

    lv = live()
    print(f"\n[live NTSD vs synthetic]  {lv['window'][0]} -> {lv['window'][1]}")
    for k in ("EFA", "VEA"):
        s = lv[k]
        b = s["beta_fit"]["coef"]
        print(f"   SPY+{k}: n={s['n_days']}  cum real {s['cum_real'] * 100:+.2f}%  "
              f"synth {s['cum_synth'] * 100:+.2f}%   gap {s['mean_gap_ann'] * 100:+.2f}%/yr "
              f"(se {s['mean_gap_ann_se'] * 100:.2f})   TE {s['tracking_error_ann'] * 100:.2f}%   "
              f"corr {s['corr']:.4f}   fit us {b['us']:.2f} intl {b['intl']:.2f}")

    summary = dict(assumptions=dict(TER=TER, TXN=TXN, SPREAD=SPREAD, ER_backout=ER,
                                    weights=[W_US, W_CASH, W_INTL],
                                    rebalance="quarter-end + 5pp drift"),
                   ntsdsim_decomposition=decomp, testfolio_gap_fit=gap_fit,
                   testfolio_gap_mean_ann=float(gap.mean() * 252), daily_reset=reset,
                   source_check=sc, live=lv)
    with open(os.path.join(OUTDIR, "ntsd_results.json"), "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    D.write_manifest("ec_ntsd.py")
    print(f"\nwrote {OUTDIR}")


if __name__ == "__main__":
    main()
