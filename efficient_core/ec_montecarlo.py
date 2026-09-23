"""
ec_montecarlo.py -- forward-looking distributions for 90/60 versus 100% global
equities, and Table 2 of the brief.

METHOD
------
Stationary BLOCK bootstrap, not an i.i.d. draw and not a fitted normal.

Why blocks: the whole question is about a portfolio whose two legs move
together in some regimes and apart in others, over horizons of decades.  An
i.i.d. bootstrap destroys the persistence of rate cycles -- exactly the thing
that decides whether the bond leg pays -- and a Gaussian model throws away the
fat left tail that 2022 sits in.  Blocks of 12 months (36 months in the
sensitivity) keep runs of bull and bear markets intact.

Why PAIRED draws: 90/60 and 100% equities are simulated on the SAME resampled
history, month for month.  P(90/60 beats All World) is then a genuine paired
probability rather than a comparison of two independently drawn distributions,
which would badly overstate the dispersion of the difference.

TWO SOURCE SAMPLES, deliberately
--------------------------------
  A. Global 1990-2026 monthly, from the reconstruction.  Matches the actual
     product, but its bond history is dominated by a 30-year bull market in
     bonds and therefore flatters the bond leg.
  B. US 1928-2025 annual, from Damodaran.  Only 98 observations and US-only,
     but it contains the 1940s, the 1950-1981 rate rise and a real stagflation.

Reporting both is the point.  If the two disagree, the answer is
regime-dependent, and that is the finding -- not something to average away.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

import ec_data as D
from common import metrics as M
import ec_portfolios as P

OUT = D.OUT
RNG = np.random.default_rng(20260908)
N_PATHS = 20000
HORIZONS = (10, 20, 30, 40)


# ---------------------------------------------------------------------------
def block_indices(n_obs: int, n_steps: int, n_paths: int, block: int,
                  rng=RNG) -> np.ndarray:
    """Circular block bootstrap index matrix of shape (n_paths, n_steps)."""
    n_blocks = int(np.ceil(n_steps / block))
    starts = rng.integers(0, n_obs, size=(n_paths, n_blocks))
    offs = np.arange(block)
    idx = (starts[:, :, None] + offs[None, None, :]) % n_obs
    return idx.reshape(n_paths, -1)[:, :n_steps]


def _path_stats(rets: np.ndarray, per_year: int) -> dict:
    """rets: (paths, steps) simple returns.  Returns terminal wealth, CAGR,
    realised vol and max drawdown per path."""
    nav = np.cumprod(1.0 + rets, axis=1)
    terminal = nav[:, -1]
    years = rets.shape[1] / per_year
    cagr = terminal ** (1.0 / years) - 1.0
    vol = rets.std(axis=1, ddof=1) * np.sqrt(per_year)
    peak = np.maximum.accumulate(nav, axis=1)
    mdd = (nav / peak - 1.0).min(axis=1)
    return {"terminal": terminal, "cagr": cagr, "vol": vol, "mdd": mdd}


def simulate(sample: pd.DataFrame, per_year: int, block: int, horizon_years: int,
             n_paths: int = N_PATHS, costs: float = P.TOTAL_COSTS,
             bond_premium_shift: float = 0.0, chunk: int = 2500) -> dict:
    """Paired simulation of 90/60 and 100% equities.

    `sample` needs columns eq (equity total return), cash (financing rate) and
    fut (bond futures EXCESS return), each per period.
    `bond_premium_shift` adds an annual amount to the bond leg, used for the
    sensitivity runs.
    """
    eq = sample["eq"].to_numpy()
    cash = sample["cash"].to_numpy()
    fut = sample["fut"].to_numpy() + bond_premium_shift / per_year
    n_obs = len(eq)
    n_steps = horizon_years * per_year

    acc = {k: [] for k in ("t9", "te", "c9", "ce", "v9", "ve", "d9", "de")}
    done = 0
    while done < n_paths:
        k = min(chunk, n_paths - done)
        idx = block_indices(n_obs, n_steps, k, block)
        r9 = (P.W_EQUITY * eq[idx] + P.W_CASH * cash[idx]
              + P.W_BOND * fut[idx] - costs / per_year)
        re = eq[idx]
        s9, se = _path_stats(r9, per_year), _path_stats(re, per_year)
        for a, b in [("t9", s9["terminal"]), ("te", se["terminal"]),
                     ("c9", s9["cagr"]), ("ce", se["cagr"]),
                     ("v9", s9["vol"]), ("ve", se["vol"]),
                     ("d9", s9["mdd"]), ("de", se["mdd"])]:
            acc[a].append(b)
        done += k
    out = {k: np.concatenate(v) for k, v in acc.items()}

    diff = out["c9"] - out["ce"]
    return {
        "horizon": horizon_years,
        "p_outperform": float((out["t9"] > out["te"]).mean()),
        "median_advantage_pp": float(np.median(diff) * 100),
        "p5_advantage_pp": float(np.percentile(diff, 5) * 100),
        "p95_advantage_pp": float(np.percentile(diff, 95) * 100),
        "cagr_9060_median": float(np.median(out["c9"])),
        "cagr_9060_p5": float(np.percentile(out["c9"], 5)),
        "cagr_9060_p95": float(np.percentile(out["c9"], 95)),
        "cagr_eq_median": float(np.median(out["ce"])),
        "cagr_eq_p5": float(np.percentile(out["ce"], 5)),
        "cagr_eq_p95": float(np.percentile(out["ce"], 95)),
        "wealth_9060_median": float(np.median(out["t9"])),
        "wealth_eq_median": float(np.median(out["te"])),
        "wealth_9060_p5": float(np.percentile(out["t9"], 5)),
        "wealth_eq_p5": float(np.percentile(out["te"], 5)),
        "vol_9060_median": float(np.median(out["v9"])),
        "vol_eq_median": float(np.median(out["ve"])),
        "mdd_9060_median": float(np.median(out["d9"])),
        "mdd_eq_median": float(np.median(out["de"])),
        "mdd_9060_p5": float(np.percentile(out["d9"], 5)),
        "mdd_eq_p5": float(np.percentile(out["de"], 5)),
        "p_lose_money_9060": float((out["t9"] < 1.0).mean()),
        "p_lose_money_eq": float((out["te"] < 1.0).mean()),
        "p_cagr_gt_4_9060": float((out["c9"] > 0.04).mean()),
        "p_cagr_gt_4_eq": float((out["ce"] > 0.04).mean()),
        "p_cagr_gt_6_9060": float((out["c9"] > 0.06).mean()),
        "p_cagr_gt_6_eq": float((out["ce"] > 0.06).mean()),
        "p_cagr_gt_8_9060": float((out["c9"] > 0.08).mean()),
        "p_cagr_gt_8_eq": float((out["ce"] > 0.08).mean()),
        "_raw": out,
    }


# ---------------------------------------------------------------------------
def global_monthly_sample() -> pd.DataFrame:
    g = pd.read_csv(rf"{OUT}\panel_global_daily.csv", index_col=0,
                    parse_dates=True)
    m = pd.DataFrame({
        "eq": (1 + g["equity_dm"]).resample("ME").prod() - 1,
        "cash": (1 + g["cash"]).resample("ME").prod() - 1,
        "fut": (1 + g["futures"]).resample("ME").prod() - 1,
    }).dropna()
    return m


def us_annual_sample() -> pd.DataFrame:
    d = D.load_damodaran_annual()
    return pd.DataFrame({"eq": d["stocks"], "cash": d["bills"],
                         "fut": d["bonds"] - d["bills"]}).dropna()


# ---------------------------------------------------------------------------
def run_all():
    print("=" * 92)
    print("MONTE CARLO -- 90/60 versus 100% global equities")
    print("=" * 92)

    gm = global_monthly_sample()
    ua = us_annual_sample()
    print(f"\nSample A: global monthly reconstruction, {gm.index[0].date()}"
          f"..{gm.index[-1].date()}, {len(gm)} months, 12-month blocks")
    print(f"          equity {((1 + gm['eq']).prod() ** (12 / len(gm)) - 1) * 100:5.2f}%/yr, "
          f"bond leg {((1 + gm['fut']).prod() ** (12 / len(gm)) - 1) * 100:+5.2f}%/yr, "
          f"cash {((1 + gm['cash']).prod() ** (12 / len(gm)) - 1) * 100:5.2f}%/yr")
    print(f"Sample B: US annual 1928-2025, {len(ua)} years, 4-year blocks")
    print(f"          equity {((1 + ua['eq']).prod() ** (1 / len(ua)) - 1) * 100:5.2f}%/yr, "
          f"bond leg {((1 + ua['fut']).prod() ** (1 / len(ua)) - 1) * 100:+5.2f}%/yr, "
          f"cash {((1 + ua['cash']).prod() ** (1 / len(ua)) - 1) * 100:5.2f}%/yr")
    print(f"\n{N_PATHS:,} paths per horizon, paired draws, "
          f"costs {P.TOTAL_COSTS * 100:.2f}%/yr charged to the 90/60 leg only.")

    results = {}
    raw_store = {}
    for tag, sample, ppy, block in [("A_global_monthly", gm, 12, 12),
                                    ("B_us_annual", ua, 1, 4)]:
        rows = []
        for h in HORIZONS:
            r = simulate(sample, ppy, block, h)
            raw_store[(tag, h)] = r.pop("_raw")
            rows.append(r)
        results[tag] = pd.DataFrame(rows)

    # ---- Table 2 ----
    print("\n" + "=" * 92)
    print("TABLE 2 -- OUTPERFORMANCE PROBABILITY")
    print("=" * 92)
    for tag, label in [("A_global_monthly",
                        "Sample A -- global 1990-2026 (bond bull market era)"),
                       ("B_us_annual",
                        "Sample B -- US 1928-2025 (includes stagflation)")]:
        df = results[tag]
        print(f"\n{label}")
        print(f"  {'horizon':>8s} {'P(90/60 > All World)':>21s} "
              f"{'median advantage':>18s} {'5th pct':>10s} {'95th pct':>10s}")
        for _, r in df.iterrows():
            print(f"  {int(r['horizon']):6d}yr {r['p_outperform'] * 100:20.1f}% "
                  f"{r['median_advantage_pp']:+17.2f}pp "
                  f"{r['p5_advantage_pp']:+9.2f}pp {r['p95_advantage_pp']:+9.2f}pp")

    # ---- full distributions ----
    print("\n" + "=" * 92)
    print("DISTRIBUTIONS BY HORIZON")
    print("=" * 92)
    for tag, label in [("A_global_monthly", "Sample A (global 1990-2026)"),
                       ("B_us_annual", "Sample B (US 1928-2025)")]:
        df = results[tag]
        print(f"\n{label}")
        print(f"  {'hz':>4s} {'CAGR 90/60 (5/50/95)':>26s} "
              f"{'CAGR equities (5/50/95)':>26s} {'wealth 90/60':>13s} "
              f"{'wealth eq':>10s}")
        for _, r in df.iterrows():
            print(f"  {int(r['horizon']):3d}y "
                  f"{r['cagr_9060_p5'] * 100:7.2f} {r['cagr_9060_median'] * 100:7.2f} "
                  f"{r['cagr_9060_p95'] * 100:7.2f}   "
                  f"{r['cagr_eq_p5'] * 100:7.2f} {r['cagr_eq_median'] * 100:7.2f} "
                  f"{r['cagr_eq_p95'] * 100:7.2f}   "
                  f"{r['wealth_9060_median']:12.2f}x {r['wealth_eq_median']:9.2f}x")
        print(f"\n  {'hz':>4s} {'vol 90/60':>10s} {'vol eq':>8s} "
              f"{'median maxDD 90/60':>19s} {'eq':>8s} "
              f"{'P(lose money) 90/60':>20s} {'eq':>8s}")
        for _, r in df.iterrows():
            print(f"  {int(r['horizon']):3d}y {r['vol_9060_median'] * 100:9.2f}% "
                  f"{r['vol_eq_median'] * 100:7.2f}% "
                  f"{r['mdd_9060_median'] * 100:18.1f}% "
                  f"{r['mdd_eq_median'] * 100:7.1f}% "
                  f"{r['p_lose_money_9060'] * 100:19.2f}% "
                  f"{r['p_lose_money_eq'] * 100:7.2f}%")
        print(f"\n  {'hz':>4s} " + "  ".join(
            f"{'P(CAGR>' + t + ') 9060/eq':>21s}" for t in ["4%", "6%", "8%"]))
        for _, r in df.iterrows():
            print(f"  {int(r['horizon']):3d}y " + "  ".join(
                f"{r[f'p_cagr_gt_{t}_9060'] * 100:9.1f}% /"
                f"{r[f'p_cagr_gt_{t}_eq'] * 100:8.1f}%" for t in ["4", "6", "8"]))

    # ---- sensitivity ----
    print("\n" + "=" * 92)
    print("MONTE CARLO SENSITIVITY -- the result is only as good as the bond leg")
    print("=" * 92)
    print("""
