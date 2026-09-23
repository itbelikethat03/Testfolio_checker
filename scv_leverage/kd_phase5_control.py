"""
PHASE 5 -- random-day removal control.

For each X we remove X RANDOMLY chosen days B times and rebuild the Kelly
estimate, then ask where the "remove the X best days" result sits inside that
null distribution. This separates "Kelly is sensitive to extreme positive
observations" from "Kelly is just noisy when you drop 200 observations".

Both the treatment and the control are scored on the SAME discrete f-grid so
the comparison is exact (no optimiser-tolerance mismatch).

Speed trick: log(1 + rf_t + f*x_t) is precomputed once as an (n x n_f) matrix.
The mean over any subset is then (column_total - sum of the removed rows) / m,
so one replicate costs O(X * n_f) instead of O(n * n_f).
"""
import numpy as np
import pandas as pd
import os
from kd_data import load_daily, series_frame, SERIES, OUTDIR, write_manifest

os.makedirs(OUTDIR, exist_ok=True)
df = load_daily()

X_VALUES = [1, 5, 10, 20, 50, 100, 200, 500]
B = 2000
SEED = 20260907
F_GRID = np.arange(0.0, 8.0 + 1e-9, 0.01)          # long-only, 0.01 resolution
NF = len(F_GRID)

summary_rows, draw_rows = [], []

for key, meta in SERIES.items():
    # Each series on its own calendar -- see kd_data.series_frame.
    sub, apy, years = series_frame(df, key)
    rf_all = sub["rf"].to_numpy(float)
    n = len(sub)
    x = sub[meta["exc"]].to_numpy(float)
    total = sub[meta["total"]].to_numpy(float)

    # ---- precompute log-growth matrix L and infeasibility mask V ------------
    L = np.empty((n, NF), np.float32)
    V = np.empty((n, NF), np.uint8)
    CH = 64
    for j0 in range(0, NF, CH):
        j1 = min(NF, j0 + CH)
        w = 1.0 + rf_all[:, None] + np.outer(x, F_GRID[j0:j1])
        bad = w <= 0
        V[:, j0:j1] = bad
        L[:, j0:j1] = np.log(np.where(bad, 1.0, w)).astype(np.float32)
    Lsum = L.sum(0, dtype=np.float64)
    Vsum = V.sum(0, dtype=np.int64)

    S1, S2 = x.sum(), (x * x).sum()

    def score(drop_idx):
        """(kelly_emp_on_grid, kelly_gauss) for the sample with drop_idx removed."""
        m = n - len(drop_idx)
        ls = Lsum - L[drop_idx].sum(0, dtype=np.float64)
        vs = Vsum - V[drop_idx].sum(0, dtype=np.int64)
        g = np.where(vs == 0, ls / m, -np.inf)
        ke = float(F_GRID[int(np.argmax(g))])
        s1 = S1 - x[drop_idx].sum()
        s2 = S2 - (x[drop_idx] ** 2).sum()
        mu = s1 / m
        var = s2 / m - mu * mu
        kg = 0.0 if var < 1e-12 else float(mu / var)
        return ke, kg

    order_best = np.argsort(-total, kind="stable")
    base_ke, base_kg = score(np.array([], int))
    print(f"\n[{key}] baseline on grid: kelly_emp={base_ke:.2f}x  kelly_gauss={base_kg:.2f}x")

    rng = np.random.default_rng(SEED)
    for X in X_VALUES:
        treat_ke, treat_kg = score(order_best[:X])

        ke_draws = np.empty(B)
        kg_draws = np.empty(B)
        for b in range(B):
            idx = rng.choice(n, size=X, replace=False)
            ke_draws[b], kg_draws[b] = score(idx)

        # where does the treatment sit inside the null?
        pct_below = float((ke_draws <= treat_ke).mean() * 100)
        z = ((treat_ke - ke_draws.mean()) / ke_draws.std(ddof=1)
             if ke_draws.std(ddof=1) > 0 else np.nan)

        summary_rows.append(dict(
            series=key, X=X,
            base_kelly_emp=base_ke, treat_best_kelly_emp=treat_ke,
            rand_mean=ke_draws.mean(), rand_median=np.median(ke_draws),
            rand_sd=ke_draws.std(ddof=1),
            rand_p5=np.percentile(ke_draws, 5), rand_p95=np.percentile(ke_draws, 95),
            rand_min=ke_draws.min(), rand_max=ke_draws.max(),
            treat_pctile_in_null=pct_below, treat_z=z,
            base_kelly_gauss=base_kg, treat_best_kelly_gauss=treat_kg,
            rand_gauss_mean=kg_draws.mean(), rand_gauss_sd=kg_draws.std(ddof=1),
            rand_gauss_p5=np.percentile(kg_draws, 5),
            rand_gauss_p95=np.percentile(kg_draws, 95),
            B=B, seed=SEED))
        for v_e, v_g in zip(ke_draws, kg_draws):
            draw_rows.append((key, X, v_e, v_g))
        print(f"  X={X:<4} best-removed f*={treat_ke:5.2f}x | random f*: "
              f"mean={ke_draws.mean():5.2f} sd={ke_draws.std(ddof=1):.3f} "
              f"[p5={np.percentile(ke_draws,5):5.2f}, p95={np.percentile(ke_draws,95):5.2f}] "
              f"| treatment percentile={pct_below:5.2f}%  z={z:+7.1f}")

    del L, V

summ = pd.DataFrame(summary_rows)
summ.to_csv(rf"{OUTDIR}\phase5_random_control.csv", index=False)
pd.DataFrame(draw_rows, columns=["series", "X", "kelly_emp", "kelly_gauss"]
             ).to_csv(rf"{OUTDIR}\phase5_random_draws.csv", index=False)

print("\n" + "=" * 96)
print("PHASE 5 -- BEST-DAY REMOVAL vs RANDOM-DAY REMOVAL (empirical Kelly f*)")
print("=" * 96)
lab = {"mkt": "Broad market", "scv": "Small-cap value"}
for key in SERIES:
    s = summ[summ.series == key]
    print(f"\n--- {lab[key]} (baseline f* = {s.iloc[0]['base_kelly_emp']:.2f}x, "
          f"B={B} random draws per X) ---")
    print(f"{'X':>5}{'best-removed':>14}{'random mean':>13}{'random sd':>11}"
          f"{'random p5':>11}{'random p95':>11}{'pctile':>9}{'z':>10}")
    for _, r in s.iterrows():
        print(f"{int(r['X']):>5}{r['treat_best_kelly_emp']:>13.2f}x"
              f"{r['rand_mean']:>13.2f}{r['rand_sd']:>11.3f}{r['rand_p5']:>11.2f}"
              f"{r['rand_p95']:>11.2f}{r['treat_pctile_in_null']:>8.2f}%{r['treat_z']:>10.1f}")

print(f"\nWrote {OUTDIR}\\phase5_random_control.csv (+ raw draws)")
write_manifest("kd_phase5_control.py")
