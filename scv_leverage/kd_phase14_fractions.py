"""
PHASE 14 -- fractional Kelly vs best-day removal.

Question: is the risk reduction bought by FRACTIONAL KELLY (Half, Quarter)
comparable to stress-testing Full Kelly by REMOVING the 10, 25 or 100 best days?
Treated as a hypothesis to test, not an equivalence to assume.

The two transformations are kept separate:
  fractional Kelly   r_p = rf + (c * f*) * x      c in {1, 0.5, 0.25}
                     -- scales exposure, keeps the whole history
  best-day removal   drop the X best days (ranked by UNLEVERED total return
                     on the full original sample), keep the rest in
                     chronological order -- changes the distribution, keeps
                     the exposure

PRIMARY SIZING: f* = kelly_emp() estimated ONCE on the original series and
applied unchanged to every dataset, so only the distribution differs between
datasets. f* is therefore in-sample; the walk-forward sensitivity removes that.

ANNUALISATION: removed days are dropped, so every annualised figure is a
per-observation moment scaled by the series' own apy (Phase 4 convention):
CAGR = exp(mean(log(1+r)) * apy) - 1. Final wealth is (1+CAGR)^years over the
identical calendar span, so every scenario starts with $1 on the same date and
ends on the same date. The raw product of the retained days is also reported;
it is the "removed days earned 0%" reading.

SENSITIVITIES (phase14_sensitivity.csv, column `variant`)
  walkforward     f* re-estimated each month-end on the scenario's own retained
                  history up to that date, applied next month; 10-year warm-up,
                  clipped to [0, 4]
  fixed_1936      primary sizing, restricted to the walk-forward trading window
  cash_day        removed days kept on the calendar but earn rf (excess = 0)
  cost_futures    borrowed portion max(f - 1, 0) charged fed funds + 0.30%/yr
  cost_broker     ... fed funds + 1.00%/yr (retail margin loan)
  cost_letf       ... fed funds + the swap spread fitted to SSO/UPRO, plus a 0.91% TER
                  (common/leverage.py presets)
"""
import json
import os
import time

import numpy as np
import pandas as pd

from kd_data import load_daily, series_frame, SERIES, OUTDIR, write_manifest
from kd_kelly import kelly_emp
from common import leverage as LV

os.makedirs(OUTDIR, exist_ok=True)
T0 = time.time()

FRACTIONS = [("full", "Full Kelly", 1.0), ("half", "Half Kelly", 0.5),
             ("quarter", "Quarter Kelly", 0.25)]
X_MAIN = [0, 10, 25, 100]
X_EQUIV = [0, 5, 10, 15, 25, 35, 50, 75, 100, 150, 200, 300, 500]
DD_LEVELS = [-0.20, -0.35, -0.50]
WF_WARMUP_YEARS = 10
WF_CAP = 4.0
COST_PRESETS = ["futures", "broker", "letf"]      # common/leverage.py
HIST_EDGES = np.round(np.arange(-0.20, 0.2001, 0.005), 3)

# Similarity vectors, declared up front. Every metric is z-scaled by its
# standard deviation across the 12 primary scenarios of that series.
SIM_ALL = ["cagr", "ann_vol", "sharpe", "sortino", "max_dd", "calmar",
           "mdd_duration_days", "log_final_wealth"]
SIM_RISK = ["ann_vol", "max_dd", "mdd_duration_days", "worst_month"]
SIM_RETURN = ["cagr", "sharpe", "sortino", "log_final_wealth"]
EQUIV_METRICS = ["cagr", "ann_vol", "sharpe", "sortino", "max_dd", "calmar",
                 "mdd_duration_days", "worst_month", "log_final_wealth"]
DELTA_METRICS = ["cagr", "ann_vol", "sharpe", "sortino", "max_dd", "calmar",
                 "final_wealth", "worst_day", "worst_month", "mdd_duration_days",
                 "mdd_recovery_days", "longest_underwater_days", "pct_days_below_20"]

