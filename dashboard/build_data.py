"""
build_data.py -- normalise the two portfolio studies into ONE payload.

Sources
-------
efficient_core_9060   "Do levered bonds pay?" -- WisdomTree Global Efficient Core
                      (90/60) reconstructed from index rules. Developed-market
                      daily data 1990-2026 + US annual 1928-2025.

SCV_leverage_analysis "How much of the Kelly criterion rests on a handful of
                      days?" (kelly_bestdays). Fama-French US daily 1926-2026,
                      Kelly leverage sweeps and best-day removal.

The two studies were written independently and DO NOT share a window, a
universe or a base currency.  This script does not paper over that: every
portfolio carries its own coverage, and metrics are only ever computed on a
window a portfolio actually spans.  What it does add is parity -- the US
market / US small-value series from the Kelly study are re-scored with
`ec_metrics` on the Efficient Core windows, so the same Sharpe and Sortino
definitions apply to all eight portfolios.

Output: data.json  (consumed by build_dashboard.py)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SUITE = HERE.parent
EC = SUITE / "efficient_core"
KD = SUITE / "scv_leverage"
KDOUT = KD / "kelly_bestdays"
ECOUT = EC / "output"
NTSDOUT = ECOUT / "ntsd"

sys.path.insert(0, str(SUITE))
sys.path.insert(0, str(EC))
sys.path.insert(0, str(KD))

import ec_data                  # noqa: E402  EC_CONFIG, for the manifest check
import kd_data                  # noqa: E402  Ken-French parsing, reused verbatim
from common import leverage as LV, manifest, paths   # noqa: E402
from common import metrics as M  # noqa: E402  metric definitions, used for BOTH studies

RECONOUT = paths.RECON_OUT

# Which scripts must have produced the outputs this page reads, per folder.
KD_SCRIPTS = ["kd_phase2_validate.py", "kd_phase346_removal.py", "kd_phase5_control.py",
              "kd_phase8_diag.py", "kd_phase79_mc.py", "kd_phase12_cluster.py",
              "kd_phase12_context.py", "kd_phase13_optlev.py", "kd_phase14_fractions.py"]
EC_SCRIPTS = ["ec_validate.py", "ec_analysis.py", "ec_montecarlo.py", "ec_ntsd.py"]


def manifest_warnings() -> list[str]:
    """Every output that was not produced under the current configuration."""
    w = [f"scv_leverage: {m}" for m in manifest.check(KDOUT, KD_SCRIPTS, **kd_data.config())]
    w += [f"efficient_core: {m}" for m in manifest.check(ECOUT, EC_SCRIPTS, **ec_data.EC_CONFIG)]
    if (RECONOUT / "recon_summary.csv").exists():
        w += [f"reconstructions: {m}" for m in
              manifest.check(RECONOUT, ["recon.py"], letf_spread=LV.LETF_SPREAD,
                             letf_rate_beta=LV.LETF_RATE_BETA)]
    return w


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def jnum(x, nd=6):
    """JSON-safe number: NaN/inf/non-numeric -> None, otherwise rounded."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return round(f, nd) if np.isfinite(f) else None


def jval(v, nd=6):
    """One DataFrame cell -> a JSON-safe scalar."""
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return jnum(v, nd)
    if v is None or pd.isna(v):
        return None
    if isinstance(v, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(v).date())
    return str(v)


def records(df: pd.DataFrame, nd=6) -> list[dict]:
    """DataFrame -> list of dicts with NaN scrubbed and floats rounded."""
    return [{k: jval(v, nd) for k, v in row.items()}
            for row in df.to_dict(orient="records")]


def columns(df: pd.DataFrame, cols=None, nd=6) -> dict:
    """Date-indexed frame -> {dates: [...], col: [...], ...} for charting."""
    cols = list(df.columns) if cols is None else cols
    return dict(dates=[str(d.date()) for d in df.index],
                **{c: [jnum(v, nd) for v in df[c]] for c in cols})


def month_end_compound(r) -> pd.Series | pd.DataFrame:
    """Daily simple returns -> month-end compounded returns (empty month -> NaN)."""
    return (1.0 + r).resample("ME").prod(min_count=1) - 1.0


