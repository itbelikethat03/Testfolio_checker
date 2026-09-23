"""
tf_compare.py -- diff each testfolio series against our equivalent, and explain
every gap.

The headline case is FFSCV against the Kelly study's `scv` (Fama-French
SMALL HiBM): same nominal source, same 1926-07-01 start, but a 1.44pp CAGR gap.
The hypothesis ladder is walked cheapest-first and the sharpest test runs first:
on the dates both cover, are the daily returns the same numbers? Everything else
follows from that answer.

Writes COMPARISON.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
EC = HERE.parent / "efficient_core"
KD = HERE.parent / "scv_leverage"
sys.path.insert(0, str(EC))
sys.path.insert(0, str(KD))

import tf_load                      # noqa: E402
import tf_metrics as T              # noqa: E402
from common import ff               # noqa: E402

ANN = 252.0
FF_BLOCKS = {"value-weighted": "value", "equal-weighted": "equal"}


def stats(r: pd.Series) -> dict:
    nav = (1 + r).cumprod()
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    dd = nav / nav.cummax() - 1
    return dict(n=len(r), start=str(r.index[0].date()), end=str(r.index[-1].date()),
                years=yrs, cagr=float(nav.iloc[-1] ** (1 / yrs) - 1),
                vol=float(r.std(ddof=1) * np.sqrt(ANN)), maxdd=float(dd.min()))


def overlap_rows(a: pd.Series, b: pd.Series) -> list[str]:
    j = a.index.intersection(b.index)
    if len(j) < 60:
        return [f"| Overlap | too short ({len(j)} days) |"]
    x, y = a.loc[j], b.loc[j]
    return [
        f"| Shared trading days | {len(j):,} |",
        f"| Daily return correlation | {np.corrcoef(x, y)[0, 1]:.6f} |",
        f"| Days identical to 1e-9 | {((x-y).abs() < 1e-9).mean()*100:.2f}% |",
        f"| Max absolute daily difference | {(x-y).abs().max()*100:.2f}pp |",
        f"| Mean daily difference (ours − tf) | {(x-y).mean()*10000:+.3f}bp |",
        f"| Implied annual drift | {(x-y).mean()*ANN*100:+.2f}pp/yr |",
    ]


def ff_column_scan(tfr: pd.Series) -> list[str]:
    """Correlate testfolio's FFSCV against all 12 FF 6-portfolio series."""
    rows = []
    for bname, weighting in FF_BLOCKS.items():
        df = ff.us_port6_daily(weighting)
        for c in df.columns:
            s = df[c].dropna()
            j = s.index.intersection(tfr.index)
            if len(j) < 1000:
                continue
            x, y = s.loc[j], tfr.loc[j]
            yrs = (j[-1] - j[0]).days / 365.25
            rows.append(dict(block=bname, col=c,
                             corr=float(np.corrcoef(x, y)[0, 1]),
                             ident=float(((x - y).abs() < 1e-9).mean()),
                             cagr=float((1 + x).prod() ** (1 / yrs) - 1),
                             vol=float(x.std(ddof=1) * np.sqrt(ANN))))
    return rows