LAB = {"mkt": "Broad market", "scv": "Small-cap value"}


def sid(frac, X):
    return f"{frac}_x{X}"


def slabel(frac, X):
    name = dict((a, b) for a, b, _ in FRACTIONS).get(frac, "Unlevered 1.00x")
    return f"{name}, " + ("original" if X == 0 else f"-{X} best days")


# ------------------------------------------------------------------ metrics --
def metrics(rp, rf, dates, apy, years):
    """Every Phase 14 statistic for one daily portfolio path.

    rp, rf: retained daily total portfolio return and risk-free rate.
    dates : their real dates (chronological, gaps where days were removed)."""
    rp = np.asarray(rp, float)
    exc = rp - rf
    n = len(rp)
    wiped = bool(np.any(rp <= -1.0))
    lg = np.log1p(np.maximum(rp, -1 + 1e-15))
    cagr = -1.0 if wiped else float(np.expm1(lg.mean() * apy))
    sd_e = exc.std(ddof=1)
    down = np.sqrt(np.mean(np.minimum(exc, 0.0) ** 2)) * np.sqrt(apy)

    # NAV with a $1 starting value, so a first-day loss counts as a drawdown
    nav = np.concatenate([[1.0], np.cumprod(1.0 + rp)])
    d = np.concatenate([[dates[0]], dates])
    peak = np.maximum.accumulate(nav)
    dd = nav / peak - 1.0
    t = int(np.argmin(dd))
    mdd = float(dd[t])
    p = int(np.flatnonzero(dd[:t + 1] >= 0)[-1])
    after = np.flatnonzero(nav[t:] >= peak[t])
    recovered = len(after) > 0
    r = t + int(after[0]) if recovered else len(nav) - 1
    day = np.timedelta64(1, "D")

    # underwater spells
    u = (dd < -1e-12).astype(int)
    edges = np.diff(np.concatenate([[0], u, [0]]))
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    longest, depths = 0.0, []
    for s, e in zip(starts, ends):
        end_date = d[e] if e < len(d) else d[-1]
        longest = max(longest, float((end_date - d[s - 1]) / day))
        depths.append(dd[s:e].min())
    depths = np.array(depths) if depths else np.array([0.0])

    s = pd.Series(rp, index=pd.DatetimeIndex(dates))
    monthly = (1.0 + s).resample("ME").prod(min_count=1).dropna() - 1.0

    q = np.quantile(rp, [0.01, 0.05, 0.5, 0.95, 0.99])
    dm = rp - rp.mean()
    sdp = rp.std()
    out = dict(
        n_obs=n,
        cagr=cagr,
        ann_vol=float(rp.std(ddof=1) * np.sqrt(apy)),
        sharpe=float(exc.mean() / sd_e * np.sqrt(apy)) if sd_e > 0 else np.nan,
        sortino=float(exc.mean() * apy / down) if down > 0 else np.nan,
        max_dd=mdd,
        calmar=float(cagr / abs(mdd)) if mdd < 0 else np.nan,
        final_wealth=float((1.0 + cagr) ** years),
        log_final_wealth=float(np.log1p(cagr) * years) if cagr > -1 else -np.inf,
        final_wealth_raw=float(nav[-1]),
        worst_day=float(rp.min()),
        best_day=float(rp.max()),
        worst_month=float(monthly.min()),
        mdd_peak=str(pd.Timestamp(d[p]).date()),
        mdd_trough=str(pd.Timestamp(d[t]).date()),
        mdd_recovery=str(pd.Timestamp(d[r]).date()) if recovered else None,
        mdd_recovered=recovered,
        mdd_duration_days=float((d[r] - d[p]) / day),
        mdd_recovery_days=float((d[r] - d[t]) / day),
        mdd_duration_tdays=int(r - p),
        mdd_recovery_tdays=int(r - t),
        longest_underwater_days=longest,
        n_dd_20=int((depths <= -0.20).sum()),
        n_dd_35=int((depths <= -0.35).sum()),
        n_dd_50=int((depths <= -0.50).sum()),
        pct_days_below_20=float((dd[1:] < -0.20).mean()),
        q01=float(q[0]), q05=float(q[1]), q50=float(q[2]), q95=float(q[3]), q99=float(q[4]),
        skew=float(np.mean(dm ** 3) / sdp ** 3),
        kurt=float(np.mean(dm ** 4) / sdp ** 4 - 3.0),
        wiped_out=wiped,
    )
    return out, nav[1:], dd[1:]


