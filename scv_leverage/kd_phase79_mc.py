"""
PHASE 7 + 9 -- Monte Carlo over the "X best days removed" counterfactual.

Question: if the X strongest historical days had never occurred, how would
different multiples of Kelly have performed over a 25-year future?

Design
------
DGP        : moving-block bootstrap (block = 20 trading days, the default
             already used by lev25_montecarlo.py) drawn from the REDUCED daily
             series with the X best days deleted. (x_t, rf_t) are resampled
             with the SAME index so the historical rate/return pairing survives.
Horizon    : 25 years = round(25 * apy) trading days, apy = the sample's own
             262.78 obs/yr, so a simulated f=1 path is directly comparable with
             the historical CAGR (Phase 11 validation).
Portfolio  : W_{t+1}/W_t = 1 + rf_t + f*x_t - cost, floored at 0. The main
             run borrows at the T-bill rate (cost = 0); at X in (0, 50) the
             futures / broker / letf presets of common/leverage.py are run on
             the same draws as schemes block20_<preset>; they borrow at fed
             funds (the day's gap over the bill) + the preset's spread.
Sizing     : two regimes --
             "full"     f = c * (baseline X=0 Kelly)   -> investor who sized on
                        the full history and then lives in the stressed world
             "stressed" f = c * (Kelly of the X-removed sample) -> investor who
                        correctly re-estimated Kelly
             plus fixed 1.0x and 2.0x benchmarks.
Robustness : the same grid re-run with an i.i.d. bootstrap and with block=60.
"""
import numpy as np
import pandas as pd
import os
import time
from kd_data import load_daily, series_frame, SERIES, OUTDIR, write_manifest
from kd_kelly import kelly_emp
from common import leverage as LV

os.makedirs(OUTDIR, exist_ok=True)
df = load_daily()

N_SIMS = 20_000
N_YEARS = 25
CHUNK = 2_000
SEED = 4242
FRACS = [0.25, 0.50, 0.75, 1.00, 1.25, 1.50]
X_MC = [0, 10, 50, 200]
MAIN_BLOCK = 20
COST_PRESETS = ["futures", "broker", "letf"]      # common/leverage.py
SERIES_ORDER = {"mkt": 0, "scv": 1}
SCHEME_ORDER = {"block20": 0, "iid": 1, "block60": 2}
# Cost schemes reuse the block20 seed, so they re-score the SAME paths.
SCHEME_SEED = dict(SCHEME_ORDER, **{f"block20_{p}": 0 for p in COST_PRESETS})

print(f"MC: {N_SIMS:,} paths x {N_YEARS}y per series "
      f"(horizon in days is set from each series' own obs/yr)")


def block_idx(n_obs, n_sims, n_days, block, rng):
    if block <= 1:
        return rng.integers(0, n_obs, size=(n_sims, n_days), dtype=np.int32)
    nb = int(np.ceil(n_days / block))
    starts = rng.integers(0, n_obs - block + 1, size=(n_sims, nb), dtype=np.int32)
    off = np.arange(block, dtype=np.int32)
    return (starts[:, :, None] + off[None, None, :]).reshape(n_sims, -1)[:, :n_days]


