"""
PHASE 3 (baseline), PHASE 4 (remove X best days), PHASE 6 (best / worst / both).

Counterfactual framing
----------------------
Removing days does not shorten the investment horizon: it defines a MODIFIED
RETURN DISTRIBUTION. All annualised quantities are therefore computed as
per-observation moments scaled by the sample's own observations-per-year
(262.78 here -- above 252 because the NYSE traded Saturdays until 1952).
CAGR = exp(mean(log(1+r)) * apy) - 1, i.e. "the long-run growth rate of an
investor drawing returns from the reduced distribution".

Max drawdown is the drawdown of the retained days re-concatenated in
chronological order, i.e. the realised counterfactual path.
"""
import numpy as np
import pandas as pd
import os
from kd_data import load_daily, series_frame, SERIES, OUTDIR, write_manifest
from kd_kelly import subset_stats

os.makedirs(OUTDIR, exist_ok=True)
df = load_daily()
X_VALUES = [0, 1, 5, 10, 20, 50, 100, 200, 500]

rows = []
removed_log = []

for key, meta in SERIES.items():
    # Each series has its own calendar and therefore its own obs/yr.
    sub, apy, years = series_frame(df, key)
    total_all = sub[meta["total"]].to_numpy(float)
    exc_all = sub[meta["exc"]].to_numpy(float)
    rf_all = sub["rf"].to_numpy(float)
    dates = sub.index
    n = len(sub)
    print(f"\n{key}: apy (obs/yr) = {apy:.3f}   n = {n:,}   years = {years:.2f}")

    # rank by TOTAL daily return (the colloquial "best trading day")
    order_best = np.argsort(-total_all, kind="stable")   # descending
    order_worst = np.argsort(total_all, kind="stable")   # ascending

    for mode in ["best", "worst", "both"]:
        for X in X_VALUES:
            if mode == "best":
                drop = order_best[:X]
            elif mode == "worst":
                drop = order_worst[:X]
            else:
                drop = np.concatenate([order_best[:X], order_worst[:X]])
            keep = np.ones(n, bool)
            keep[drop] = False
            assert keep.sum() == n - len(set(drop.tolist())), "removal count mismatch"

            s = subset_stats(total_all[keep], exc_all[keep], rf_all[keep], apy)
            s.update(series=key, mode=mode, X=X, n_removed=n - keep.sum())
            rows.append(s)

    # log which days were removed (top 20 best / worst) for Phase 11 inspection
    for lbl, order in [("best", order_best), ("worst", order_worst)]:
        for rank, i in enumerate(order[:20], 1):
            removed_log.append(dict(series=key, kind=lbl, rank=rank,
                                    date=str(dates[i].date()),
                                    total_ret=float(total_all[i])))

res = pd.DataFrame(rows)
cols = ["series", "mode", "X", "n_removed", "n_obs", "ann_arith_total", "cagr",
        "ann_vol", "sharpe", "max_dd", "worst_day", "best_day", "skew", "kurt",
        "kelly_gauss", "kelly_quad", "kelly_emp", "kelly_emp_half",
        "kelly_emp_quarter", "fmax_feasible"]
res = res[cols + [c for c in res.columns if c not in cols]]
res.to_csv(rf"{OUTDIR}\phase346_removal.csv", index=False)
pd.DataFrame(removed_log).to_csv(rf"{OUTDIR}\removed_days_log.csv", index=False)

# ---------------------------------------------------------------- reporting --
pd.set_option("display.width", 200, "display.max_columns", 50)