def keep_mask(n, order, X):
    k = np.ones(n, bool)
    k[order[:X]] = False
    assert k.sum() == n - X, "removal count mismatch"
    return k


# --------------------------------------------------------------- similarity --
def zscaled(rows, cols):
    M = rows[cols].to_numpy(float)
    sd = M.std(axis=0)
    sd[sd == 0] = 1.0
    return (M - M.mean(axis=0)) / sd


def similarity(rows, series, variant):
    """Long-form RMS z-distance between every pair of scenarios."""
    rows = rows.reset_index(drop=True)
    Z = {k: zscaled(rows, c) for k, c in
         [("all", SIM_ALL), ("risk", SIM_RISK), ("return", SIM_RETURN)]}
    out = []
    for i, a in rows.iterrows():
        for j, b in rows.iterrows():
            rec = dict(series=series, variant=variant, from_id=a["scenario"],
                       to_id=b["scenario"], from_frac=a["frac"], from_X=a["X"],
                       to_frac=b["frac"], to_X=b["X"])
            for k, z in Z.items():
                rec[f"dist_{k}"] = float(np.sqrt(np.mean((z[i] - z[j]) ** 2)))
            for m in SIM_ALL + ["worst_month"]:
                rec[f"diff_{m}"] = float(b[m] - a[m])
            out.append(rec)
    return out


def equivalent_x(grid, target, metric):
    """X at which Full Kelly minus X best days matches `target` on `metric`,
    by linear interpolation on the X grid. First crossing; None if none."""
    xs = grid["X"].to_numpy(float)
    ys = grid[metric].to_numpy(float)
    for i in range(len(xs) - 1):
        a, b = ys[i] - target, ys[i + 1] - target
        if a == 0:
            return float(xs[i]), "exact"
        if a * b < 0:
            return float(xs[i] + (xs[i + 1] - xs[i]) * a / (a - b)), "interpolated"
    if ys[-1] == target:
        return float(xs[-1]), "exact"
    lo, hi = np.nanmin(ys), np.nanmax(ys)
    where = "below" if target < lo else "above" if target > hi else "between"
    return None, f"no match in 0-{int(xs[-1])} (target {where} Full -X range)"


# ------------------------------------------------------------- walk-forward --
def walkforward_f(dates, exc, rf, trade_start):
    """Month-end expanding-window f*, applied through the following month.
    Returns the daily f for the trading window and the monthly path."""
    di = pd.DatetimeIndex(dates)
    months = di.to_period("M")
    trade = di >= trade_start
    f_daily = np.full(len(dates), np.nan)
    path = []
    for m in months[trade].unique():
        cut = int(np.searchsorted(dates, np.datetime64(m.start_time)))
        f = min(max(kelly_emp(exc[:cut], rf[:cut]), 0.0), WF_CAP)
        f_daily[(months == m) & trade] = f
        path.append((m.to_timestamp("M"), f))
    return f_daily, path


# ===================================================================== main ==
df = load_daily()
p4 = pd.read_csv(rf"{OUTDIR}\phase346_removal.csv")
p4 = p4[p4["mode"] == "best"]

grid_rows, sens_rows, sim_rows, eqx_rows, share_rows, hist_rows = [], [], [], [], [], []
nearest_rows, paths, checks = [], [], []
summary = dict(fractions={k: c for k, _, c in FRACTIONS}, X_main=X_MAIN, series={})

