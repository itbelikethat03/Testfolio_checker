"""
PHASE 8 -- choosing the Monte Carlo methodology.

The existing project MC (sv_full_analysis.py, lev25_montecarlo.py,
sv_vs_mkt_analysis.py) is a MOVING-BLOCK BOOTSTRAP -- there is no GARCH and no
regime-switching model anywhere in the codebase (verified by grep). This script
tests whether the block bootstrap is good enough for this experiment by
measuring what each resampling scheme preserves.
"""
import numpy as np
import pandas as pd
import json
import os
from kd_data import load_daily, series_frame, SERIES, OUTDIR, write_manifest

os.makedirs(OUTDIR, exist_ok=True)
df = load_daily()
rng = np.random.default_rng(2024)
OUT = {}


def acf(a, lags):
    a = a - a.mean()
    d = np.dot(a, a)
    return [float(np.dot(a[:-l], a[l:]) / d) for l in lags]


def ljung_box(a, m=20):
    n = len(a)
    r = acf(a, range(1, m + 1))
    q = n * (n + 2) * sum(rr ** 2 / (n - k - 1) for k, rr in enumerate(r))
    return float(q)


def block_sample(a, n_out, block, rng):
    n = len(a)
    nb = int(np.ceil(n_out / block))
    starts = rng.integers(0, n - block + 1, size=nb)
    idx = (starts[:, None] + np.arange(block)[None, :]).ravel()[:n_out]
    return a[idx]


print("=" * 88)
print("PHASE 8 -- WHAT DOES EACH RESAMPLING SCHEME PRESERVE?")
print("=" * 88)
print("Ljung-Box Q(20): on returns (autocorrelation) and on |returns| "
      "(volatility clustering).\n5% critical value for 20 df = 31.4\n")

for key, meta in SERIES.items():
    sub, apy, _years = series_frame(df, key)
    x = sub[meta["exc"]].to_numpy(float)
    n = len(x)
    print(f"--- {key} ---")
    variants = {
        "historical": x,
        "iid bootstrap": x[rng.integers(0, n, n)],
        "block=5": block_sample(x, n, 5, rng),
        "block=20": block_sample(x, n, 20, rng),
        "block=60": block_sample(x, n, 60, rng),
    }
    rowset = []
    print(f"{'variant':<16}{'LB(r)':>10}{'LB(|r|)':>11}{'ac1(|r|)':>10}"
          f"{'ac20(|r|)':>11}{'kurt':>8}{'skew':>8}{'min%':>8}")
    for name, a in variants.items():
        absa = np.abs(a)
        s = pd.Series(a)
        row = dict(variant=name, lb_ret=ljung_box(a), lb_abs=ljung_box(absa),
                   ac1_abs=acf(absa, [1])[0], ac20_abs=acf(absa, [20])[0],
                   kurt=float(s.kurtosis()), skew=float(s.skew()),
                   min_pct=float(a.min() * 100))
        rowset.append(row)
        print(f"{name:<16}{row['lb_ret']:>10.0f}{row['lb_abs']:>11.0f}"
              f"{row['ac1_abs']:>10.3f}{row['ac20_abs']:>11.3f}"
              f"{row['kurt']:>8.1f}{row['skew']:>+8.2f}{row['min_pct']:>8.2f}")
    OUT[key] = rowset
    print()

print("Reading:")
print("  * i.i.d. bootstrap keeps the unconditional fat tails (kurtosis, worst day)")
print("    but DESTROYS volatility clustering: LB(|r|) collapses toward noise.")
print("  * block bootstrap recovers most of the clustering; block=20 (~1 month,")
print("    the default already used by lev25_montecarlo.py) is a reasonable")
print("    choice -- block=60 adds little and cuts the number of distinct blocks.")
print("  * Fat tails and skew are inherited automatically because we resample")
print("    ACTUAL daily returns, so no GARCH-t or regime-switching model is")
print("    needed to generate them. A GARCH model would ADD parametric")
print("    assumptions without adding realism that matters for a")
print("    mean/variance-driven Kelly estimate.")
print("  * What the block bootstrap does NOT reproduce: multi-year valuation")
print("    cycles and regime persistence longer than the block. Both the block")
print("    and the i.i.d. variant are therefore reported side by side.")

with open(rf"{OUTDIR}\phase8_diagnostics.json", "w") as f:
    json.dump(OUT, f, indent=2)
print(f"\nWrote {OUTDIR}\\phase8_diagnostics.json")
write_manifest("kd_phase8_diag.py")