def ffscv_investigation(tf: pd.Series) -> list[str]:
    # Always the raw Ken French series, whatever kd_data.SCV_SOURCE is set to --
    # this page is the evidence for that setting, so it must not depend on it.
    ours = ff.us_small_value_daily()
    mkt = ff.us_market_daily()["mkt_total"]
    tfr = tf.pct_change().dropna()

    L = ["## FFSCV vs our `scv` (Fama-French SMALL HiBM)\n"]
    L.append("This is the pairing that matters: same nominal source, same "
             "1926-07-01 start, and the largest gap of any pair on this page.\n")

    a, b = stats(ours), stats(tfr)
    L.append("| | ours | testfolio |")
    L.append("|---|---:|---:|")
    L.append(f"| Window | {a['start']} → {a['end']} | {b['start']} → {b['end']} |")
    L.append(f"| Observations | {a['n']:,} | {b['n']:,} |")
    L.append(f"| Obs/yr | {a['n']/a['years']:.2f} | {b['n']/b['years']:.2f} |")
    L.append(f"| CAGR | {a['cagr']*100:.2f}% | {b['cagr']*100:.2f}% |")
    L.append(f"| Volatility | {a['vol']*100:.2f}% | {b['vol']*100:.2f}% |")
    L.append(f"| Max drawdown | {a['maxdd']*100:.2f}% | {b['maxdd']*100:.2f}% |")
    L.append("")

    # ---- Test 0
    L.append("### Test 0 — are the daily returns the same numbers?\n")
    L.append("| | |")
    L.append("|---|---:|")
    L += overlap_rows(ours, tfr)
    L.append("")
    L.append("**No.** Not one of the 24,951 shared days matches, and the correlation "
             "is 0.94 rather than 1.00. Whatever the gap is, it is not a calendar "
             "artefact — these are two different portfolios. Tests 1–4 establish what "
             "kind of difference it is.\n")

    # ---- Test 1: Saturdays, and whether OUR handling is right
    sat = ours[ours.index.weekday == 5]
    wk = ours[(ours.index.weekday != 5) & (ours.index <= sat.index.max())]
    msat = mkt[mkt.index.weekday == 5]
    L.append("### Test 1 — the Saturday sessions are real, and ours are handled correctly\n")
    L.append(f"Our series carries **{len(sat):,} Saturday sessions**, all on or before "
             f"{sat.index.max().date()}; testfolio's carries **0**. The NYSE traded "
             "Saturday mornings until 1952.\n")
    L.append("| | n | mean return |")
    L.append("|---|---:|---:|")
    L.append(f"| Saturdays (small value) | {len(sat):,} | {sat.mean()*100:+.4f}% |")
    L.append(f"| All other pre-1952 days | {len(wk):,} | {wk.mean()*100:+.4f}% |")
    L.append(f"| Saturdays (broad market) | {len(msat):,} | {msat.mean()*100:+.4f}% |")
    L.append("")
    L.append("Those Saturday returns are strongly positive on both series — this is the "
             "documented pre-1952 weekend effect (French, 1980: Monday returns negative, "
             "Saturday positive). **They are real sessions carrying real return**, so "
             "deleting them destroys return that actually happened:\n")

    variants = {
        "Saturdays kept — as we build it": ours,
        "Saturdays deleted": ours[ours.index.weekday != 5],
    }
    L.append("| Our variant | Obs | CAGR | Vol | Max DD |")
    L.append("|---|---:|---:|---:|---:|")
    for name, s in variants.items():
        st = stats(s.dropna())
        L.append(f"| {name} | {st['n']:,} | {st['cagr']*100:.2f}% | "
                 f"{st['vol']*100:.2f}% | {st['maxdd']*100:.2f}% |")
    bs = stats(tfr)
    L.append(f"| **testfolio FFSCV** | {bs['n']:,} | **{bs['cagr']*100:.2f}%** | "
             f"**{bs['vol']*100:.2f}%** | **{bs['maxdd']*100:.2f}%** |")
    L.append("")
    L.append("Testfolio's 12.95% sits **between** our two calendar treatments, so it is "
             "not simply dropping Saturdays either. Our handling is the correct one and "
             "is not the source of the gap.\n")

    # ---- Test 2: end date
    trunc = ours[ours.index <= tfr.index[-1]]
    st = stats(trunc)
    L.append("### Test 2 — end-date alignment\n")
    L.append(f"Truncating ours to testfolio's last day ({tfr.index[-1].date()}) moves "
             f"CAGR from {a['cagr']*100:.2f}% to **{st['cagr']*100:.2f}%** — "
             f"{(st['cagr']-a['cagr'])*100:+.2f}pp. Not the explanation either.\n")

    # ---- Test 3: which FF portfolio is it?
    L.append("### Test 3 — is it a different Fama-French portfolio?\n")
    L.append("Testfolio's series was correlated against **all twelve** series in the "
             "6-portfolio 2×3 file — both the value-weighted and equal-weighted blocks. "
             "If FFSCV were any of them, one row would correlate at 1.000.\n")
    scan = ff_column_scan(tfr)
    scan.sort(key=lambda r: -r["corr"])
    L.append("| Block | Column | Correlation | Identical days | CAGR | Vol |")
    L.append("|---|---|---:|---:|---:|---:|")
    for r in scan:
        mark = " ←ours" if (r["block"] == "value-weighted" and r["col"] == "SMALL HiBM") else ""
        L.append(f"| {r['block']} | {r['col']}{mark} | {r['corr']:.5f} | "
                 f"{r['ident']*100:.2f}% | {r['cagr']*100:.2f}% | {r['vol']*100:.2f}% |")
    L.append(f"| **testfolio FFSCV** | | | | **{bs['cagr']*100:.2f}%** | "
             f"**{bs['vol']*100:.2f}%** |")
    L.append("")
    L.append(f"The best match is {scan[0]['corr']:.3f} — nowhere near 1.000, and "
             "**zero identical days against any of the twelve**. Testfolio's FFSCV is "
             "not a column of this file.\n")

    # ---- Test 4: monthly, and where the divergence lives
    om = (1 + ours).resample("ME").prod() - 1
    tm = (1 + tfr).resample("ME").prod() - 1
    j = om.index.intersection(tm.index)
    x, y = om.loc[j], tm.loc[j]
    L.append("### Test 4 — monthly frequency, and where the divergence sits\n")
    L.append("Aggregating both to month-end removes every intra-month calendar "
             "difference, including the Saturdays. If the two were the same portfolio "
             "sampled differently, monthly returns would agree.\n")
    L.append("| | |")
    L.append("|---|---:|")
    L.append(f"| Months compared | {len(j):,} |")
    L.append(f"| Monthly correlation | {np.corrcoef(x, y)[0, 1]:.6f} |")
    L.append(f"| Months matching to 1e-4 | {((x-y).abs() < 1e-4).mean()*100:.2f}% |")
    L.append(f"| Max absolute monthly difference | {(x-y).abs().max()*100:.2f}pp |")
    L.append(f"| Mean difference | {(x-y).mean()*12*100:+.2f}pp/yr |")
    L.append("")
    dec = (x - y).groupby((x.index.year // 10) * 10).mean() * 12 * 100
    cnt = (x - y).groupby((x.index.year // 10) * 10).count()
    L.append("| Decade | Mean difference (ours − tf) | Months |")
    L.append("|---|---:|---:|")
    for d in dec.index:
        L.append(f"| {d}s | {dec[d]:+.2f}pp/yr | {cnt[d]} |")
    L.append("")
    L.append("The gap is **not a constant drag** — it is concentrated in the 1930s "
             f"({dec.get(1930, float('nan')):+.1f}pp/yr) and 1940s "
             f"({dec.get(1940, float('nan')):+.1f}pp/yr), the microcap-heavy, "
             "thinly-traded era, and runs around +1.5 to +2pp/yr through most of the "
             "modern period. A fee would be flat across decades and would not touch "
             "volatility; this does both.\n")

    # ---- Test 5: which side matches Ken French's own MONTHLY file?
    from kd_phase2_validate import kf_monthly_small_value
    mo = kf_monthly_small_value()
    if mo is not None:
        j5 = mo.index.intersection(om.index).intersection(tm.index)
        cg = lambda s: (1 + s).prod() ** (12 / len(s)) - 1
        L.append("### Test 5 — Ken French's own monthly file decides it\n")
        L.append("Ken French publishes the 2×3 portfolios **monthly** as well as daily, built "
                 "separately. If our daily parse were wrong, compounding it to month-end would "
                 "not reproduce the monthly file.\n")
        L.append("| | vs KF monthly: correlation | CAGR |")
        L.append("|---|---:|---:|")
        L.append(f"| KF monthly file, SMALL HiBM | — | {cg(mo[j5])*100:.2f}% |")
        L.append(f"| **ours** (KF daily, compounded) | **{np.corrcoef(mo[j5], om[j5])[0, 1]:.5f}** "
                 f"| {cg(om[j5])*100:.2f}% |")
        L.append(f"| testfolio FFSCV (compounded) | {np.corrcoef(mo[j5], tm[j5])[0, 1]:.5f} "
                 f"| {cg(tm[j5])*100:.2f}% |")
        L.append("")
        L.append(f"Over {len(j5):,} months ours tracks the official monthly series almost "
                 "exactly; testfolio's does not. **FFSCV is not Ken French's SMALL HiBM**, "
                 "and ours is.\n")

    # ---- fingerprint
    jj = ours.index.intersection(tfr.index)
    ob, tb = ours.loc[jj], tfr.loc[jj]
    L.append("### Fingerprint\n")
    L.append("| | ours | testfolio |")
    L.append("|---|---|---|")
    L.append(f"| Best single day | {ob.idxmax().date()} {ob.max()*100:+.2f}% | "
             f"{tb.idxmax().date()} {tb.max()*100:+.2f}% |")
    L.append(f"| Worst single day | {ob.idxmin().date()} {ob.min()*100:+.2f}% | "
             f"{tb.idxmin().date()} {tb.min()*100:+.2f}% |")
    L.append(f"| Daily skew | {ob.skew():.3f} | {tb.skew():.3f} |")
    L.append(f"| Excess kurtosis | {ob.kurtosis():.2f} | {tb.kurtosis():.2f} |")
    L.append(f"| Lag-1 autocorrelation | {ob.autocorr(1):.4f} | {tb.autocorr(1):.4f} |")
    L.append("")
    L.append("The extremes land on **the same two dates** — 1933-03-15 (the reopening "
             "after the Bank Holiday) and 1933-07-21 — so this is unmistakably the same "
             "market over the same history. But testfolio's version is damped at every "
             "extreme: lower skew, lower kurtosis, and **lower lag-1 autocorrelation "
             f"({tb.autocorr(1):.3f} vs {ob.autocorr(1):.3f})**.\n")
    L.append("Lower autocorrelation is the informative one. The Kelly study attributes "
             "our +0.128 daily autocorrelation to stale microcap pricing. Testfolio's "
             "series shows materially less of it, which points at a small-value "
             "portfolio with **larger, more liquid holdings** — a screened or "
             "investable-universe construction rather than the raw research portfolio.\n")

    L.append("### Verdict\n")
    L.append("**Neither series is wrong; they are different portfolios, and ours is "
             "correctly built.** Our `scv` is the documented `SMALL HiBM` column of the "
             "value-weighted block, parsed correctly, on a calendar whose Saturday "
             "sessions are genuine. Testfolio's FFSCV is a different, more liquid "
             "small-value construction that testfolio does not document.\n")
    L.append("**There is no bug to fix on our side.** What this does provide is "
             "independent corroboration of a caveat the Kelly study already makes about "
             "itself: `SMALL HiBM` is a research portfolio holding untradeable microcaps, "
             "and `dfsvx_compare.py` puts the implied investable drag at ≈1.09%/yr. "
             f"Testfolio's more liquid construction runs **{(a['cagr']-b['cagr'])*100:.2f}pp/yr "
             "below ours** — the same order of magnitude, arrived at independently.\n")
    L.append("**What the Kelly study does with this.** The two are never spliced into one "
             "series (they are different portfolios, so a join would put a level break "
             "into every statistic). `scv_leverage/kd_data.py` takes one source at a time: "
             "`SCV_SOURCE = \"kf\"` (default: documented, reproducible, matches the monthly "
             "file) or `\"testfolio\"` (ends 2025-10-31), and `SCV_HAIRCUT` can subtract a "
             "constant investability drag from the KF series.\n")
    return L


def letf_section() -> list[str]:
    """SSOSIM / UPROSIM against our leveraged-ETF model, and why they differ."""
    import json
    from common import ff as FF, leverage as LV, assets, paths
    sims = {k: v.pct_change().dropna() for k, v in tf_load.load_letf_sims().items()}
    s2, s3 = sims["SSOSIM"], sims["UPROSIM"]
    L = ["## SSOSIM / UPROSIM vs our leveraged-ETF model\n"]
    L.append("Both files start on 1885-03-20. After each fund's launch, testfolio's series **is "
             "the real fund**:\n")
    L.append("| | window | real fund | testfolio | daily corr |")
    L.append("|---|---|---:|---:|---:|")
    for tic, sim in (("SSO", s2), ("UPRO", s3)):
        real = assets.load(tic)
        j = real.index.intersection(sim.index)
        L.append(f"| {tic} | {j[0].date()} → {j[-1].date()} | {stats(real[j])['cagr']*100:.2f}% | "
                 f"{stats(sim[j])['cagr']*100:.2f}% | {np.corrcoef(real[j], sim[j])[0, 1]:.4f} |")
    L.append("")
    L.append("So the two sources can only disagree **before** launch, where both are models.\n")

    # --- what testfolio charges, backed out of the pair
    j = s2.index.intersection(s3.index)
    s2, s3 = s2[j], s3[j]
    E = 0.0091
    dt = pd.Series(j, index=j).diff().dt.days.fillna(1) / 365.0
    R = 3 * s2 - 2 * s3 + E * dt
    U = 2 * s2 - s3 + E * dt
    ffr = LV.fed_funds()
    Ra = R.groupby(R.index.year).sum() / dt.groupby(dt.index.year).sum()
    A = pd.DataFrame({"R": Ra, "ff": ffr.groupby(ffr.index.year).mean()}).loc[1955:2005].dropna()
    k, c = np.polyfit(A["ff"], A["R"], 1)
    e = A["R"] - (k * A["ff"] + c)
    L.append("### What testfolio charges for leverage\n")
    L.append("Both sims apply one model to one underlying index `u`: `r_L = bill + L·(u − bill) − "
             "(L − 1)·(R − bill) − TER`. Two leverage levels are enough to solve it exactly, every "
             "day:\n")
    L.append("* borrowing rate `R = 3·SSOSIM − 2·UPROSIM + TER`")
    L.append("* underlying `u = 2·SSOSIM − UPROSIM + TER`\n")
    L.append(f"Annual average of R against effective fed funds, 1955–2005 (before either fund "
             f"existed): **R = {k:.3f} × fed funds + {c*100:.2f}pp** (R² "
             f"{1 - e.var() / A['R'].var():.4f}, residual {e.std()*100:.2f}pp). Testfolio's "
             "borrowing cost therefore scales with the rate level: about fed funds + 2pp at 5% "
             "rates and + 3.4pp at 10%.\n")
    dec = pd.DataFrame({"R": Ra, "ff": ffr.groupby(ffr.index.year).mean()}).loc[1955:2005]
    dd = dec.groupby((dec.index // 10) * 10).mean() * 100
    L.append("| decade | testfolio R | fed funds | R − fed funds |")
    L.append("|---|---:|---:|---:|")
    for d, r in dd.iterrows():
        L.append(f"| {d}s | {r['R']:.2f}% | {r['ff']:.2f}% | {r['R'] - r['ff']:+.2f}pp |")
    L.append("")

    # --- the underlying is the same index as ours
    m = FF.us_market_daily()["mkt_total"]
    jj = U.index.intersection(m.index)
    L.append("The implied underlying `u` against the Ken French US market, on shared dates. The "
             "row before 1952 is **not comparable**: Ken French carries the Saturday sessions "
             "(real, positive-return days) and testfolio does not, so intersecting the two "
             "calendars deletes those days from ours.\n")
    L.append("| era | testfolio u | KF US market | Δ |")
    L.append("|---|---:|---:|---:|")
    for a, z in (("1927", "1951"), ("1955", "1969"), ("1970", "1989"), ("1990", "2008"), ("2009", "2026")):
        kk = jj[(jj >= a) & (jj <= f"{z}-12-31")]
        cu, cm = stats(U[kk])["cagr"], stats(m[kk])["cagr"]
        L.append(f"| {a}–{z}{' (calendar mismatch)' if a == '1927' else ''} | {cu*100:.2f}% | "
                 f"{cm*100:.2f}% | {(cu-cm)*100:+.2f}pp |")
    L.append("")
    L.append("Outside the 1970s–80s the index agrees to a few tenths of a point, so **the "
             "financing rule, not the index, is what separates the two histories**.\n")

    # --- which financing rule the real funds support
    vp = paths.RECON_OUT / "leverage_validation.json"
    if vp.exists():
        v = json.loads(vp.read_text(encoding="utf-8"))
        rs = v["rate_sensitive"]
        L.append("### Which rule the real funds support\n")
        L.append("The real SSO (2006+) and UPRO (2009+) have lived through two 4%-rate windows. "
                 "Each financing rule, run on SPY and scored against the funds (model minus real, "
                 "pp/yr; `common/validate_leverage.py`):\n")
        L.append("| fund / regime | avg fed funds | constant spread (+0.69%) | "
                 f"ours ({rs['beta']:.3f} × fed funds + {rs['spread']*100:.2f}%) | "
                 "testfolio (1.27 × fed funds + 0.67%) |")
        L.append("|---|---:|---:|---:|---:|")
        for key, row in v["model_errors_by_regime"].items():
            L.append(f"| {key} | {row['avg_fed_funds']*100:.2f}% | {row['constant']*100:+.2f} | "
                     f"{row['rate-sensitive']*100:+.2f} | {row['testfolio']*100:+.2f} |")
        L.append("")
        L.append("Testfolio's rule is 0.5–2pp/yr too punitive in exactly the high-rate windows "
                 "where it differs from ours. A constant spread is slightly generous there. The "
                 "rate-sensitive fit matches every regime within ~0.1pp except 2020–21, whose "
                 "COVID-crash swap costs at ~0% rates are excluded from the rate fit, and it is "
                 "what `common/leverage.py`'s `letf` preset uses.\n")

    # --- the resulting histories
    L.append("### Resulting pre-launch histories\n")
    L.append("| | era | ours | testfolio | Δ |")
    L.append("|---|---|---:|---:|---:|")
    for tic in ("SSO", "UPRO"):
        p = paths.RECON_OUT / f"{tic}.json"
        if not p.exists():
            continue
        vt = json.loads(p.read_text(encoding="utf-8")).get("vs_testfolio")
        if not vt:
            continue
        L.append(f"| **{tic}** | {vt['start'][:4]}–{vt['end'][:4]} | {vt['cagr_ours']*100:.2f}% | "
                 f"{vt['cagr_testfolio']*100:.2f}% | {(vt['cagr_ours']-vt['cagr_testfolio'])*100:+.2f}pp |")
        for lab, e in vt["eras"].items():
            L.append(f"| | {lab} | {e['ours']*100:.2f}% | {e['testfolio']*100:.2f}% | "
                     f"{(e['ours']-e['testfolio'])*100:+.2f}pp |")
    L.append("")
    L.append("The remaining gap is testfolio's heavier high-rate financing. From 2009 the "
             "testfolio column is the real fund, and ours runs a little below it because the Ken "
             "French total market lagged the S&P 500 over that stretch.\n")
    return L


def generic(tic: str, tf: pd.Series, ours: pd.Series, our_label: str,
            note: str) -> list[str]:
    tfr = tf.pct_change().dropna()
    L = [f"## {tf_load.EXPECTED[tic]['label']} vs our `{our_label}`\n", note + "\n"]
    j = ours.index.intersection(tfr.index)
    if len(j) > 60:
        ao, bo = stats(ours.loc[j]), stats(tfr.loc[j])
        L.append(f"On the {len(j):,} shared trading days "
                 f"({j[0].date()} → {j[-1].date()}):\n")
        L.append("| | ours | testfolio | Δ |")
        L.append("|---|---:|---:|---:|")
        L.append(f"| CAGR | {ao['cagr']*100:.2f}% | {bo['cagr']*100:.2f}% | "
                 f"{(ao['cagr']-bo['cagr'])*100:+.2f}pp |")
        L.append(f"| Volatility | {ao['vol']*100:.2f}% | {bo['vol']*100:.2f}% | "
                 f"{(ao['vol']-bo['vol'])*100:+.2f}pp |")
        L.append(f"| Max drawdown | {ao['maxdd']*100:.2f}% | {bo['maxdd']*100:.2f}% | "
                 f"{(ao['maxdd']-bo['maxdd'])*100:+.2f}pp |")
        L.append("")
        L.append("| | |")
        L.append("|---|---:|")
        L += overlap_rows(ours, tfr)
    L.append("")
    return L


def main():
    ser = tf_load.load_all()
    panel = pd.read_csv(EC / "output" / "panel_global_daily.csv",
                        parse_dates=["date"]).set_index("date").sort_index()

    L = ["# Testfolio vs our series\n"]
    L.append("Each section asks whether our series and testfolio's are the same "
             "underlying data, and where they are not, what accounts for it. Where a "
             "primary source exists (Ken French's own files, a live fund) it is the "
             "referee; testfolio is an independent second opinion, not the truth.\n")
    L.append("Both sides are measured with the conventions established in "
             "[VERIFY.md](VERIFY.md) — fixed 252 annualisation, 365.25 day-count — so "
             "no gap below is a measurement artefact.\n")
    L.append("---\n")

    L += ffscv_investigation(ser["FFSCV"])
    L.append("---\n")

    # NTSDSIM: WisdomTree NTSD = 90% US stocks + 60% developed ex-US EQUITY futures
    # (not bond futures), reconstructed in efficient_core/ec_ntsd.py.
    ntsd = pd.read_csv(EC / "output" / "ntsd" / "ntsd_synthetic_daily.csv",
                       parse_dates=["date"]).set_index("date")["ntsd_synth"].dropna()
    L += generic("NTSDSIM", ser["NTSDSIM"], ntsd, "ntsd_synth",
                 "NTSD (WisdomTree Efficient U.S. Plus International Equity) holds **0.90 US "
                 "equity + 0.60 notional developed ex-US equity futures + 0.10 bills**: 1.5× "
                 "equity, which is why its beta is 1.34 and its volatility sits well above "
                 "the market's. It is *not* the stock/bond 90/60 (`rec9060`), and an earlier "
                 "version of this page wrongly compared it with that. `efficient_core/"
                 "ec_ntsd.py` rebuilds it from the Ken French US market, testfolio's VEASIM "
                 "and the 1-month bill, net of the 0.35% TER, 0.02% trading costs and a 0.30% "
                 "futures financing spread, with quarterly + 5pp-drift rebalancing. A gap of "
                 "a few tenths of a percent a year is the whole cost/spread uncertainty.")
    L.append("---\n")

    L += generic("VTSIM_L2", ser["VTSIM_L2"], panel["lev15"].dropna(), "lev15",
                 "**Different leverage: testfolio is 2×, ours is 1.5×**, and ours is "
                 "developed-markets while testfolio's is global. Not comparable "
                 "head-to-head; no gap below is an error. Recorded to place both on the "
                 "leverage axis. (The leverage-cost model itself is validated against live "
                 "SSO/UPRO by `common/validate_leverage.py`.)")
    L.append("---\n")

    L += generic("TLTSIM", ser["TLTSIM"], panel["futures"].dropna(), "futures sleeve",
                 "Our `futures` column is the **excess** return on 1.0 notional of the "
                 "four-currency bond ladder; TLTSIM is a **total-return** US long "
                 "Treasury. They differ by the whole financing leg by construction, so "
                 "the CAGR gap should be roughly the cash rate — and it is.")
    L.append("---\n")

    L += letf_section()
    L.append("---\n")

    L.append("## DBMFSIM — no counterpart\n")
    L.append("The managed-futures work in `SCV_leverage_analysis` (`mf_and_kelly.py`, "
             "`mf_solve_cost.py`) lost its outputs to a dead scratchpad and its scripts "
             "still point at that path, so there is nothing to compare against. "
             "DBMFSIM 2000-2026 — 6.77% CAGR, 9.58% volatility, −20.44% max drawdown, "
             "beta 0.01 — is a usable external benchmark if that work is revived. "
             "See `context/reference/tech-debt.md`.\n")

    (HERE / "COMPARISON.md").write_text("\n".join(L), encoding="utf-8")
    print(f"[ok] {HERE / 'COMPARISON.md'}")


if __name__ == "__main__":
    main()