for key, meta in SERIES.items():
    sub, apy, years = series_frame(df, key, with_gap=True)
    tot = sub[meta["total"]].to_numpy(float)
    exc = sub[meta["exc"]].to_numpy(float)
    rf = sub["rf"].to_numpy(float)
    gap = sub["gap"].to_numpy(float)
    dates = sub.index.to_numpy()
    n = len(sub)
    order = np.argsort(-tot, kind="stable")
    f_star = kelly_emp(exc, rf)
    print(f"\n{LAB[key]}: n={n:,}  apy={apy:.3f}  years={years:.2f}  "
          f"f* (empirical, full sample) = {f_star:.3f}x")

    f4 = p4[(p4.series == key)].set_index("X")
    checks.append(dict(series=key, check="f* equals Phase 4 kelly_emp at X=0",
                       ok=bool(abs(f_star - f4.loc[0, "kelly_emp"]) < 1e-3),
                       got=f_star, want=float(f4.loc[0, "kelly_emp"])))

    levels = [(k, lbl, c * f_star, c) for k, lbl, c in FRACTIONS] + [("unlev", "Unlevered", 1.0, None)]
    month_cols = {}

    # ---- primary: fixed f*, drop convention, the whole X grid
    for X in X_EQUIV:
        k = keep_mask(n, order, X)
        for frac, lbl, f, c in levels:
            rp = rf[k] + f * exc[k]
            m, nav, dd = metrics(rp, rf[k], dates[k], apy, years)
            m.update(series=key, frac=frac, X=X, scenario=sid(frac, X),
                     label=slabel(frac, X), leverage=f, kelly_mult=c)
            grid_rows.append(m)

            if frac == "unlev" and X in f4.index:      # reproduce Phase 4 exactly
                for col, p4col in [("cagr", "cagr"), ("ann_vol", "ann_vol"), ("sharpe", "sharpe")]:
                    checks.append(dict(series=key, check=f"unlevered X={X} {col} equals Phase 4",
                                       ok=bool(abs(m[col] - f4.loc[X, p4col]) < 1e-9),
                                       got=m[col], want=float(f4.loc[X, p4col])))

            if X in X_MAIN and frac != "unlev":
                idx = pd.DatetimeIndex(dates[k])
                month_cols[f"nav_{sid(frac, X)}"] = pd.Series(nav, idx).resample("ME").last()
                month_cols[f"dd_{sid(frac, X)}"] = pd.Series(dd, idx).resample("ME").min()
                h, _ = np.histogram(np.clip(rp, HIST_EDGES[0], HIST_EDGES[-1] - 1e-12), HIST_EDGES)
                for lo, hi, cnt in zip(HIST_EDGES[:-1], HIST_EDGES[1:], h):
                    hist_rows.append(dict(series=key, scenario=sid(frac, X), bin_lo=lo,
                                          bin_hi=hi, share=cnt / len(rp)))

    # ---- share of log wealth creation from the best days, per fraction
    for frac, lbl, f, c in levels:
        rp = rf + f * exc
        lg = np.log1p(rp)
        order_lev = np.argsort(-rp, kind="stable")
        for X in [10, 25, 100]:
            share_rows.append(dict(
                series=key, frac=frac, leverage=f, X=X,
                share_of_log_growth=float(lg[order[:X]].sum() / lg.sum()),
                pct_of_days=X / n,
                overlap_with_levered_best=len(set(order[:X]) & set(order_lev[:X])) / X))

    # ---- sensitivities
    trade_start = pd.Timestamp(dates[0]) + pd.DateOffset(years=WF_WARMUP_YEARS)
    wf_paths = {}
    for X in X_MAIN:
        k = keep_mask(n, order, X)
        d_k, e_k, r_k = dates[k], exc[k], rf[k]
        t0 = time.time()
        f_wf, fpath = walkforward_f(d_k, e_k, r_k, trade_start)
        wf_paths[X] = fpath
        tw = ~np.isnan(f_wf)
        yrs_tw = (pd.Timestamp(d_k[tw][-1]) - pd.Timestamp(d_k[tw][0])).days / 365.25
        print(f"  walk-forward X={X:<3} {len(fpath):,} monthly estimates in {time.time()-t0:,.0f}s")

        for frac, lbl, c in FRACTIONS:
            base = dict(series=key, frac=frac, X=X, scenario=sid(frac, X),
                        label=slabel(frac, X), kelly_mult=c)
            # walk-forward
            f_t = c * f_wf[tw]
            m, _, _ = metrics(r_k[tw] + f_t * e_k[tw], r_k[tw], d_k[tw], apy, yrs_tw)
            m.update(base, variant="walkforward", leverage=float(f_t.mean()),
                     leverage_min=float(f_t.min()), leverage_max=float(f_t.max()))
            sens_rows.append(m)
            # fixed f*, same window
            f = c * f_star
            m, _, _ = metrics(r_k[tw] + f * e_k[tw], r_k[tw], d_k[tw], apy, yrs_tw)
            m.update(base, variant="fixed_1936", leverage=f, leverage_min=f, leverage_max=f)
            sens_rows.append(m)
            # financing costs (common/leverage.py presets)
            for fname in COST_PRESETS:
                drag = LV.PRESETS[fname].cost(f, 1.0 / apy, gap[k])
                m, _, _ = metrics(r_k + f * e_k - drag, r_k, d_k, apy, years)
                m.update(base, variant=f"cost_{fname}", leverage=f,
                         leverage_min=f, leverage_max=f)
                sens_rows.append(m)
            # cash day: removed days stay on the calendar, earn rf
            e_cash = exc.copy()
            e_cash[order[:X]] = 0.0
            m, _, _ = metrics(rf + f * e_cash, rf, dates, apy, years)
            m.update(base, variant="cash_day", leverage=f, leverage_min=f, leverage_max=f)
            sens_rows.append(m)

    # ---- month-end paths for charts and the dashboard
    mc = pd.DataFrame(month_cols)
    for X, fpath in wf_paths.items():
        mc[f"wf_f_x{X}"] = pd.Series(dict(fpath))
    mc.index.name = "date"
    mc.insert(0, "series", key)
    paths.append(mc.reset_index())

    # ---- similarity (primary and walk-forward)
    G = pd.DataFrame([r for r in grid_rows if r["series"] == key])
    P = G[G.X.isin(X_MAIN) & (G.frac != "unlev")]
    sim_rows += similarity(P, key, "primary")
    S = pd.DataFrame([r for r in sens_rows if r["series"] == key and r["variant"] == "walkforward"])
    S["log_final_wealth"] = S["log_final_wealth"].astype(float)
    sim_rows += similarity(S, key, "walkforward")

    # ---- equivalent X, and the per-metric nearest removal scenario
    full = G[G.frac == "full"].sort_values("X")
    for frac in ["half", "quarter"]:
        tgt = G[(G.frac == frac) & (G.X == 0)].iloc[0]
        for mtr in EQUIV_METRICS:
            x_eq, how = equivalent_x(full, tgt[mtr], mtr)
            eqx_rows.append(dict(series=key, frac=frac, metric=mtr, target=float(tgt[mtr]),
                                 full_x0=float(full[mtr].iloc[0]), equivalent_X=x_eq, how=how))
            cands = full[full.X.isin(X_MAIN)]
            gaps = (cands[mtr] - tgt[mtr]).abs()
            j = gaps.idxmin()
            nearest_rows.append(dict(series=key, frac=frac, metric=mtr, target=float(tgt[mtr]),
                                     nearest_X=int(cands.loc[j, "X"]),
                                     nearest_value=float(cands.loc[j, mtr]),
                                     abs_gap=float(gaps.loc[j]),
                                     rel_gap=float(gaps.loc[j] / abs(tgt[mtr])) if tgt[mtr] else np.nan,
                                     **{f"value_full_x{x}": float(cands.set_index("X").loc[x, mtr])
                                        for x in X_MAIN}))

    # ---- identities
    for X in X_MAIN:
        sh = P[P.X == X].set_index("frac")
        checks.append(dict(series=key, check=f"Sharpe invariant across fractions at X={X}",
                           ok=bool(np.ptp(sh["sharpe"]) < 1e-9 and np.ptp(sh["sortino"]) < 1e-9),
                           got=float(np.ptp(sh["sharpe"])), want=0.0))

    summary["series"][key] = dict(label=LAB[key], f_star=f_star, apy=apy, years=years, n=n,
                                  start=str(sub.index[0].date()), end=str(sub.index[-1].date()),
                                  wf_trade_start=str(trade_start.date()))

