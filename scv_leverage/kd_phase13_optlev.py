"""
PHASE 13 -- optimal leverage as a function of X best days removed.

Phase 4 gives the Kelly fraction implied by the reduced DAILY distribution.
This script asks a different, more operational question: over a 25-year horizon,
what leverage do the simulated paths actually reward? Four definitions of
"optimal", all swept on the same fine f-grid and the same bootstrap draws:

  f_kelly   analytic -- argmax of daily E[log(1 + rf + f*x - cost)]   (Phase 4, no MC)
  f_growth  argmax of MEDIAN 25-year CAGR                      (MC)
  f_p5      argmax of 5th-PERCENTILE 25-year CAGR              (MC, robust optimum)
  f_budget  largest f with P(max drawdown <= -50%) <= 25%      (MC, risk budget)

f_kelly and f_growth should agree closely -- that is a validation of both. The
interesting result is how far f_p5 and f_budget sit below them, and how much
more stable they are as X grows.

FINANCING (common/leverage.py). The main sweep borrows at the bill rate
(`frictionless`, the textbook Kelly setting). For X in COST_X the same draws are
re-scored under the `broker` and `letf` presets, which charge the borrowed part
fed funds (the day's gap over the bill, resampled with the same index) plus a
spread (and, for letf, the fund's TER on NAV), so the cost of leverage is
measured on paths that differ in nothing else. Those rows go to
phase13_*_costs.csv; the frictionless files keep their schema.

Paired design: the same bootstrap indices are reused across every f and every
financing preset within a config, so the curves are smooth and the argmax is not
chasing simulation noise.

Each series is simulated on its OWN calendar (`series_frame`), with its own
obs/yr, so a 25-year horizon is the right number of days for each.
"""
import os
import time

import numpy as np
import pandas as pd

from kd_data import OUTDIR, SERIES, load_daily, series_frame, write_manifest  # puts the suite on sys.path
from kd_kelly import kelly_emp
from common import leverage as LV

N_SIMS = 5_000
N_YEARS = 25
CHUNK = 1_000
BLOCK = 20
SEED = 90210
F_GRID = np.round(np.arange(0.1, 4.001, 0.1), 2)
X_VALUES = [0, 5, 10, 20, 50, 100, 200]
COST_X = [0, 20, 100]
COST_PRESETS = ["broker", "letf"]
DD_BUDGET, DD_MAX_PROB = -0.50, 0.25
SERIES_ORDER = {"mkt": 0, "scv": 1}


def block_idx(n_obs, n_sims, n_days, block, rng):
    nb = int(np.ceil(n_days / block))
    starts = rng.integers(0, n_obs - block + 1, size=(n_sims, nb), dtype=np.int32)
    off = np.arange(block, dtype=np.int32)
    return (starts[:, :, None] + off[None, None, :]).reshape(n_sims, -1)[:, :n_days]


def sweep_rows(acc, key, X, fin_name, f_kelly):
    rows = []
    for f in F_GRID:
        tw, dd = acc[f]["tw"], acc[f]["dd"]
        cagr = np.where(tw > 0, tw ** (1.0 / N_YEARS) - 1.0, -1.0)
        rows.append(dict(
            series=key, X=X, financing=fin_name, f=float(f), f_kelly_analytic=f_kelly,
            cagr_median=float(np.median(cagr)),
            cagr_p5=float(np.percentile(cagr, 5)),
            cagr_p25=float(np.percentile(cagr, 25)),
            mean_log_growth=float(np.mean(np.log(np.maximum(tw, 1e-300))) / N_YEARS),
            mdd_median=float(np.median(dd)),
            p_dd_50=float((dd <= -0.50).mean()),
            p_dd_90=float((dd <= -0.90).mean()),
            p_loss=float((tw < 1.0).mean()),
            tw_median=float(np.median(tw))))
    return rows


