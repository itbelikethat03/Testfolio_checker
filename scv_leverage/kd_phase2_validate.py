"""
PHASE 2 + PHASE 11 (part 1): verify the return series before any Kelly work.
Read-only; prints diagnostics and writes nothing except a small JSON.

Every per-series statistic is computed on that series' own calendar
(`series_frame`), because the two series need not share one.
"""
import json
import os

import numpy as np
import pandas as pd

import kd_data
from kd_data import OUTDIR, SERIES, SCV_HAIRCUT, SCV_SOURCE, load_daily, series_frame


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    df = load_daily()
    frames = {k: series_frame(df, k) for k in SERIES}
    OUT = {}

    print("\n" + "=" * 78)
    print("PHASE 2 -- RETURN SERIES DEFINITION CHECKS")
    print("=" * 78)
    for key, (sub, apy, years) in frames.items():
        print(f"{key}: {sub.index.min().date()} -> {sub.index.max().date()}  "
              f"({years:.2f} calendar years, n={len(sub):,}, {apy:.2f} obs/yr)")
    print(f"scv source: {SERIES['scv']['label']}"
          + (f", haircut {SCV_HAIRCUT:.2%}/yr" if SCV_HAIRCUT else ""))

    # --- 1. identity check: total == exc + rf, exactly by construction --------
    for key, (sub, _, _) in frames.items():
        m = SERIES[key]
        assert np.allclose(sub[m["total"]], sub[m["exc"]] + sub["rf"])
    print("\n[OK] mkt_total = mkt_exc + rf   and   scv_exc = scv_total - rf")

    # --- 2. is the SCV series a total or an excess return? ----------------------
    # If it were an excess return it would be near-zero-mean in the 1980s when
    # T-bills yielded 10%+. Compare its mean against RF in a high-rate decade.
    sub = df.loc["1980":"1989"]
    apy_m = frames["mkt"][1]
    print("\n1980-1989 daily means (x100):")
    print(f"  RF        {sub['rf'].mean()*100:.5f}   "
          f"(~{((1+sub['rf']).prod()**(apy_m/len(sub))-1)*100:.2f}%/yr)")
    print(f"  Mkt-RF    {sub['mkt_exc'].mean()*100:.5f}")
    print(f"  SCV       {sub['scv_total'].mean()*100:.5f}")
    print("  -> the SCV mean sits ABOVE Mkt-RF by roughly the T-bill yield,")
    print("     confirming it is a TOTAL return series (not excess).")

    # --- 3. full-sample CAGR, each on its own calendar ---------------------------
    for key, (sub, apy, years) in frames.items():
        col = SERIES[key]["total"]
        nav = (1 + sub[col]).prod()
        print(f"  full-sample CAGR {key:<4} {(nav ** (1 / years) - 1)*100:6.2f}%   "
              f"($1 -> ${nav:,.0f})")

    # --- 3b. SCV cross-check against Ken French's own MONTHLY file --------------
    # The daily and monthly files are built separately by Ken French; if the daily
    # parse is right, daily compounded to month-end must match the monthly file.
    if SCV_SOURCE == "kf" and not SCV_HAIRCUT:
        mo = kf_monthly_small_value()
        if mo is not None:
            s = frames["scv"][0]["scv_total"]
            dm = (1 + s).resample("ME").prod() - 1
            j = mo.index.intersection(dm.index)
            c = float(np.corrcoef(mo[j], dm[j])[0, 1])
            cg = lambda x: (1 + x).prod() ** (12 / len(x)) - 1
            print(f"\n  KF monthly file vs daily compounded ({len(j)} months): "
                  f"corr {c:.5f}   CAGR {cg(mo[j])*100:.2f}% vs {cg(dm[j])*100:.2f}%")
            OUT["kf_monthly_check"] = dict(months=len(j), corr=c,
                                           cagr_monthly_file=float(cg(mo[j])),
                                           cagr_daily_compounded=float(cg(dm[j])))
            assert c > 0.999, "daily SMALL HiBM does not match Ken French's monthly file"

    # --- 4. missing-value / sanity scan -----------------------------------------
    print("\nSanity scan (each series on its own calendar):")
    for key, (sub, _, _) in frames.items():
        for c in sub.columns:
            s = sub[c]
            print(f"  {key}.{c:<10} min={s.min()*100:8.2f}%  max={s.max()*100:8.2f}%  "
                  f"nan={s.isna().sum()}  n={len(s)}")
    print(f"  negative RF days: {(df['rf'] < 0).sum()}")
    print(f"  duplicate dates : {df.index.duplicated().sum()}")
    print(f"  monotonic dates : {df.index.is_monotonic_increasing}")

    # --- 5. known-event spot checks ---------------------------------------------
    print("\nKnown-event spot checks (daily total returns):")
    for d in ["1987-10-19", "2008-10-13", "2020-03-16", "2020-03-24", "1929-10-28"]:
        ts = pd.Timestamp(d)
        if ts in df.index:
            r = df.loc[ts]
            print(f"  {d}: mkt {r['mkt_total']*100:+7.2f}%   scv {r['scv_total']*100:+7.2f}%")

    # --- 6. distributional shape -> is a Gaussian Kelly appropriate? ------------
    print("\nDaily EXCESS-return distribution shape:")
    for key, (sub, _, _) in frames.items():
        s = sub[SERIES[key]["exc"]]
        print(f"  {key}: mean={s.mean()*100:.4f}%  sd={s.std()*100:.4f}%  "
              f"skew={s.skew():+.2f}  excess-kurt={s.kurtosis():.1f}  "
              f"lag1-autocorr={s.autocorr(1):+.3f}")
    print("  -> strong excess kurtosis: the Gaussian f*=mu/sigma^2 formula is an")
    print("     approximation only; the empirical log-optimal f* is also reported.")

    both = df[["mkt_total", "scv_total"]].dropna()
    corr = both["mkt_total"].corr(both["scv_total"])
    print(f"\n  corr(mkt_total, scv_total) daily on {len(both):,} shared days = {corr:.3f}")

    OUT["scv_source"] = SCV_SOURCE
    OUT["scv_haircut"] = SCV_HAIRCUT
    OUT["sample"] = {k: dict(start=str(sub.index.min().date()), end=str(sub.index.max().date()),
                             n=len(sub), years=round(years, 2), obs_per_year=round(apy, 3))
                     for k, (sub, apy, years) in frames.items()}
    OUT["shape"] = {f"{k}_exc": dict(mean=float(s.mean()), sd=float(s.std()),
                                     skew=float(s.skew()), kurt=float(s.kurtosis()),
                                     ac1=float(s.autocorr(1)))
                    for k, (sub, _, _) in frames.items()
                    for s in [sub[SERIES[k]["exc"]]]}
    OUT["corr_daily_total"] = float(corr)
    with open(rf"{OUTDIR}\phase2_validation.json", "w") as f:
        json.dump(OUT, f, indent=2)
    kd_data.write_manifest("kd_phase2_validate.py")
    print(f"\nWrote {OUTDIR}\\phase2_validation.json")


def kf_monthly_small_value():
    """Ken French's 6-portfolio MONTHLY file, SMALL HiBM (VW). Cached next to the
    daily file; downloaded once. Returns None if it cannot be fetched."""
    import urllib.request
    from common import ff, paths
    path = paths.SHARED / "ff6" / "6_Portfolios_2x3_CSV.zip"
    if not path.exists():
        url = ("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
               "6_Portfolios_2x3_CSV.zip")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            path.write_bytes(urllib.request.urlopen(req, timeout=120).read())
        except Exception as exc:                    # offline: skip the check
            print(f"  [skip] KF monthly file unavailable ({type(exc).__name__})")
            return None
    m = ff.block_titled(ff.read_text(path), "Value Weighted Returns -- Monthly", "%Y%m")
    m.index = m.index + pd.offsets.MonthEnd(0)
    return m["SMALL HiBM"].dropna()


if __name__ == "__main__":
    main()