def run_config(x_red, rf_red, levels, block, seed, apy, H, fin="frictionless",
               gap_red=None):
    """levels: list of (label, f). Returns dict label -> metrics arrays.

    `apy` and `H` are per-series: the two series may sit on different calendars,
    so a 25-year horizon is a different number of trading days for each.
    `fin` is a common/leverage.py financing preset; `gap_red` the per-day
    fed-funds-minus-bill gap, resampled with the same index as the returns."""
    n_obs = len(x_red)
    rng = np.random.default_rng(seed)
    fin = LV.get(fin)
    acc = {lab: dict(tw=np.empty(N_SIMS), dd=np.empty(N_SIMS),
                     vol=np.empty(N_SIMS), rfw=np.empty(N_SIMS)) for lab, _ in levels}
    for lo in range(0, N_SIMS, CHUNK):
        hi = min(N_SIMS, lo + CHUNK)
        idx = block_idx(n_obs, hi - lo, H, block, rng)
        xb = x_red[idx].astype(np.float32)
        rb = rf_red[idx].astype(np.float32)
        gb = (gap_red[idx].astype(np.float32)
              if fin.over_fed_funds and gap_red is not None else np.float32(0.0))
        rf_wealth = np.prod(1.0 + rb, axis=1, dtype=np.float64)
        for lab, f in levels:
            ret = rb + f * xb
            if fin.name != "frictionless":
                ret = ret - (np.float32(max(f - 1.0, 0.0)) * (gb + np.float32(fin.spread / apy))
                             + np.float32(fin.ter / apy))
            fac = np.maximum(1.0 + ret, 0.0)
            nav = np.cumprod(fac, axis=1, dtype=np.float64)
            peak = np.maximum.accumulate(nav, axis=1)
            acc[lab]["tw"][lo:hi] = nav[:, -1]
            acc[lab]["dd"][lo:hi] = (nav / peak - 1.0).min(axis=1)
            acc[lab]["vol"][lo:hi] = ret.std(axis=1) * np.sqrt(apy)
            acc[lab]["rfw"][lo:hi] = rf_wealth
            del ret, fac, nav, peak
        del xb, rb, idx
    return acc


def metrics(a):
    tw, dd, vol, rfw = a["tw"], a["dd"], a["vol"], a["rfw"]
    cagr = np.where(tw > 0, tw ** (1.0 / N_YEARS) - 1.0, -1.0)
    q = lambda arr, p: float(np.percentile(arr, p))
    return dict(
        cagr_median=float(np.median(cagr)), cagr_mean=float(cagr.mean()),
        cagr_p1=q(cagr, 1), cagr_p5=q(cagr, 5), cagr_p25=q(cagr, 25),
        cagr_p75=q(cagr, 75), cagr_p95=q(cagr, 95),
        ann_vol_median=float(np.median(vol)),
        mdd_median=float(np.median(dd)), mdd_p5=q(dd, 5), mdd_mean=float(dd.mean()),
        tw_median=float(np.median(tw)), tw_p1=q(tw, 1), tw_p5=q(tw, 5),
        tw_p25=q(tw, 25), tw_p75=q(tw, 75), tw_p95=q(tw, 95),
        tw_mean=float(tw.mean()),
        p_lose_money=float((tw < 1.0).mean()),
        p_below_tbills=float((tw < rfw).mean()),
        p_dd_50=float((dd <= -0.50).mean()),
        p_dd_90=float((dd <= -0.90).mean()),
        p_ruin_99=float((tw < 0.01).mean()),
    )


rows = []
tw_store = {}
t0 = time.time()

for key, meta in SERIES.items():
    frame, apy, _years = series_frame(df, key, with_gap=True)
    H = int(round(N_YEARS * apy))
    print(f"\n[{key}] n={len(frame):,}  apy={apy:.2f}  horizon={H:,} days")
    total = frame[meta["total"]].to_numpy(float)
    x_all = frame[meta["exc"]].to_numpy(float)
    rf_all = frame["rf"].to_numpy(float)
    gap_all = frame["gap"].to_numpy(float)
    order_best = np.argsort(-total, kind="stable")

    # baseline Kelly, estimated on the untouched sample
    f_base = kelly_emp(x_all, rf_all)

    for X in X_MC:
        keep = np.ones(len(frame), bool)
        keep[order_best[:X]] = False
        x_red, rf_red, gap_red = x_all[keep], rf_all[keep], gap_all[keep]
        f_stressed = kelly_emp(x_red, rf_red)

        levels = []
        for c in FRACS:
            levels.append((f"full_{c:.2f}", c * f_base))
        for c in FRACS:
            levels.append((f"stressed_{c:.2f}", c * f_stressed))
        levels += [("fixed_1.0x", 1.0), ("fixed_2.0x", 2.0)]

        schemes = [("block20", MAIN_BLOCK, "frictionless")]
        if X in (0, 50):
            schemes += [("iid", 1, "frictionless"), ("block60", 60, "frictionless")]
            schemes += [(f"block20_{p}", MAIN_BLOCK, p) for p in COST_PRESETS]

        for sname, blk, fin in schemes:
            # deterministic per-config seed (Python's str hash is randomised,
            # so it must NOT be used here -- reproducibility requirement)
            cfg_seed = SEED + 1000 * SERIES_ORDER[key] + 10 * X + SCHEME_SEED[sname]
            acc = run_config(x_red, rf_red, levels, blk, seed=cfg_seed,
                             apy=apy, H=H, fin=fin, gap_red=gap_red)
            for lab, f in levels:
                m = metrics(acc[lab])
                m.update(series=key, X=X, scheme=sname, level=lab,
                         regime=lab.split("_")[0], frac=float(lab.split("_")[1].rstrip("x"))
                         if lab.startswith(("full", "stressed")) else np.nan,
                         f_used=f, f_base=f_base, f_stressed=f_stressed)
                rows.append(m)
                if sname == "block20" and lab in ("full_1.00", "full_0.50",
                                                  "stressed_1.00", "fixed_1.0x"):
                    tw_store[(key, X, lab)] = acc[lab]["tw"].astype(np.float32)
            print(f"  {key} X={X:<4} {sname:<13} f_base={f_base:.2f} "
                  f"f_stressed={f_stressed:.2f}  [{time.time()-t0:.0f}s]")