# ============================================================ assemble / write
grid = pd.DataFrame(grid_rows)
grid["log_final_wealth"] = grid["log_final_wealth"].astype(float)
prim = grid[grid.X.isin(X_MAIN)].copy()
for key in SERIES:
    b = prim[(prim.series == key) & (prim.scenario == "full_x0")].iloc[0]
    msk = prim.series == key
    for mtr in DELTA_METRICS:
        prim.loc[msk, f"d_{mtr}"] = prim.loc[msk, mtr] - b[mtr]
        prim.loc[msk, f"pct_{mtr}"] = (prim.loc[msk, mtr] / b[mtr] - 1.0) if b[mtr] else np.nan

lead = ["series", "frac", "X", "scenario", "label", "kelly_mult", "leverage"]
prim = prim[lead + [c for c in prim.columns if c not in lead]]
grid = grid[lead + [c for c in grid.columns if c not in lead]]
sens = pd.DataFrame(sens_rows)
sens = sens[["variant"] + lead + ["leverage_min", "leverage_max"]
            + [c for c in sens.columns if c not in lead + ["variant", "leverage_min", "leverage_max"]]]

prim.to_csv(rf"{OUTDIR}\phase14_scenarios.csv", index=False)
grid.to_csv(rf"{OUTDIR}\phase14_grid.csv", index=False)
sens.to_csv(rf"{OUTDIR}\phase14_sensitivity.csv", index=False)
pd.DataFrame(sim_rows).to_csv(rf"{OUTDIR}\phase14_similarity.csv", index=False)
pd.DataFrame(eqx_rows).to_csv(rf"{OUTDIR}\phase14_equivalent_x.csv", index=False)
pd.DataFrame(nearest_rows).to_csv(rf"{OUTDIR}\phase14_nearest.csv", index=False)
pd.DataFrame(share_rows).to_csv(rf"{OUTDIR}\phase14_growth_share.csv", index=False)
pd.DataFrame(hist_rows).to_csv(rf"{OUTDIR}\phase14_distribution.csv", index=False)
pd.concat(paths).to_csv(rf"{OUTDIR}\phase14_paths.csv", index=False, float_format="%.6g")