The bond term premium realised in a sample is the single assumption the answer
turns on.  Here the historical bond leg is shifted up and down before
resampling, holding everything else -- including the equity/bond correlation
structure of the blocks -- unchanged.
""")
    base_btp = (1 + gm["fut"]).prod() ** (12 / len(gm)) - 1
    print(f"  Sample A's own bond term premium is {base_btp * 100:+.2f}%/yr.\n")
    print(f"  {'shift':>7s} {'term premium':>13s}  " + "  ".join(
        f"{'P(win) ' + str(h) + 'y':>12s}" for h in HORIZONS))
    sens = []
    for shift in [-0.020, -0.015, -0.010, -0.005, 0.0, 0.005, 0.010]:
        row = {"shift": shift, "term_premium": base_btp + shift}
        cells = []
        for h in HORIZONS:
            r = simulate(gm, 12, 12, h, n_paths=8000, bond_premium_shift=shift)
            r.pop("_raw")
            row[f"p_win_{h}y"] = r["p_outperform"]
            row[f"median_adv_{h}y"] = r["median_advantage_pp"]
            cells.append(f"{r['p_outperform'] * 100:11.1f}%")
        sens.append(row)
        print(f"  {shift * 100:+6.1f}% {(base_btp + shift) * 100:+12.2f}%  "
              + "  ".join(cells))
    sens = pd.DataFrame(sens)

    print(f"\n  {'shift':>7s} {'term premium':>13s}  " + "  ".join(
        f"{'median adv ' + str(h) + 'y':>16s}" for h in HORIZONS))
    for _, r in sens.iterrows():
        print(f"  {r['shift'] * 100:+6.1f}% {r['term_premium'] * 100:+12.2f}%  "
              + "  ".join(f"{r[f'median_adv_{h}y']:+13.2f}pp" for h in HORIZONS))

    print("\n  The probability of winning crosses 50% at roughly the break-even")
    print("  term premium derived analytically in ec_analysis.py section 4b.")
    print("  Below that the structure is a losing bet on expected return, and")
    print("  the case for it has to rest entirely on risk reduction.")

    # ---- persist ----
    for tag, df in results.items():
        df.to_csv(rf"{OUT}\montecarlo_{tag}.csv", index=False)
    sens.to_csv(rf"{OUT}\montecarlo_sensitivity.csv", index=False)
    np.savez_compressed(
        rf"{OUT}\montecarlo_paths.npz",
        **{f"{tag}_{h}_{k}": raw_store[(tag, h)][k]
           for (tag, h) in raw_store for k in ("t9", "te", "c9", "ce", "d9", "de")})
    with open(rf"{OUT}\montecarlo_summary.json", "w") as fh:
        json.dump({t: df.to_dict("records") for t, df in results.items()},
                  fh, indent=2)
    D.write_manifest("ec_montecarlo.py")
    print(f"\nwrote montecarlo_*.csv / .npz / .json to {OUT}")
    return results, sens


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    run_all()
