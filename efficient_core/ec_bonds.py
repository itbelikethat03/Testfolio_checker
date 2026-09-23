"""
ec_bonds.py -- synthetic constant-maturity government bond returns, and from
them the return of a bond FUTURES position.

WHY THIS IS NEEDED
------------------
The 60% bond sleeve of the WisdomTree Global Efficient Core Index is held in
government bond FUTURES.  A futures position requires no funded capital, so its
return is (to a very good approximation) the EXCESS return of the underlying
bond over the local short rate:

        futures return  ~=  bond total return  -  local financing rate

That identity is the whole reason a 90/60 fund can exist, and it is also why
"financing cost" is not a free parameter: it is whatever the local money-market
rate happens to be, because that is what the futures price embeds.

METHOD
------
For each currency and tenor we hold a par bond of constant maturity M.  At each
step we reprice the bond we bought at the previous yield using the new yield,
add the accrued coupon, and roll back to a fresh M-year par bond:

    P(y, m, c) = c * (1 - (1+y)^-m) / y  +  (1+y)^-m          (annual coupons)
    R_t        = P(y_t(M - dt), M - dt, y_{t-1}(M)) - 1 + y_{t-1}(M) * dt

The bond is repriced at the yield the curve shows for its *aged* maturity
(M - dt), interpolated across the observed tenors, not at the M-year yield.
That matters: on an upward-sloping curve the aged bond is worth more than the
M-year point implies, and the difference is the ROLL-DOWN return, which is a
real and material part of what a bond futures ladder earns.  Using the M-year
yield instead understates a US 7-10y position by roughly 0.4pp a year.

This construction captures duration, convexity and roll-down, and it handles
negative yields (which EUR and JPY both had) without special-casing.

VALIDATION
----------
Run this file directly.  It compares the synthetic 2y / 7y / 20y US series
against the actual total returns of SHY, IEF and TLT since 2002.  If the
synthetic construction were wrong, those comparisons would not line up.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import ec_data as D

# ---------------------------------------------------------------------------
# Bond-sleeve specification, read off the WisdomTree index methodology
# (October 2025, "WisdomTree Global Efficient Core Index Methodology"):
#   "8 government bond future contracts laddered across maturities from 2 to
#    30-year segments ... grouped by currency and the weight of each currency
#    group will match the corresponding currency weight (re-scaled) from the
#    equity component ... all contracts equal weighted in each currency."
#
# The exact 8 contracts are not enumerated in the public methodology.  The
# split below is an ESTIMATE that satisfies every stated constraint (8
# contracts, 2-30y, four currencies, the documented US 2/5/10/30 ladder that
# WisdomTree also uses in NTSX).  ec_analysis.py runs a sensitivity on it.
#
# NOMINAL vs CHEAPEST-TO-DELIVER.  A bond future is named for a maturity
# BASKET, and it tracks the cheapest bond in that basket, which is materially
# shorter than the contract's name: the 10-year Note future (ZN) delivers a
# ~7-year note, the Classic Bond future (ZB) a ~18-year bond.  So the two
# ladders below describe the SAME contracts, one by name and one by what they
# actually track.
#
# LADDER_CTD is the base case, for two reasons decided before looking at any
# fit statistic: (a) it reproduces the ~7-year sleeve duration and the 3-8y
# duration target WisdomTree publishes for this construction, whereas the
# nominal ladder implies ~8.5y; (b) it is the physically correct description of
# a futures position.  ec_analysis.py reports the nominal ladder as a
# sensitivity so the choice is visible rather than buried.
# ---------------------------------------------------------------------------
LADDER_NOMINAL = {
    "usd": [2, 5, 10, 30],   # ZT, ZF, ZN, ZB  -- contract names
    "eur": [5, 10],          # Bobl, Bund
    "gbp": [10],             # Long Gilt
    "jpy": [10],             # 10y JGB
}

LADDER_CTD = {
    "usd": [2, 4.5, 7, 18],  # what ZT / ZF / ZN / ZB actually deliver
    "eur": [4.5, 8.5],       # Bobl, Bund
    "gbp": [9],              # Long Gilt
    "jpy": [9],              # 10y JGB
}

LADDER = LADDER_CTD

# Currency weights.  ESTIMATE derived from the fund's own published country
# weights (NTSG factsheet, 31/07/2026: US 69.32, JP 6.08, FR 3.25, UK 3.02,
# DE 2.47, NL 1.58, ES 1.39, + smaller EMU members ~1.6), keeping only the four
# currencies that have a bond sleeve and rescaling them to 100%.
CCY_WEIGHTS = {"usd": 0.781, "eur": 0.117, "gbp": 0.034, "jpy": 0.068}

# Alternative weightings used for the robustness check in ec_analysis.py.
CCY_ALTS = {
    "US only": {"usd": 1.0, "eur": 0.0, "gbp": 0.0, "jpy": 0.0},
    "equal 4-ccy": {"usd": .25, "eur": .25, "gbp": .25, "jpy": .25},
    "1990s Japan-heavy": {"usd": .45, "eur": .13, "gbp": .07, "jpy": .35},
}

# Coupons per year, matching each curve's quoting convention. Treasuries, gilts
# and JGBs pay (and are quoted) semi-annually; the ECB curve is an annual spot
# curve, so the euro leg stays annual.
COUPON_FREQ = {"usd": 2, "eur": 1, "gbp": 2, "jpy": 2}

FINANCING_COL = {"usd": "us_3m", "eur": "eur_3m", "gbp": "gbp_on",
                 "jpy": "jpy_1y"}

# Observed curve points per currency: maturity (years) -> column name.
# Used to interpolate the yield of an aged bond, i.e. to capture roll-down.
CURVE_POINTS = {
    "usd": {0.25: "us_3m", 2: "us_2y", 5: "us_5y", 10: "us_10y", 30: "us_30y"},
    "eur": {0.25: "eur_3m", 2: "eur_2y", 5: "eur_5y", 10: "eur_10y",
            30: "eur_30y"},
    "gbp": {0.003: "gbp_on", 5: "gbp_5y", 10: "gbp_10y", 20: "gbp_20y"},
    "jpy": {1: "jpy_1y", 2: "jpy_2y", 5: "jpy_5y", 10: "jpy_10y",
            30: "jpy_30y"},
}


# ---------------------------------------------------------------------------
# par-bond maths
# ---------------------------------------------------------------------------
def _price(y, m, c, freq=1):
    """Price (per 1 of face) of a bond, annual coupon rate `c` paid `freq` times
    a year, maturity `m` years, priced at yield `y` quoted with the same
    compounding.  Vectorised; safe at y == 0."""
    y = np.asarray(y, dtype=float) / freq
    c = np.asarray(c, dtype=float) / freq
    n = np.asarray(m, dtype=float) * freq
    disc = np.power(1.0 + y, -n)
    with np.errstate(divide="ignore", invalid="ignore"):
        annuity = np.where(np.abs(y) < 1e-10, n, (1.0 - disc) / y)
    return c * annuity + disc


def cm_bond_returns(curve: pd.DataFrame, points: dict, M: float,
                    freq: int = 1) -> pd.DataFrame:
    """Total return of a constant-maturity M-year par bond, given a whole yield
    curve so the aged bond can be repriced at its own maturity (roll-down).

    `curve`  -- frame of yields (decimal) indexed by date
    `points` -- {maturity_in_years: column name} describing that curve
    `freq`   -- coupons per year, matching how the curve's yields are quoted
                (COUPON_FREQ: 2 for Treasuries, gilts and JGBs)
    Returns a frame with `dt` (year fraction), `tr` (total return over the
    step) and `dur` (modified duration at the start of the step)."""
    mats = np.array(sorted(points), dtype=float)
    cols = [points[m] for m in sorted(points)]
    sub = curve[cols].astype(float)

    # Curves grow tenors over time (the 30y JGB only starts in 1999, the 30y
    # UST in 1977).  Rather than throw away every date on which one tenor is
    # missing, interpolate from whatever points exist that day -- but never
    # EXTRAPOLATE past the long end, so a date is usable only if the curve
    # actually reaches out to M.
    avail = sub.notna()
    long_enough = (avail * mats).max(axis=1) >= M
    usable = long_enough & (avail.sum(axis=1) >= 3)
    sub = sub[usable]
    if len(sub) < 3:
        raise ValueError(f"not enough curve observations for M={M}")

    grid = sub.values                                   # (n, k) yields
    dates = sub.index
    dt = dates.to_series().diff().dt.days.values / 365.0

    def interp_row(target, row):
        ok = np.isfinite(row)
        return float(np.interp(target, mats[ok], row[ok]))

    y_M = np.array([interp_row(M, row) for row in grid])
    y0 = np.r_[np.nan, y_M[:-1]]                        # coupon set yesterday
    aged = M - dt                                       # maturity today
    y_aged = np.array([interp_row(a, row) if np.isfinite(a) else np.nan
                       for a, row in zip(aged, grid)])

    tr = _price(y_aged, aged, y0, freq) - 1.0 + y0 * dt

    h = 1e-5
    dur = -(_price(y0 + h, M, y0, freq) - _price(y0 - h, M, y0, freq)) / (2 * h)

    out = pd.DataFrame({"dt": dt, "tr": tr, "dur": dur}, index=dates)
    return out.iloc[1:]


# ---------------------------------------------------------------------------
# assembling the four-currency futures sleeve
# ---------------------------------------------------------------------------
def build_curves(freq: str = "D") -> pd.DataFrame:
    """One frame of every yield we need, on a common calendar."""
    us, eur = D.load_us_curve(), D.load_eur_curve()
    gbp, jpy = D.load_gbp_curve(), D.load_jpy_curve()
    cur = pd.concat([us, eur, gbp, jpy], axis=1).sort_index()
    cur = cur[~cur.index.duplicated()]
    return cur


def futures_sleeve(curves: pd.DataFrame, calendar: pd.DatetimeIndex,
                   ccy_weights: dict | None = None,
                   ladder: dict | None = None) -> pd.DataFrame:
    """Return, per date on `calendar`, the excess (= futures) return of each
    currency's bond ladder and of the blended sleeve.

    `sleeve` is the return on 1.0 of NOTIONAL bond exposure.  Multiply by the
    0.60 notional weight to get the contribution to the fund."""
    ccy_weights = ccy_weights or CCY_WEIGHTS
    ladder = ladder or LADDER

    cur = curves.reindex(curves.index.union(calendar)).ffill(limit=7)
    cur = cur.reindex(calendar)

    per_ccy, durations = {}, {}
    for ccy, tenors in ladder.items():
        if ccy_weights.get(ccy, 0.0) == 0.0:
            continue
        fin = cur[FINANCING_COL[ccy]]
        legs, durs = [], []
        for M in tenors:
            r = cm_bond_returns(cur, CURVE_POINTS[ccy], M, COUPON_FREQ[ccy])
            legs.append(r["tr"] - fin.reindex(r.index) * r["dt"])
            durs.append(r["dur"])
        per_ccy[ccy] = pd.concat(legs, axis=1).mean(axis=1)
        durations[ccy] = pd.concat(durs, axis=1).mean(axis=1)

    df = pd.DataFrame(per_ccy)
    ccys = list(df.columns)

    # Renormalise across whatever currencies have data on each date.  The euro
    # curve only starts in 2004, so before then the sleeve is the USD/GBP/JPY
    # ladder rescaled to 100% rather than a hole in the series.  ec_analysis.py
    # measures what this substitution is worth over the overlapping period.
    w = pd.Series({c: ccy_weights[c] for c in ccys}, dtype=float)
    mask = df[ccys].notna()
    wmat = mask.mul(w, axis=1)
    wsum = wmat.sum(axis=1).replace(0.0, np.nan)

    df["sleeve"] = (df[ccys].fillna(0.0) * wmat).sum(axis=1) / wsum
    dur = pd.DataFrame({c: durations[c].reindex(df.index) for c in ccys})
    df["duration"] = (dur.fillna(0.0) * wmat).sum(axis=1) / wsum
    df["n_ccy"] = mask.sum(axis=1)
    return df


def us_only_sleeve(curves: pd.DataFrame, calendar: pd.DatetimeIndex,
                   tenors=(2, 5, 10, 30)) -> pd.DataFrame:
    """The NTSX bond sleeve: an equal-weighted 2/5/10/30 UST futures ladder."""
    return futures_sleeve(curves, calendar,
                          ccy_weights={"usd": 1.0},
                          ladder={"usd": list(tenors)})


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------
def _ann(series, dt_years):
    nav = float((1 + series).prod())
    return nav ** (1 / dt_years) - 1


def validate_against_treasury_etfs():
    """Synthetic constant-maturity bonds vs the real thing (SHY / IEI / IEF /
    TLT total returns).  Each ETF tracks a maturity BUCKET, so we compare it
    with the constant maturity closest to that bucket's average."""
    px = D.load_prices(["SHY", "IEI", "IEF", "TLT"])
    cur = build_curves()

    print("\nSynthetic constant-maturity US Treasuries vs actual ETF total returns")
    print("(ETFs hold maturity buckets, so a small duration mismatch is expected)")
    print(f"{'ETF':6s} {'bucket':12s} {'synth M':>8s} {'window':>25s} "
          f"{'ETF CAGR':>9s} {'synth':>9s} {'diff':>8s} {'corr':>6s} {'TE':>7s}")

    rows = []
    for tic, bucket, M in [("SHY", "1-3y UST", 2.0), ("IEI", "3-7y UST", 5.0),
                           ("IEF", "7-10y UST", 8.5), ("TLT", "20y+ UST", 22.0)]:
        etf = px[tic].dropna()
        etf_r = etf.pct_change().dropna()
        syn = cm_bond_returns(cur, CURVE_POINTS["usd"], M, COUPON_FREQ["usd"])

        idx = etf_r.index.intersection(syn.index)
        a, b = etf_r.reindex(idx), syn["tr"].reindex(idx)
        yrs = (idx[-1] - idx[0]).days / 365.25
        ca, cb = _ann(a, yrs), _ann(b, yrs)
        te = float((a - b).std() * np.sqrt(252))
        rows.append((tic, ca, cb, te))
        print(f"{tic:6s} {bucket:12s} {M:8.1f} "
              f"{str(idx[0].date()) + '..' + str(idx[-1].date()):>25s} "
              f"{ca * 100:8.2f}% {cb * 100:8.2f}% {(cb - ca) * 100:7.2f}pp "
              f"{a.corr(b):6.3f} {te * 100:6.2f}%")
    return rows


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    cur = build_curves()
    print(f"curves: {cur.index.min().date()} -> {cur.index.max().date()}, "
          f"n={len(cur):,}\ncolumns: {list(cur.columns)}")

    validate_against_treasury_etfs()

    ff = D.load_ff_developed_daily()
    cal = ff.index
    sl = futures_sleeve(cur, cal).dropna(subset=["sleeve"])
    print(f"\nGlobal 4-currency futures sleeve (return on 1.0 notional):")
    print(f"  window   {sl.index.min().date()} -> {sl.index.max().date()}  n={len(sl):,}")
    print(f"  mean duration {sl['duration'].mean():.2f}y   "
          f"(latest {sl['duration'].iloc[-1]:.2f}y)")
    yrs = (sl.index[-1] - sl.index[0]).days / 365.25
    for c in [c for c in sl.columns if c not in ("sleeve", "duration")] + ["sleeve"]:
        s = sl[c].dropna()
        print(f"  {c:8s} ann.excess {_ann(s, yrs) * 100:6.2f}%  "
              f"vol {s.std() * np.sqrt(252) * 100:5.2f}%")

    us = us_only_sleeve(cur, D.load_ff_us_daily().index).dropna(subset=["sleeve"])
    us = us.loc["2018-08-01":]
    yrs = (us.index[-1] - us.index[0]).days / 365.25
    print(f"\nUS 2/5/10/30 ladder since NTSX launch: ann.excess "
          f"{_ann(us['sleeve'], yrs) * 100:.2f}%  duration {us['duration'].mean():.2f}y")