# ---- headline: nearest Full -X by overall distance, for Half and Quarter
sim = pd.DataFrame(sim_rows)
head = {}
for variant in ["primary", "walkforward"]:
    for key in SERIES:
        for frac in ["half", "quarter"]:
            s = sim[(sim.variant == variant) & (sim.series == key) & (sim.from_id == sid(frac, 0))
                    & (sim.to_frac == "full")].set_index("to_X")
            head.setdefault(variant, {}).setdefault(key, {})[frac] = {
                f"dist_{d}": {str(x): float(s.loc[x, f"dist_{d}"]) for x in X_MAIN}
                for d in ["all", "risk", "return"]}
summary["nearest"] = head
summary["checks"] = checks
summary["runtime_s"] = round(time.time() - T0, 1)


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.floating, float)):
        return float(o) if np.isfinite(o) else None
    if isinstance(o, np.integer):
        return int(o)
    return o


with open(rf"{OUTDIR}\phase14_summary.json", "w") as fh:
    json.dump(_clean(summary), fh, indent=2)
write_manifest("kd_phase14_fractions.py")

# ================================================================ reporting ==
pd.set_option("display.width", 220, "display.max_columns", 60)
print("\n" + "=" * 100)
print("PHASE 14 -- FRACTIONAL KELLY x BEST-DAY REMOVAL  (fixed full-sample f*, drop convention)")
print("=" * 100)
for key in SERIES:
    print(f"\n--- {LAB[key]}  (f* = {summary['series'][key]['f_star']:.2f}x) ---")
    print(f"{'scenario':<34}{'lev':>6}{'CAGR':>8}{'Vol':>8}{'Sharpe':>8}{'Sortino':>8}"
          f"{'MaxDD':>8}{'Calmar':>8}{'$1->':>12}{'wMonth':>8}{'DDdur(y)':>9}{'#DD<-50':>8}")
    for _, r in prim[prim.series == key].sort_values(["frac", "X"], key=lambda s: s.map(
            {"full": 0, "half": 1, "quarter": 2}) if s.name == "frac" else s).iterrows():
        print(f"{r['label']:<34}{r['leverage']:>5.2f}x{r['cagr']*100:>7.2f}%{r['ann_vol']*100:>7.1f}%"
              f"{r['sharpe']:>8.3f}{r['sortino']:>8.3f}{r['max_dd']*100:>7.1f}%{r['calmar']:>8.3f}"
              f"{r['final_wealth']:>12,.0f}{r['worst_month']*100:>7.1f}%"
              f"{r['mdd_duration_days']/365.25:>9.1f}{r['n_dd_50']:>8}")