def optima(res):
    opt = []
    for (key, X, fin), g in res.groupby(["series", "X", "financing"], sort=False):
        g = g.sort_values("f").reset_index(drop=True)
        within = g[g["p_dd_50"] <= DD_MAX_PROB]
        opt.append(dict(
            series=key, X=X, financing=fin,
            f_kelly=g["f_kelly_analytic"].iloc[0],
            f_growth=float(g.loc[g["cagr_median"].idxmax(), "f"]),
            cagr_at_growth=float(g["cagr_median"].max()),
            f_meanlog=float(g.loc[g["mean_log_growth"].idxmax(), "f"]),
            f_p5=float(g.loc[g["cagr_p5"].idxmax(), "f"]),
            cagr_p5_at_p5=float(g["cagr_p5"].max()),
            f_budget=float(within["f"].max()) if len(within) else 0.0,
            cagr_at_budget=float(g.loc[g["f"] == within["f"].max(), "cagr_median"].iloc[0])
            if len(within) else np.nan))
    return pd.DataFrame(opt).sort_values(["series", "financing", "X"])


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    df = load_daily()
    print(f"Sweep: {len(F_GRID)} leverage levels x {len(X_VALUES)} X-values x 2 series; "
          f"financing presets {COST_PRESETS} at X in {COST_X}\n")

    rows = []
    t0 = time.time()
    for key, meta in SERIES.items():
        frame, apy, _ = series_frame(df, key, with_gap=True)
        H = int(round(N_YEARS * apy))
        total = frame[meta["total"]].to_numpy(float)
        x_all = frame[meta["exc"]].to_numpy(float)
        rf_all = frame["rf"].to_numpy(float)
        # Per-day cost of each borrowed unit over rf, per preset: fed-funds gap,
        # (rate_beta - 1) x fed funds, plus spread (common/leverage.py).
        prem_all = {fn: np.broadcast_to(np.asarray(LV.PRESETS[fn].borrow_premium(
            1.0 / apy, frame["gap"].to_numpy(float), frame["ff_acc"].to_numpy(float)), float),
            (len(frame),)).copy() for fn in ["frictionless"] + COST_PRESETS}
        order_best = np.argsort(-total, kind="stable")
        print(f"  [{key}] n={len(frame):,}  apy={apy:.2f}  horizon={H:,} days")

        for X in X_VALUES:
            keep = np.ones(len(frame), bool)
            keep[order_best[:X]] = False
            x_red, rf_red = x_all[keep], rf_all[keep]
            fins = ["frictionless"] + (COST_PRESETS if X in COST_X else [])
            prem_red = {fn: prem_all[fn][keep] for fn in fins}
            fk = {fn: kelly_emp(x_red, rf_red, spread=prem_red[fn]) for fn in fins}

            acc = {fn: {f: dict(tw=np.empty(N_SIMS), dd=np.empty(N_SIMS)) for f in F_GRID}
                   for fn in fins}
            rng = np.random.default_rng(SEED + 1000 * SERIES_ORDER[key] + X)
            for lo in range(0, N_SIMS, CHUNK):
                hi = min(N_SIMS, lo + CHUNK)
                idx = block_idx(len(x_red), hi - lo, H, BLOCK, rng)
                xb = x_red[idx].astype(np.float32)
                rb = rf_red[idx].astype(np.float32)
                pb = {fn: prem_red[fn][idx].astype(np.float32) for fn in fins
                      if fn != "frictionless"}
                for f in F_GRID:
                    base = 1.0 + rb + np.float32(f) * xb
                    for fn in fins:
                        fin = LV.PRESETS[fn]
                        if fn == "frictionless":
                            fac = np.maximum(base, 0.0)
                        else:
                            drag = (np.float32(max(f - 1.0, 0.0)) * pb[fn]
                                    + np.float32(fin.ter / apy))
                            fac = np.maximum(base - drag, 0.0)
                        nav = np.cumprod(fac, axis=1, dtype=np.float64)
                        acc[fn][f]["tw"][lo:hi] = nav[:, -1]
                        acc[fn][f]["dd"][lo:hi] = (nav / np.maximum.accumulate(nav, axis=1)
                                                   - 1).min(axis=1)
                        del fac, nav
                    del base
                del xb, rb, pb, idx

            for fn in fins:
                rows += sweep_rows(acc[fn], key, X, fn, fk[fn])
            print(f"  {key} X={X:<4} f_kelly " + "  ".join(f"{fn}={fk[fn]:5.2f}x" for fn in fins)
                  + f"   [{time.time()-t0:.0f}s]")

    res = pd.DataFrame(rows)
    opt = optima(res)
    fr = res["financing"] == "frictionless"
    res[fr].drop(columns="financing").to_csv(rf"{OUTDIR}\phase13_leverage_sweep.csv", index=False)
    res[~fr].to_csv(rf"{OUTDIR}\phase13_leverage_sweep_costs.csv", index=False)
    ofr = opt["financing"] == "frictionless"
    opt[ofr].drop(columns="financing").to_csv(rf"{OUTDIR}\phase13_optimal_leverage.csv",
                                              index=False)
    opt.to_csv(rf"{OUTDIR}\phase13_optimal_leverage_costs.csv", index=False)
    write_manifest("kd_phase13_optlev.py")

    lab = {"mkt": "Broad market", "scv": SERIES["scv"]["label"]}
    print("\n" + "=" * 110)
    print("PHASE 13 -- OPTIMAL LEVERAGE vs. NUMBER OF BEST DAYS REMOVED")
    print("=" * 110)
    for key in SERIES:
        for fn, s in opt[opt.series == key].groupby("financing", sort=False):
            print(f"\n--- {lab[key]} -- financing: {fn} ---")
            print(f"{'X':>5}{'f_kelly':>10}{'f_growth':>10}{'f_meanlog':>11}{'f_p5':>8}"
                  f"{'f_budget':>10}  |{'medCAGR@growth':>16}{'p5CAGR@p5':>12}{'medCAGR@budget':>16}")
            for _, r in s.iterrows():
                print(f"{int(r['X']):>5}{r['f_kelly']:>9.2f}x{r['f_growth']:>9.2f}x"
                      f"{r['f_meanlog']:>10.2f}x{r['f_p5']:>7.2f}x{r['f_budget']:>9.2f}x  |"
                      f"{r['cagr_at_growth']*100:>15.2f}%{r['cagr_p5_at_p5']*100:>11.2f}%"
                      f"{r['cagr_at_budget']*100:>15.2f}%")

    print(f"\n(f_budget = largest f with P(max drawdown <= {DD_BUDGET*100:.0f}%) <= "
          f"{DD_MAX_PROB*100:.0f}%)")
    print(f"\nWrote {OUTDIR}\\phase13_*.csv   total {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