print("\n" + "=" * 92)
print("PHASE 3 -- BASELINE (X = 0, full sample)")
print("=" * 92)
base = res[(res.X == 0) & (res["mode"] == "best")].set_index("series")
lab = {"mkt": "Broad market", "scv": "Small-cap value"}
fmt = [("Observations", "n_obs", "{:,.0f}"),
       ("Ann. arithmetic mean (total)", "ann_arith_total", "{:.2%}"),
       ("Geometric mean / CAGR", "cagr", "{:.2%}"),
       ("Annualised volatility", "ann_vol", "{:.2%}"),
       ("Sharpe ratio", "sharpe", "{:.3f}"),
       ("Max drawdown", "max_dd", "{:.2%}"),
       ("Worst daily return", "worst_day", "{:.2%}"),
       ("Best daily return", "best_day", "{:.2%}"),
       ("Daily skew", "skew", "{:+.2f}"),
       ("Daily excess kurtosis", "kurt", "{:.1f}"),
       ("Full Kelly  (Gaussian mu/s^2)", "kelly_gauss", "{:.2f}x"),
       ("Full Kelly  (quadratic exact)", "kelly_quad", "{:.2f}x"),
       ("Full Kelly  (EMPIRICAL log-opt)", "kelly_emp", "{:.2f}x"),
       ("Half Kelly  (empirical)", "kelly_emp_half", "{:.2f}x"),
       ("Quarter Kelly (empirical)", "kelly_emp_quarter", "{:.2f}x"),
       ("Max feasible f (no wipe-out)", "fmax_feasible", "{:.2f}x")]
print(f"{'Metric':<34}{lab['mkt']:>18}{lab['scv']:>18}")
for name, col, f in fmt:
    print(f"{name:<34}{f.format(base.loc['mkt', col]):>18}{f.format(base.loc['scv', col]):>18}")

print("\n" + "=" * 92)
print("PHASE 4 -- KELLY vs. NUMBER OF BEST DAYS REMOVED")
print("=" * 92)
for key in SERIES:
    sub = res[(res.series == key) & (res["mode"] == "best")].set_index("X")
    print(f"\n--- {lab[key]} ---")
    print(f"{'X':>5}{'CAGR':>9}{'AnnMean':>9}{'Vol':>8}{'Sharpe':>8}{'MaxDD':>9}"
          f"{'Kelly_G':>9}{'Kelly_E':>9}{'%ofbase':>9}")
    k0g, k0e = sub.loc[0, "kelly_gauss"], sub.loc[0, "kelly_emp"]
    for X in X_VALUES:
        r = sub.loc[X]
        print(f"{X:>5}{r['cagr']*100:>8.2f}%{r['ann_arith_total']*100:>8.2f}%"
              f"{r['ann_vol']*100:>7.2f}%{r['sharpe']:>8.3f}{r['max_dd']*100:>8.1f}%"
              f"{r['kelly_gauss']:>8.2f}x{r['kelly_emp']:>8.2f}x"
              f"{r['kelly_emp']/k0e*100:>8.1f}%")

print("\n" + "=" * 92)
print("PHASE 6 -- BEST vs WORST vs BOTH")
print("=" * 92)
for key in SERIES:
    print(f"\n--- {lab[key]} : empirical full Kelly f* ---")
    print(f"{'X':>5}{'remove best':>14}{'remove worst':>14}{'remove both':>14}"
          f"{'|':>3}{'CAGR best':>12}{'CAGR worst':>12}{'CAGR both':>12}")
    for X in X_VALUES:
        g = {m: res[(res.series == key) & (res["mode"] == m) & (res.X == X)].iloc[0]
             for m in ["best", "worst", "both"]}
        print(f"{X:>5}{g['best']['kelly_emp']:>13.2f}x{g['worst']['kelly_emp']:>13.2f}x"
              f"{g['both']['kelly_emp']:>13.2f}x{'|':>3}"
              f"{g['best']['cagr']*100:>11.2f}%{g['worst']['cagr']*100:>11.2f}%"
              f"{g['both']['cagr']*100:>11.2f}%")

print(f"\nWrote {OUTDIR}\\phase346_removal.csv and removed_days_log.csv")
write_manifest("kd_phase346_removal.py")
