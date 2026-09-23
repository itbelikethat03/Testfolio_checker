"""
verify_suite.py -- regression harness for the whole suite.

Recomputes the load-bearing numbers of every study straight from code and the
cached data (no study outputs are read), then compares them with the snapshot
in verify_baseline.json.

    python verify_suite.py              compare against the snapshot
    python verify_suite.py --snapshot   overwrite the snapshot with this run

A pure refactor must leave every number unchanged (tolerance 1e-9). A change
that is meant to move numbers is re-snapshotted deliberately, and the diff this
script prints is the record of what moved.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

SUITE = Path(__file__).resolve().parent
for sub in ("efficient_core", "scv_leverage", "testfolio_check"):
    sys.path.insert(0, str(SUITE / sub))
sys.path.insert(0, str(SUITE))

BASELINE = SUITE / "verify_baseline.json"
TOL = 1e-9


def _stats(prefix: str, r, rf, M) -> dict:
    return {f"{prefix}.cagr": M.cagr(r), f"{prefix}.vol": M.vol(r),
            f"{prefix}.sharpe": M.sharpe(r, rf), f"{prefix}.maxdd": M.max_drawdown(r)}


def efficient_core() -> dict:
    import ec_bonds as B
    from common import metrics as M
    import ec_portfolios as P

    out = {}
    g = P.global_panel()
    for c in ("equity_dm", "cash", "futures", "rec9060", "lev15", "scv_dm"):
        out.update(_stats(f"ec.global.{c}", g[c].dropna(), g["rf"], M))
    u = P.us_panel(start="2018-08-01")
    out.update(_stats("ec.us.rec9060_us", u["rec9060_us"], u["rf"], M))
    cur = B.build_curves()
    for m in (2, 7, 20):
        tr = B.cm_bond_returns(cur, B.CURVE_POINTS["usd"], m)["tr"]
        out[f"ec.bond.usd_{m}y.cagr"] = M.cagr(tr.loc["1990":])
    return out


def ntsd() -> dict:
    import ec_data as D
    from common import metrics as M
    import ec_ntsd as N
    from common import leverage as LV

    ff = D.load_ff_us_daily().loc[N.HIST_START:]
    veasim = N.returns_on(N.load_testfolio("VEASIM"), ff.index)
    r = N.simulate_ntsd(ff["us_total"], veasim, ff["rf"], intl_er=N.ER["VEASIM"],
                        gap=LV.gap_on(ff.index, ff["rf"], "kf_1m"))["ret"]
    return {"ntsd.synth.cagr": M.cagr(r), "ntsd.synth.vol": M.vol(r),
            "ntsd.synth.maxdd": M.max_drawdown(r)}


def kelly() -> dict:
    import kd_data
    import kd_kelly

    out = {}
    df = kd_data.load_daily(verbose=False)
    for key, meta in kd_data.SERIES.items():
        sub, apy, _ = kd_data.series_frame(df, key)
        s = kd_kelly.subset_stats(sub[meta["total"]].to_numpy(float),
                                  sub[meta["exc"]].to_numpy(float),
                                  sub["rf"].to_numpy(float), apy)
        for k in ("cagr", "ann_vol", "sharpe", "max_dd", "kelly_emp"):
            out[f"kd.{key}.{k}"] = s[k]
        out[f"kd.{key}.n"] = float(len(sub))
    return out


def testfolio() -> dict:
    import tf_load
    import tf_metrics as T

    out = {}
    rf = T.french_rf()
    for tic, nav in tf_load.load_all(verbose=False).items():
        m = T.compute(nav, rf=rf)
        for k in ("cagr", "vol", "max_dd", "ulcer", "sharpe__excess_mean",
                  "sortino__mar_rf", "longest_dd__to_recover", "avg_dd__daily_underwater"):
            out[f"tf.{tic}.{k}"] = m[k]
    return out


def collect() -> dict:
    out = {}
    for fn in (efficient_core, ntsd, kelly, testfolio):
        t0 = time.time()
        out.update(fn())
        print(f"  {fn.__name__:<16} {time.time() - t0:5.1f}s")
    return {k: float(v) for k, v in out.items()}


def main() -> None:
    print("verify_suite: recomputing ...")
    now = collect()

    if "--snapshot" in sys.argv or not BASELINE.exists():
        BASELINE.write_text(json.dumps(now, indent=1, sort_keys=True), encoding="utf-8")
        print(f"[snapshot] {len(now)} numbers -> {BASELINE.name}")
        return

    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    moved, missing = [], sorted(set(base) - set(now))
    for k in sorted(set(base) | set(now)):
        a, b = base.get(k), now.get(k)
        if a is None or b is None:
            continue
        if not (np.isclose(a, b, rtol=0, atol=TOL) or (np.isnan(a) and np.isnan(b))):
            moved.append((k, a, b))

    for k, a, b in moved:
        print(f"  MOVED  {k:<46} {a:+.8f} -> {b:+.8f}  ({b - a:+.2e})")
    for k in missing:
        print(f"  GONE   {k}")
    for k in sorted(set(now) - set(base)):
        print(f"  NEW    {k:<46} {now[k]:+.8f}")
    if moved or missing:
        print(f"\n{len(moved)} moved, {len(missing)} gone (tolerance {TOL:g})")
        sys.exit(1)
    print(f"\nALL {len(base)} NUMBERS REPRODUCE (tolerance {TOL:g})")


if __name__ == "__main__":
    main()