print("\n" + "=" * 100)
print("DISTANCE (RMS z-gap) FROM HALF / QUARTER (original) TO FULL KELLY minus X best days")
print("=" * 100)
for variant in ["primary", "walkforward"]:
    for key in SERIES:
        for frac in ["half", "quarter"]:
            h = head[variant][key][frac]
            line = "  ".join(f"X={x:<3} all {h['dist_all'][str(x)]:.2f} risk {h['dist_risk'][str(x)]:.2f} "
                             f"ret {h['dist_return'][str(x)]:.2f}" for x in X_MAIN)
            print(f"{variant:<12}{LAB[key]:<17}{frac:<8} {line}")

print("\n" + "=" * 100)
print("EQUIVALENT X: best days Full Kelly must lose to match Half / Quarter on each metric")
print("=" * 100)
eq = pd.DataFrame(eqx_rows)
for key in SERIES:
    for frac in ["half", "quarter"]:
        e = eq[(eq.series == key) & (eq.frac == frac)]
        print(f"\n{LAB[key]} / {frac}:")
        for _, r in e.iterrows():
            v = f"{r['equivalent_X']:.0f}" if r["equivalent_X"] is not None and pd.notna(r["equivalent_X"]) else "-"
            print(f"  {r['metric']:<20} X = {v:>5}   {r['how']}")

print("\n" + "=" * 100)
print("SHARE OF TOTAL LOG WEALTH CREATION FROM THE BEST X DAYS")
print("=" * 100)
sh = pd.DataFrame(share_rows)
for key in SERIES:
    t = sh[sh.series == key].pivot(index="frac", columns="X", values="share_of_log_growth")
    print(f"\n{LAB[key]}\n{(t * 100).round(1).to_string()}")

print("\nChecks:")
bad = [c for c in checks if not c["ok"]]
for c in checks:
    print(f"  [{'ok' if c['ok'] else 'FAIL'}] {c['series']}: {c['check']}")
print(f"\nWrote phase14_*.csv / phase14_summary.json to {OUTDIR}  ({time.time()-T0:,.0f}s)")
if bad:
    raise SystemExit(f"{len(bad)} validation check(s) failed")