res = pd.DataFrame(rows)
front = ["series", "X", "scheme", "regime", "frac", "level", "f_used",
         "f_base", "f_stressed"]
res = res[front + [c for c in res.columns if c not in front]]
res.to_csv(rf"{OUTDIR}\phase79_montecarlo.csv", index=False)
np.savez_compressed(rf"{OUTDIR}\phase79_terminal_wealth.npz",
                    **{f"{k[0]}|{k[1]}|{k[2]}": v for k, v in tw_store.items()})
write_manifest("kd_phase79_mc.py")

# ------------------------------------------------------------------ report --
pd.set_option("display.width", 220, "display.max_columns", 60)
lab = {"mkt": "Broad market", "scv": "Small-cap value"}
main = res[res.scheme == "block20"]

print("\n" + "=" * 118)
print("PHASE 9 -- MONTE CARLO, 25-YEAR PATHS, block-20 bootstrap "
      f"({N_SIMS:,} sims, seed {SEED})")
print("=" * 118)
for key in SERIES:
    for regime in ["full", "stressed"]:
        print(f"\n### {lab[key]} -- leverage sized on the "
              f"{'FULL history (not re-estimated)' if regime=='full' else 'STRESSED sample (re-estimated)'}")
        print(f"{'X':>5}{'frac':>7}{'f':>7}{'medCAGR':>9}{'p5CAGR':>9}{'medTW':>10}"
              f"{'p5TW':>9}{'p1TW':>9}{'medMDD':>9}{'P(loss)':>9}{'P(<Tbill)':>10}"
              f"{'P(DD<-50)':>10}{'P(DD<-90)':>10}{'P(ruin)':>9}")
        for X in X_MC:
            for c in FRACS:
                r = main[(main.series == key) & (main.X == X) &
                         (main.level == f"{regime}_{c:.2f}")].iloc[0]
                print(f"{X:>5}{c:>7.2f}{r['f_used']:>7.2f}"
                      f"{r['cagr_median']*100:>8.2f}%{r['cagr_p5']*100:>8.2f}%"
                      f"{r['tw_median']:>10.1f}{r['tw_p5']:>9.2f}{r['tw_p1']:>9.2f}"
                      f"{r['mdd_median']*100:>8.1f}%{r['p_lose_money']*100:>8.1f}%"
                      f"{r['p_below_tbills']*100:>9.1f}%{r['p_dd_50']*100:>9.1f}%"
                      f"{r['p_dd_90']*100:>9.1f}%{r['p_ruin_99']*100:>8.2f}%")

print(f"\nWrote {OUTDIR}\\phase79_montecarlo.csv  ({len(res)} rows) "
      f"and phase79_terminal_wealth.npz   total {time.time()-t0:.0f}s")