def read_csv_dated(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# 1. the two daily panels
# --------------------------------------------------------------------------
def load_panels():
    ec = read_csv_dated(ECOUT / "panel_global_daily.csv")
    kd = kd_data.load_daily(verbose=False)

    print(f"[ec] {ec.index.min().date()} -> {ec.index.max().date()}  n={len(ec):,}")
    print(f"[kd] {kd.index.min().date()} -> {kd.index.max().date()}  n={len(kd):,}")
    return ec, kd


# --------------------------------------------------------------------------
# 2. the unified portfolio registry
# --------------------------------------------------------------------------
# Every portfolio the dashboard knows about, from both studies, described in
# the same terms so a reader can see WHY two rows are or are not comparable.
PORTFOLIOS = [
    dict(id="rec9060", study="ec", col="rec9060",
         label="Reconstructed 90/60",
         short="90/60",
         slot=1,
         universe="Developed markets (22 countries, ESG-screened)",
         exposure="0.90 equity + 0.10 cash + 0.60 bond futures",
         notional=1.50, net_lev=1.50, equity_beta=0.90,
         costs="0.27%/yr (0.25% TER + 0.02% txn)",
         kind="synthetic",
         note="Index rules implemented literally: drifting weights, quarterly "
              "rebalance, 5pp drift trigger, four-currency cash. Validated "
              "against NTSX to +0.02pp/yr over 8.1 years."),
    dict(id="equity_dm", study="ec", col="equity_dm",
         label="Developed equities",
         short="DM equity",
         slot=2,
         universe="Developed markets (Ken French DM)",
         exposure="1.00 equity",
         notional=1.00, net_lev=1.00, equity_beta=1.00,
         costs="none (index)",
         kind="index",
         note="The benchmark NTSG is measured against. Not All-World: no "
              "emerging markets."),
    dict(id="lev15", study="ec", col="lev15",
         label="Developed equities, 1.5x levered",
         short="DM equity 1.5x",
         slot=3,
         universe="Developed markets (Ken French DM)",
         exposure="1.50 equity, borrowing 0.50 in USD",
         notional=1.50, net_lev=1.50, equity_beta=1.50,
         costs="USD 1-month bill + 0.30%/yr on the borrowed 0.50 (futures financing)",
         kind="synthetic",
         note="The like-for-like alternative use of leverage: same 1.5x "
              "notional as 90/60, but all of it in equity."),
    dict(id="scv_dm", study="ec", col="scv_dm",
         label="Developed small-cap value",
         short="DM small value",
         slot=4,
         universe="Developed markets, small-cap high book-to-market",
         exposure="1.00 equity",
         notional=1.00, net_lev=1.00, equity_beta=1.00,
         costs="none (index)",
         kind="index",
         note="Included as the factor alternative to leverage. Over 1990-2026 "
              "it beat 90/60 on both CAGR and Sharpe."),
    dict(id="acwi", study="ec", col="acwi",
         label="Global equities, All World (ACWI)",
         short="ACWI",
         slot=5,
         universe="Global developed + emerging (iShares ACWI, live ETF)",
         exposure="1.00 equity",
         notional=1.00, net_lev=1.00, equity_beta=1.00,
         costs="fund TER, embedded in price",
         kind="live fund",
         note="Live ETF price history, starts 2008-03-31."),
    dict(id="ntsg", study="ec", col="ntsg",
         label="Actual NTSG (live fund)",
         short="NTSG live",
         slot=7,
         universe="Developed markets (WisdomTree Global Efficient Core)",
         exposure="0.90 equity + 0.10 cash + 0.60 bond futures",
         notional=1.50, net_lev=1.50, equity_beta=0.90,
         costs="0.27%/yr, embedded in price",
         kind="live fund",
         note="The real fund. Only 1.8 years of history -- its metrics are "
              "not comparable to any long-window row."),
    dict(id="us_mkt", study="kd", col="mkt_total",
         label="US total market (CRSP VW)",
         short="US market",
         slot=6,
         universe="United States, value-weighted total market",
         exposure="1.00 equity",
         notional=1.00, net_lev=1.00, equity_beta=1.00,
         costs="none (research portfolio)",
         kind="index",
         note="From the Kelly study. US-only and gross of all costs, so it is "
              "not a substitute for the developed-market series."),
    dict(id="us_scv", study="kd", col="scv_total",
         label={"kf": "US small-cap value (KF SMALL HiBM)",
                "testfolio": "US small-cap value (testfolio FFSCV)"}[kd_data.SCV_SOURCE],
         short="US small value",
         slot=8,
         universe="United States, small-ME / high-BE-ME, value-weighted",
         exposure="1.00 equity",
         notional=1.00, net_lev=1.00, equity_beta=1.00,
         costs=(f"{kd_data.SCV_HAIRCUT:.2%}/yr investability haircut" if kd_data.SCV_HAIRCUT
                else "none -- see caveat"),
         kind="index",
         note={"kf": "Ken French's research portfolio, which holds untradeable microcaps. "
                     "Real funds captured ~1%/yr less (DFSVX, section 08)"
                     + (", and that haircut IS applied here." if kd_data.SCV_HAIRCUT
                        else "; that haircut is NOT applied here.")
                     + " Its +0.128 daily autocorrelation (stale microcap prices) "
                       "also flatters measured growth.",
               "testfolio": "testfolio's FFSCV: an undocumented, more liquid small-value "
                            "series (not Ken French SMALL HiBM), ending 2025-10-31."
               }[kd_data.SCV_SOURCE]),
]

# Draw order == palette slot order. The categorical palette is only validated
# for colourblind separation on ADJACENT slots, so the series must be listed in
# slot order for that guarantee to hold in a legend or a multi-line chart.
PORTFOLIOS.sort(key=lambda p: p["slot"])

# The five windows the dashboard offers. Each is a real boundary in the data,
# not a round number: a series either spans it or is marked n/a.
WINDOWS = [
    dict(id="us99", label="US long history", sub="1926-2026, 99.8y",
         start="1926-07-01", end="2026-04-30",
         why="The Kelly study's own window. Only the two US research "
              "portfolios reach back this far; nothing from the Efficient "
              "Core study exists before 1990."),
    dict(id="recon", label="Efficient Core reconstruction", sub="1990-2026, 36.1y",
         start="1990-07-03", end="2026-07-31",
         why="The longest window the 90/60 reconstruction spans. Very nearly "
              "the greatest bond bull market in recorded history -- this is "
              "not a neutral sample for a levered-bond structure."),
    dict(id="acwi", label="Since ACWI exists", sub="2008-2026, 18.3y",
         start="2008-03-31", end="2026-07-31",
         why="The only window on which all seven non-NTSG portfolios can be "
              "compared like for like."),
    dict(id="ntsx", label="Since NTSX exists", sub="2018-2026, 8.1y",
         start="2018-08-02", end="2026-07-31",
         why="The window over which the 90/60 reconstruction was validated "
              "against a real fund. Contains 2022."),
    dict(id="live", label="Since NTSG exists", sub="2024-2026, 1.8y",
         start="2024-11-11", end="2026-07-31",
         why="The live fund's entire history. Far too short for any metric "
              "here to be meaningful -- shown because it is the only window "
              "containing the actual product."),
]

# Minimum share of a window a portfolio must cover before it is scored at all.
MIN_COVERAGE = 0.90


def portfolio_returns(ec: pd.DataFrame, kd: pd.DataFrame, p: dict) -> pd.Series:
    src = ec if p["study"] == "ec" else kd
    return src[p["col"]].dropna()


def score_window(ec, kd, win) -> list[dict]:
    """Score every portfolio that genuinely spans `win`, using ec_metrics."""
    lo, hi = pd.Timestamp(win["start"]), pd.Timestamp(win["end"])
    span_days = (hi - lo).days
    rows = []

    for p in PORTFOLIOS:
        r = portfolio_returns(ec, kd, p).loc[lo:hi]
        if len(r) < 60:
            rows.append(dict(id=p["id"], status="absent"))
            continue

        coverage = (r.index[-1] - r.index[0]).days / span_days
        if coverage < MIN_COVERAGE:
            rows.append(dict(id=p["id"], status="absent",
                             partial_start=str(r.index[0].date()),
                             partial_end=str(r.index[-1].date()),
                             coverage=jnum(coverage, 4)))
            continue

        # Both studies carry a daily USD 1-month T-bill; use the study's own.
        src = ec if p["study"] == "ec" else kd
        rf = src["rf"].dropna().reindex(r.index).ffill()
        s = M.summary(r, rf, p["label"])

        # A portfolio can span the window and still stop short of its end --
        # the Kelly data ends 2026-04-30, the Efficient Core data 2026-07-31.
        truncated = (hi - r.index[-1]).days > 45 or (r.index[0] - lo).days > 45

        rows.append(dict(
            id=p["id"], status="ok",
            start=str(s["start"]), end=str(s["end"]), years=jnum(s["years"], 2),
            coverage=jnum(coverage, 4), truncated=bool(truncated),
            cagr=jnum(s["CAGR"]), vol=jnum(s["vol"]),
            sharpe=jnum(s["Sharpe"]), sortino=jnum(s["Sortino"]),
            maxdd=jnum(s["MaxDD"]), calmar=jnum(s["Calmar"]),
            downside_dev=jnum(s["downside_dev"]),
            worst_year=jnum(s["worst_year"]), worst_year_when=s["worst_year_when"],
            best_year=jnum(s["best_year"]), best_year_when=s["best_year_when"],
        ))
    return rows


# --------------------------------------------------------------------------
# 3. one monthly panel, for every chart
# --------------------------------------------------------------------------
def monthly_panel(ec, kd) -> dict:
    """Month-end compounded total returns for all eight portfolios on one axis.

    Charts are drawn from this; the metric tables above are computed on the
    full DAILY series, so a max drawdown in a table is deeper than the same
    drawdown read off a chart. That difference is real and is footnoted in
    the dashboard rather than smoothed away."""
    panel = pd.DataFrame({p["id"]: month_end_compound(portfolio_returns(ec, kd, p))
                          for p in PORTFOLIOS})
    # the risk-free leg, so the front end can draw an excess-return view
    rf = pd.concat([kd["rf"], ec["rf"]]).groupby(level=0).last()
    panel["rf"] = month_end_compound(rf)
    panel = panel.sort_index().dropna(how="all")

    c = columns(panel)
    return dict(dates=c.pop("dates"), series=c)


# --------------------------------------------------------------------------
# 4. study-specific tables, passed through with their schemas intact
# --------------------------------------------------------------------------
def csv_records(folder: Path, files: dict[str, str]) -> dict:
    return {key: records(pd.read_csv(folder / name)) for key, name in files.items()}


def json_files(folder: Path, files: dict[str, str]) -> dict:
    return {key: read_json(folder / name) for key, name in files.items()}


def month_end_last(path: Path) -> pd.DataFrame:
    """Rolling-window series, thinned to month-end so the payload stays small."""
    return read_csv_dated(path).resample("ME").last().dropna(how="all")


def ec_tables() -> dict:
    t = csv_records(ECOUT, {
        "table1_common": "table1_common_window.csv",
        "table1_own": "table1_own_windows.csv",
        "table1_ntsg": "table1_ntsg_window.csv",
        "annualised": "table_annualised_windows.csv",
        "subperiods": "table_subperiods.csv",
        "crisis": "crisis_returns.csv",
        "regimes": "regimes.csv",
        "long_us_periods": "long_us_periods.csv",
        "long_us_annual": "long_us_annual.csv",
        "robustness": "robustness.csv",
        "fin_hist": "financing_sensitivity_historical.csv",
        "fin_fwd": "financing_sensitivity_forward.csv",
        "corr_sens": "sensitivity_correlation.csv",
        "mc_sens": "montecarlo_sensitivity.csv",
    })

    # return grid: first column header is empty in the CSV
    grid = pd.read_csv(ECOUT / "sensitivity_return_grid.csv")
    t["return_grid"] = records(grid.rename(columns={grid.columns[0]: "bond"}))

    mc = read_json(ECOUT / "montecarlo_summary.json")
    t["mc_A"] = mc["A_global_monthly"]
    t["mc_B"] = mc["B_us_annual"]
    t.update(json_files(ECOUT, {"headline": "headline_stats.json",
                                "validation": "validation.json"}))

    t["rolling"] = columns(month_end_last(ECOUT / "rolling_differences.csv"))
    t["rolling_corr"] = columns(month_end_last(ECOUT / "rolling_correlation.csv"),
                                ["corr_3y"])
    return t


def kd_tables() -> dict:
    t = csv_records(KDOUT, {
        "removal": "phase346_removal.csv",
        "removed_days": "removed_days_log.csv",
        "rand_control": "phase5_random_control.csv",
        "mc79": "phase79_montecarlo.csv",
        "lev_sweep": "phase13_leverage_sweep.csv",
        "opt_lev": "phase13_optimal_leverage.csv",
        "opt_lev_costs": "phase13_optimal_leverage_costs.csv",
    })
    t.update(json_files(KDOUT, {
        "context": "phase12_context.json",
        "clustering": "phase12_clustering.json",
        "diagnostics": "phase8_diagnostics.json",
        "validation": "phase2_validation.json",
    }))
    t["p14"] = kd_phase14()
    return t


def kd_phase14() -> dict:
    """Phase 14: fractional Kelly vs best-day removal (kd_phase14_fractions.py)."""
    t = csv_records(KDOUT, {
        "scenarios": "phase14_scenarios.csv",
        "sensitivity": "phase14_sensitivity.csv",
        "equiv_x": "phase14_equivalent_x.csv",
        "growth_share": "phase14_growth_share.csv",
    })
    sim = pd.read_csv(KDOUT / "phase14_similarity.csv")
    t["similarity"] = records(sim[["series", "variant", "from_id", "to_id",
                                   "dist_all", "dist_risk", "dist_return"]], 4)
    g = pd.read_csv(KDOUT / "phase14_grid.csv")
    g = g[(g["frac"] == "full") & (g["X"] <= 100)]
    t["full_grid"] = records(g[["series", "X", "cagr", "sharpe", "max_dd", "ann_vol"]])
    h = pd.read_csv(KDOUT / "phase14_distribution.csv")
    h = h[h["scenario"].isin(["full_x0", "half_x0", "quarter_x0", "full_x100"])]
    t["distribution"] = records(h, 7)
    # month-end paths, one column block per series. NAV spans 1e-5 .. 1e8, so
    # round to significant figures -- fixed decimals would zero the low end.
    # Half Kelly with days removed is never drawn, so those columns are dropped.
    p = pd.read_csv(KDOUT / "phase14_paths.csv", parse_dates=["date"])
    p = p[[c for c in p.columns if not (c.startswith(("nav_half_", "dd_half_")) and not c.endswith("_x0"))]]
    sig4 = np.vectorize(lambda v: float(f"{v:.4g}") if np.isfinite(v) else v)
    sig3 = np.vectorize(lambda v: float(f"{v:.3g}") if np.isfinite(v) else v)
    t["paths"] = {}
    for k, d in p.groupby("series"):
        d = d.drop(columns="series").set_index("date")
        out = pd.DataFrame({c: (sig4 if c.startswith("nav_") else sig3)(d[c].to_numpy(float))
                            for c in d.columns}, index=d.index)
        t["paths"][k] = columns(out, nd=12)
    t["summary"] = read_json(KDOUT / "phase14_summary.json")
    return t


def ntsd_tables() -> dict:
    """NTSD synthetic (ec_ntsd.py). Kept out of the eight-portfolio registry:
    the categorical palette is validated for eight slots and no more."""
    t = csv_records(NTSDOUT, {"summary": "ntsd_summary.csv",
                              "spread": "ntsd_spread_sensitivity.csv"})
    t["results"] = read_json(NTSDOUT / "ntsd_results.json")

    d = read_csv_dated(NTSDOUT / "ntsd_synthetic_daily.csv")
    cols = ["ntsd_synth", "ntsdsim_testfolio", "us_mkt", "veasim"]
    t["monthly"] = columns(month_end_compound(d[cols]).dropna(how="all"))

    lv = read_csv_dated(NTSDOUT / "ntsd_live_vs_synthetic.csv")
    t["live"] = columns(lv, ["ntsd_real", "synth_efa", "synth_vea"])
    return t


def recon_tables() -> dict | None:
    """Fund reconstructions (reconstructions/recon.py) and the leverage-cost
    validation (common/validate_leverage.py). None if they have not been run."""
    if not (RECONOUT / "recon_summary.csv").exists():
        return None
    summary = pd.read_csv(RECONOUT / "recon_summary.csv")
    funds = []
    for tic in summary["ticker"]:
        f = read_json(RECONOUT / f"{tic}.json")
        funds.append({k: f.get(k) for k in ("ticker", "name", "structure", "ter",
                                             "history", "history_monthly", "vs_testfolio")})
    out = dict(summary=records(summary), funds=json.loads(json.dumps(funds, default=str)),
               presets=[dict(name=p.name, spread=p.spread, ter=p.ter, rate_beta=p.rate_beta,
                             over_fed_funds=p.over_fed_funds,
                             daily_reset=p.daily_reset, note=p.note)
                        for p in LV.PRESETS.values()])
    for key, name in (("letf", "leverage_validation.json"),
                      ("investable_scv", "investable_scv.json")):
        p = RECONOUT / name
        out[key] = read_json(p) if p.exists() else None
    return scrub(out)


def scrub(o):
    """NaN / inf anywhere in a nested structure -> None (the payload is strict JSON)."""
    if isinstance(o, dict):
        return {k: scrub(v) for k, v in o.items()}
    if isinstance(o, list):
        return [scrub(v) for v in o]
    if isinstance(o, float) and not np.isfinite(o):
        return None
    return o


# --------------------------------------------------------------------------
# 5. the cross-study bridge
# --------------------------------------------------------------------------
def leverage_bridge(scored: dict) -> dict:
    """The one axis both studies genuinely share: how much notional exposure
    a portfolio carries, and what that bought.

    The Kelly study sweeps leverage f on US equities and asks what f a growth
    or a drawdown-budget objective picks. The Efficient Core study holds two
    portfolios at 1.5x notional -- one levering equity, one levering bonds --
    and asks which is the better use of the same leverage. Plotting the
    Efficient Core portfolios against the Kelly sweep is the comparison the
    two studies were never able to make separately.

    The overlay is indicative, not an apples-to-apples overlay: the sweep is a
    25-year block-bootstrap of US daily data, the markers are realised
    developed-market history. The dashboard says so on the chart."""
    out = {}
    for wid in ("recon", "acwi"):
        rows = {r["id"]: r for r in scored[wid]}
        pts = []
        for p in PORTFOLIOS:
            row = rows.get(p["id"])
            if not row or row["status"] != "ok":
                continue
            pts.append(dict(id=p["id"], label=p["label"], short=p["short"],
                            slot=p["slot"], notional=p["notional"],
                            equity_beta=p["equity_beta"],
                            cagr=row["cagr"], vol=row["vol"],
                            maxdd=row["maxdd"], sharpe=row["sharpe"]))
        out[wid] = pts
    return out


# --------------------------------------------------------------------------
def main():
    warnings = manifest_warnings()
    for w in warnings:
        print(f"[stale] {w}")
    ec, kd = load_panels()

    scored = {}
    for w in WINDOWS:
        scored[w["id"]] = score_window(ec, kd, w)
        ok = sum(r["status"] == "ok" for r in scored[w["id"]])
        print(f"[win] {w['id']:<6} {w['sub']:<18} {ok}/{len(PORTFOLIOS)} portfolios")

    payload = dict(
        meta=dict(
            generated=str(pd.Timestamp.now().date()),
            ec_window=[str(ec.index.min().date()), str(ec.index.max().date())],
            kd_window=[str(kd.index.min().date()), str(kd.index.max().date())],
            ec_n=len(ec), kd_n=len(kd),
            min_coverage=MIN_COVERAGE,
            scv_source=kd_data.SCV_SOURCE, scv_haircut=kd_data.SCV_HAIRCUT,
            warnings=warnings,
        ),
        portfolios=PORTFOLIOS,
        windows=WINDOWS,
        scored=scored,
        panel=monthly_panel(ec, kd),
        ec=ec_tables(),
        kd=kd_tables(),
        ntsd=ntsd_tables(),
        recon=recon_tables(),
        bridge=leverage_bridge(scored),
    )

    out = HERE / "data.json"
    out.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False),
                   encoding="utf-8")
    kb = out.stat().st_size / 1024
    print(f"\n[ok] {out}  {kb:,.0f} KB")


if __name__ == "__main__":
    main()

