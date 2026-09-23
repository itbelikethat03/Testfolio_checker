"""
PHASE 12 support -- three context calculations the headline result needs.

(a) HOW BIG IS THE BEST-DAY EFFECT COMPARED WITH ORDINARY ESTIMATION ERROR?
    f* = mu/sigma^2 is a ratio dominated by mu, and mu is the hardest moment to
    estimate. Delta method (holding sigma^2 fixed):
        Var(f*) ~= Var(mu_hat)/sigma^4 = (sigma^2/n)/sigma^4 = 1/(n*sigma^2)
    so SE(f*) = 1/sqrt(n * sigma_per_period^2), which is frequency-invariant.
    A moving-block bootstrap SE is computed alongside it because daily returns
    are not i.i.d.

(b) HOW MUCH OF COMPOUNDED GROWTH CAME FROM THE BEST DAYS?
    Total growth is additive in log space, so the share is exact:
        share(X) = sum of log(1+r) over the X best days / sum over all days.

(c) IS f* EVEN STABLE ACROSS ERAS? Split-sample and 25-year-block estimates.
"""
import numpy as np
import pandas as pd
import json
import os
from kd_data import load_daily, series_frame, SERIES, OUTDIR, write_manifest
from kd_kelly import kelly_emp, kelly_gauss

df = load_daily()
OUT = {}
lab = {"mkt": "Broad market", "scv": "Small-cap value"}
X_VALUES = [1, 5, 10, 20, 50, 100, 200, 500]

print("=" * 88)
print("(a) ESTIMATION ERROR IN THE KELLY ESTIMATE ITSELF")
print("=" * 88)
rng = np.random.default_rng(31337)
rem = pd.read_csv(rf"{OUTDIR}\phase346_removal.csv")
for key, meta in SERIES.items():
    frame, apy, years = series_frame(df, key)
    n = len(frame)
    x = frame[meta["exc"]].to_numpy(float)
    f_hat = kelly_gauss(x)
    se_analytic = 1.0 / np.sqrt(n * np.var(x))

    # moving-block bootstrap SE of f* (block = 20 trading days)
    B, BLK = 2000, 20
    nb = int(np.ceil(n / BLK))
    fs = np.empty(B)
    for b in range(B):
        st = rng.integers(0, n - BLK + 1, size=nb)
        idx = (st[:, None] + np.arange(BLK)[None, :]).ravel()[:n]
        xb = x[idx]
        fs[b] = xb.mean() / xb.var()
    se_boot = fs.std(ddof=1)

    sub = rem[(rem.series == key) & (rem["mode"] == "best")].set_index("X")
    print(f"\n{lab[key]}: f* = {f_hat:.2f}x")
    print(f"  analytic SE(f*) = 1/sqrt(n*sigma^2) = {se_analytic:.3f}")
    print(f"  block-bootstrap SE(f*)              = {se_boot:.3f}  "
          f"(B={B}, block={BLK}d)")
    print(f"  => 95% CI on f* (bootstrap): {f_hat-1.96*se_boot:.2f}x to "
          f"{f_hat+1.96*se_boot:.2f}x")
    print(f"  {'X best removed':<18}{'drop in f*':>12}{'= how many bootstrap SEs':>26}")
    for X in X_VALUES:
        d = f_hat - sub.loc[X, "kelly_gauss"]
        print(f"  {X:<18}{d:>12.2f}{d/se_boot:>26.2f}")
    OUT.setdefault("estimation_error", {})[key] = dict(
        f_hat=float(f_hat), se_analytic=float(se_analytic), se_boot=float(se_boot),
        ci_lo=float(f_hat - 1.96 * se_boot), ci_hi=float(f_hat + 1.96 * se_boot),
        drops={str(X): float(f_hat - sub.loc[X, "kelly_gauss"]) for X in X_VALUES},
        drops_in_se={str(X): float((f_hat - sub.loc[X, "kelly_gauss"]) / se_boot)
                     for X in X_VALUES})

print("\n" + "=" * 88)
print("(b) SHARE OF TOTAL COMPOUNDED GROWTH FROM THE BEST DAYS")
print("=" * 88)
for key, meta in SERIES.items():
    frame, apy, years = series_frame(df, key)
    n = len(frame)
    tot = frame[meta["total"]].to_numpy(float)
    lg = np.log1p(tot)
    total_log = lg.sum()
    order = np.argsort(-tot, kind="stable")
    print(f"\n{lab[key]}: $1 -> ${np.exp(total_log):,.0f} over {years:.1f} years "
          f"(CAGR {np.expm1(total_log/years)*100:.2f}%)")
    print(f"  {'X best days':<14}{'% of trading days':>19}{'share of log growth':>21}"
          f"{'CAGR without them':>20}{'$1 grows to':>16}")
    shares = {}
    for X in X_VALUES:
        share = lg[order[:X]].sum() / total_log
        keep_log = total_log - lg[order[:X]].sum()
        cagr_wo = np.exp(keep_log / (n - X) * apy) - 1
        grows = np.exp(keep_log / (n - X) * apy * years)
        shares[str(X)] = float(share)
        print(f"  {X:<14}{X/n*100:>18.3f}%{share*100:>20.1f}%"
              f"{cagr_wo*100:>19.2f}%{grows:>16,.0f}")
    OUT.setdefault("growth_share", {})[key] = shares

print("\n" + "=" * 88)
print("(c) IS f* STABLE ACROSS ERAS?")
print("=" * 88)
for key, meta in SERIES.items():
    frame, apy, years = series_frame(df, key)
    x = frame[meta["exc"]].to_numpy(float)
    rf = frame["rf"].to_numpy(float)
    print(f"\n{lab[key]}:")
    halves = [("1926-07 to 1976-06", frame.index < "1976-07-01"),
              ("1976-07 to 2026-04", frame.index >= "1976-07-01")]
    for name, m in halves:
        print(f"  {name}: f*_gauss={kelly_gauss(x[m]):5.2f}x  "
              f"f*_emp={kelly_emp(x[m], rf[m]):5.2f}x  (n={m.sum():,})")
    print("  25-year blocks:")
    blocks = []
    for y0 in range(1926, 2026, 25):
        m = (frame.index.year >= y0) & (frame.index.year < y0 + 25)
        if m.sum() < 1000:
            continue
        fg, fe = kelly_gauss(x[m]), kelly_emp(x[m], rf[m])
        blocks.append(dict(era=f"{y0}-{y0+24}", n=int(m.sum()),
                           f_gauss=float(fg), f_emp=float(fe)))
        print(f"    {y0}-{y0+24}: f*_gauss={fg:5.2f}x  f*_emp={fe:5.2f}x  (n={m.sum():,})")
    OUT.setdefault("era_stability", {})[key] = blocks

with open(rf"{OUTDIR}\phase12_context.json", "w") as f:
    json.dump(OUT, f, indent=2)
print(f"\nWrote {OUTDIR}\\phase12_context.json")
write_manifest("kd_phase12_context.py")
