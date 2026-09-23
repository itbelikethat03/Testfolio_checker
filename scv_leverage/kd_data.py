"""
kd_data.py -- shared data layer for the "Kelly vs. best-days-removed" study.

RETURN DEFINITIONS (see PHASE 2 of the write-up)
------------------------------------------------
F-F_Research_Data_Factors_daily.csv
    Mkt-RF : daily EXCESS return of the CRSP value-weighted total-market
             portfolio, in percent.
    RF     : daily simple risk-free (1-month T-bill) rate, in percent.
    ->  mkt_exc   = Mkt-RF / 100                (excess, decimal)
    ->  mkt_total = (Mkt-RF + RF) / 100         (total,  decimal)

SMALL-CAP VALUE -- one source at a time, chosen by SCV_SOURCE
    "kf"         Ken French US `SMALL HiBM` (value-weighted 2x3 portfolio), the
                 documented research series. Compounded to month-end it matches
                 Ken French's own MONTHLY file (1926-2025: 14.26% vs 14.15%
                 CAGR, monthly correlation 0.9999), so the daily file is parsed
                 correctly. It holds microcaps an investor could not trade;
                 SCV_HAIRCUT lets a constant investability drag be applied
                 (dfsvx_compare.py measures ~1.09%/yr against DFSVX).
    "testfolio"  testfolio's FFSCV export, 1926-07-01 -> 2025-10-31. It is NOT
                 any column of the Ken French 2x3 file (monthly correlation
                 0.968 with SMALL HiBM, 12.95% vs 14.15% CAGR) -- an
                 undocumented, more liquid small-value construction. It ends
                 where the export ends; nothing is spliced onto it.

    The two sources are never joined into one series: they are different
    portfolios, and a splice would put a level break into every statistic.

    ->  scv_total = source daily total return - haircut   (decimal)
    ->  scv_exc   = scv_total - rf                        (excess, decimal)

CALENDARS
    The NYSE traded Saturday mornings until 1952-05-24. Ken French carries
    those 1,158 sessions and they carry real return (the documented pre-1952
    weekend effect), so they are kept. testfolio's FFSCV has none, so with
    SCV_SOURCE = "testfolio" `scv_total` is NaN on those dates.

    `load_daily()` returns the UNION of both calendars. Every consumer takes
    one series at a time, with that series' OWN annualisation factor -- use
    `series_frame()`, never `ann_factor()` on the whole frame.

Kelly is defined on EXCESS returns throughout; total returns are used only for
NAV / CAGR / drawdown reporting.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # the suite root
from common import ff, leverage, manifest, paths                  # noqa: E402

SCV_SOURCE = "kf"          # "kf" | "testfolio"
SCV_HAIRCUT = 0.0          # %/yr investability drag subtracted from scv (0.0109 = DFSVX)

PROJ = str(paths.KD)
SHARED = str(paths.SHARED)
OUTDIR = str(paths.KD_OUT)

# testfolio's FFSCV daily $ path. Verified by content (see load_ffscv); the
# original download folder had name collisions.
FFSCV_CSV = paths.TESTFOLIO_DATA / "FFSCV_daily.csv"
FFSCV_EXPECT = dict(start="1926-07-01", end="2025-10-31", ending_value=1_786_967_536.37)

SCV_LABELS = {
    "kf": "Small-cap value (Ken French SMALL HiBM, VW)",
    "testfolio": "Small-cap value (testfolio FFSCV)",
}


def load_ffscv(verbose=True):
    """testfolio FFSCV daily total returns, verified against its known endpoints."""
    df = pd.read_csv(FFSCV_CSV, parse_dates=["date"])
    if list(df.columns) != ["date", "value"]:
        raise ValueError(f"{FFSCV_CSV}: unexpected columns {list(df.columns)}")
    s = df.set_index("date")["value"].sort_index()

    got = (str(s.index[0].date()), str(s.index[-1].date()), float(s.iloc[-1]))
    want = (FFSCV_EXPECT["start"], FFSCV_EXPECT["end"], FFSCV_EXPECT["ending_value"])
    if got[0] != want[0] or got[1] != want[1] or abs(got[2] - want[2]) > 1.0:
        raise ValueError(
            f"{FFSCV_CSV} is not the expected FFSCV series.\n"
            f"  expected start={want[0]} end={want[1]} ending_value={want[2]:,.2f}\n"
            f"  found    start={got[0]} end={got[1]} ending_value={got[2]:,.2f}")

    r = s.pct_change().dropna()
    if verbose:
        print(f"[kd_data] testfolio FFSCV: {r.index[0].date()} -> {r.index[-1].date()}, "
              f"n={len(r):,}")
    return r


def load_scv(source=None):
    """Small-cap value daily total return from `source` (default SCV_SOURCE),
    with SCV_HAIRCUT applied pro rata per calendar day."""
    source = source or SCV_SOURCE
    if source == "kf":
        scv = ff.us_small_value_daily()
    elif source == "testfolio":
        scv = load_ffscv(verbose=False)
    else:
        raise ValueError(f"SCV_SOURCE must be 'kf' or 'testfolio', got {source!r}")
    if SCV_HAIRCUT:
        dt = scv.index.to_series().diff().dt.days.fillna(1).to_numpy() / 365.25
        scv = scv - SCV_HAIRCUT * dt
    return scv.rename("scv_total")


def load_daily(verbose=True, source=None):
    """Daily frame indexed by date with columns:
    mkt_total, mkt_exc, rf, scv_total, scv_exc  (all decimal, simple returns).

    The two series may sit on DIFFERENT calendars (see module docstring). Take
    one series at a time with `series_frame()`; do not call `ann_factor()` on
    this frame."""
    df = ff.us_market_daily()[["mkt_total", "mkt_exc", "rf"]]
    scv = load_scv(source)
    df = df.join(scv, how="outer")
    # The 6-portfolio file runs a little past the factors file. Without rf there
    # is no excess return and nothing downstream can use those dates.
    df = df[df["rf"].notna()]
    df["scv_exc"] = df["scv_total"] - df["rf"]
    # What borrowing costs over this bill each day (fed funds - 1m bill; see
    # common/leverage.py). Used only by the cost presets, never by frictionless Kelly.
    df["gap"] = leverage.gap_on(df.index, df["rf"], "kf_1m")
    df["ff_acc"] = leverage.ff_accrual_on(df.index, df["rf"], "kf_1m")

    if verbose:
        n_scv = int(df["scv_total"].notna().sum())
        print(f"[kd_data] mkt: {df.index.min().date()} -> {df.index.max().date()}, "
              f"n={len(df):,}")
        print(f"[kd_data] scv: {SCV_LABELS[source or SCV_SOURCE]}"
              f"{f', haircut {SCV_HAIRCUT:.2%}/yr' if SCV_HAIRCUT else ''}, n={n_scv:,}"
              f", absent on {len(df) - n_scv:,} dates")
    return df


def series_frame(df, key, with_gap=False):
    """One series on its OWN calendar, with its own annualisation factor.

    Returns (frame[total, exc, rf(, gap)], apy, years). Always use this rather
    than reading columns off `load_daily()` directly -- the two series need not
    share a calendar, so a single apy for the whole frame can be wrong.
    `with_gap` adds the per-day borrowing gap (fed funds minus rf) and the
    fed-funds accrual itself (`ff_acc`, for presets with rate_beta != 1)."""
    meta = SERIES[key]
    cols = [meta["total"], meta["exc"], "rf"] + (["gap", "ff_acc"] if with_gap else [])
    sub = df[cols].dropna()
    apy, years = ann_factor(sub)
    return sub, apy, years


def ann_factor(df):
    """Observations per year implied by the sample itself, so that a
    per-observation geometric mean annualizes back to the true calendar CAGR.

    Refuses a frame with gaps: on the union frame from `load_daily()` the
    count would mix two calendars."""
    if df.isna().any().any():
        raise ValueError("ann_factor() needs a gap-free frame; use series_frame(df, key)")
    years = (df.index[-1] - df.index[0]).days / 365.25
    return len(df) / years, years


def config() -> dict:
    """The data configuration every Kelly-study output depends on."""
    return dict(scv_source=SCV_SOURCE, scv_haircut=SCV_HAIRCUT,
                borrow_benchmark="fed funds", letf_spread=leverage.LETF_SPREAD,
                letf_rate_beta=leverage.LETF_RATE_BETA)


def write_manifest(script: str, **extra) -> None:
    manifest.record(OUTDIR, script, **config(), **extra)


SERIES = {
    "mkt": dict(label="Broad market (CRSP VW total market)",
                total="mkt_total", exc="mkt_exc"),
    "scv": dict(label=SCV_LABELS[SCV_SOURCE], total="scv_total", exc="scv_exc"),
}
