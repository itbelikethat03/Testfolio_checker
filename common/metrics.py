"""
metrics.py -- risk / return statistics, defined once so every table in every
study (and the testfolio cross-check) uses exactly the same conventions.

CONVENTIONS
-----------
* All inputs are SIMPLE returns in decimal, at whatever frequency. `ppy`
  (periods per year) is inferred from the index unless passed. Pass
  `ppy=TESTFOLIO_PPY` (252) to use testfolio's fixed annualisation, which
  testfolio_check/VERIFY.md established.
* CAGR is geometric and uses the true calendar span (365.25-day years), not
  periods / ppy, so it reconciles with a wealth chart.
* Sharpe and Sortino are computed on EXCESS returns over the supplied
  risk-free series -- never on total returns.
* Sortino / downside deviation use a zero-excess-return threshold (MAR = rf).
* Max drawdown is on the total-return NAV.
* Ulcer index is reported in PERCENT, as testfolio does (21.49, not 0.2149).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TESTFOLIO_PPY = 252.0


# --------------------------------------------------------------------------
# calendar
# --------------------------------------------------------------------------
def years_of(idx: pd.DatetimeIndex) -> float:
    return (idx[-1] - idx[0]).days / 365.25


def periods_per_year(idx: pd.DatetimeIndex) -> float:
    return (len(idx) - 1) / years_of(idx)


# --------------------------------------------------------------------------
# return statistics
# --------------------------------------------------------------------------
def nav(r: pd.Series) -> pd.Series:
    return (1.0 + r.fillna(0.0)).cumprod()


def cagr(r: pd.Series) -> float:
    r = r.dropna()
    if len(r) < 2:
        return np.nan
    return float((1 + r).prod() ** (1 / years_of(r.index)) - 1)


def vol(r: pd.Series, ppy: float | None = None) -> float:
    r = r.dropna()
    ppy = ppy or periods_per_year(r.index)
    return float(r.std(ddof=1) * np.sqrt(ppy))


def downside_dev(r: pd.Series, rf: pd.Series | float = 0.0,
                 ppy: float | None = None) -> float:
    r = r.dropna()
    ppy = ppy or periods_per_year(r.index)
    exc = r - (rf.reindex(r.index) if isinstance(rf, pd.Series) else rf)
    neg = exc.clip(upper=0.0)
    return float(np.sqrt((neg ** 2).mean()) * np.sqrt(ppy))


def sharpe(r: pd.Series, rf: pd.Series, ppy: float | None = None) -> float:
    r = r.dropna()
    ppy = ppy or periods_per_year(r.index)
    exc = (r - rf.reindex(r.index)).dropna()
    if exc.std(ddof=1) == 0:
        return np.nan
    return float(exc.mean() / exc.std(ddof=1) * np.sqrt(ppy))


def sortino(r: pd.Series, rf: pd.Series, ppy: float | None = None) -> float:
    r = r.dropna()
    ppy = ppy or periods_per_year(r.index)
    exc = (r - rf.reindex(r.index)).dropna()
    dd = downside_dev(r, rf, ppy)
    if dd == 0:
        return np.nan
    return float(exc.mean() * ppy / dd)


def beta(r: pd.Series, bench: pd.Series) -> float:
    """OLS slope of `r` on `bench` over their shared dates."""
    j = r.dropna().index.intersection(bench.dropna().index)
    if len(j) < 3:
        return np.nan
    return float(np.polyfit(bench.loc[j].values, r.loc[j].values, 1)[0])


# --------------------------------------------------------------------------
# drawdowns
# --------------------------------------------------------------------------
def drawdown_path(level: pd.Series) -> pd.Series:
    """Drawdown of a LEVEL (NAV / price) series."""
    return level / level.cummax() - 1.0


def drawdown(r: pd.Series) -> pd.Series:
    """Drawdown of a RETURN series."""
    return drawdown_path(nav(r))


def max_drawdown(r: pd.Series) -> float:
    return float(drawdown(r).min())


def calmar(r: pd.Series) -> float:
    mdd = max_drawdown(r)
    return float(cagr(r) / abs(mdd)) if mdd < 0 else np.nan


def ulcer_index(level: pd.Series) -> float:
    """RMS drawdown of a level series, in PERCENT."""
    dd = drawdown_path(level) * 100.0
    return float(np.sqrt((dd ** 2).mean()))


def underwater_episodes(level: pd.Series) -> pd.DataFrame:
    """Every peak -> trough -> recovery episode of a level series, including one
    still open at the end (recovered = NaT)."""
    dd = drawdown_path(level)
    rows, start = [], None
    for date, v in dd.items():
        if v < 0 and start is None:
            start = date
        elif v >= 0 and start is not None:
            seg = dd.loc[start:date]
            rows.append((start, seg.idxmin(), date, float(seg.min())))
            start = None
    if start is not None:
        seg = dd.loc[start:]
        rows.append((start, seg.idxmin(), pd.NaT, float(seg.min())))
    out = pd.DataFrame(rows, columns=["start", "trough", "recovered", "depth"])
    if out.empty:
        return out
    end = level.index[-1]
    out["len_to_recover_y"] = ((out["recovered"].fillna(end) - out["start"])
                               .dt.days / 365.25)
    out["len_to_trough_y"] = (out["trough"] - out["start"]).dt.days / 365.25
    return out


def drawdown_episodes(r: pd.Series, threshold: float = -0.10) -> pd.DataFrame:
    """Episodes of a RETURN series deeper than `threshold`, deepest first."""
    eps = underwater_episodes(nav(r))
    if eps.empty:
        return eps[["start", "trough", "recovered", "depth"]]
    out = eps.loc[eps["depth"] <= threshold, ["start", "trough", "recovered", "depth"]]
    out = out.reset_index(drop=True)
    if out.empty:
        return out
    out["months_to_trough"] = (out["trough"] - out["start"]).dt.days / 30.44
    out["months_to_recover"] = (out["recovered"] - out["trough"]).dt.days / 30.44
    return out.sort_values("depth")


def avg_drawdown(level: pd.Series) -> float:
    """Mean drawdown over the underwater days only (testfolio's convention)."""
    dd = drawdown_path(level)
    return float(dd[dd < 0].mean()) if (dd < 0).any() else 0.0


def longest_drawdown_years(level: pd.Series) -> float:
    """Longest peak -> recovery span in years (an open episode runs to the end)."""
    eps = underwater_episodes(level)
    return float(eps["len_to_recover_y"].max()) if len(eps) else 0.0


# --------------------------------------------------------------------------
# calendar-year and rolling views
# --------------------------------------------------------------------------
def calendar_year_returns(r: pd.Series) -> pd.Series:
    return r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)


def worst_best_year(r: pd.Series, complete_only: bool = True):
    """Worst / best CALENDAR year.  Partial first and last years are dropped
    when `complete_only`, so the numbers are comparable across strategies."""
    yr = calendar_year_returns(r)
    if complete_only and len(yr) > 2:
        first, last = r.index[0], r.index[-1]
        if not (first.month == 1 and first.day <= 5):
            yr = yr.drop(first.year, errors="ignore")
        if not (last.month == 12 and last.day >= 27):
            yr = yr.drop(last.year, errors="ignore")
    if yr.empty:
        return np.nan, np.nan, None, None
    return float(yr.min()), float(yr.max()), int(yr.idxmin()), int(yr.idxmax())


def rolling_cagr(r: pd.Series, years: float, ppy: float | None = None) -> pd.Series:
    """Rolling annualised return over a window of `years` calendar years."""
    r = r.dropna()
    ppy = ppy or periods_per_year(r.index)
    w = int(round(years * ppy))
    if w < 2 or w > len(r):
        return pd.Series(dtype=float)
    logn = np.log1p(r).rolling(w).sum()
    return np.expm1(logn / years).dropna()


# --------------------------------------------------------------------------
# tables
# --------------------------------------------------------------------------
def summary(r: pd.Series, rf: pd.Series, label: str = "",
            ppy: float | None = None) -> dict:
    ppy = ppy or periods_per_year(r.dropna().index)
    wy, by, wyr, byr = worst_best_year(r)
    return {
        "strategy": label,
        "start": r.dropna().index[0].date(),
        "end": r.dropna().index[-1].date(),
        "years": round(years_of(r.dropna().index), 2),
        "CAGR": cagr(r),
        "vol": vol(r, ppy),
        "Sharpe": sharpe(r, rf, ppy),
        "Sortino": sortino(r, rf, ppy),
        "MaxDD": max_drawdown(r),
        "Calmar": calmar(r),
        "downside_dev": downside_dev(r, rf, ppy),
        "worst_year": wy,
        "worst_year_when": wyr,
        "best_year": by,
        "best_year_when": byr,
    }


def summary_table(series: dict, rf: pd.Series, ppy: float | None = None) -> pd.DataFrame:
    return pd.DataFrame([summary(v, rf, k, ppy) for k, v in series.items()])


def testfolio_table(r: pd.Series, rf: pd.Series, bench: pd.Series | None = None,
                    start_value: float = 10_000.0) -> dict:
    """testfolio's summary-table columns, with the conventions VERIFY.md
    established (fixed 252 annualisation, 365.25-day CAGR, ulcer in percent,
    UPI on arithmetic excess return)."""
    r = r.dropna()
    ppy = TESTFOLIO_PPY
    level = start_value * pd.concat([pd.Series([1.0], index=[r.index[0] - pd.Timedelta(days=1)]),
                                     (1 + r).cumprod()])
    rfa = rf.reindex(r.index).ffill().fillna(0.0)
    exc = r - rfa
    c = float((level.iloc[-1] / level.iloc[0]) ** (1 / years_of(level.index)) - 1)
    mdd = float(drawdown_path(level).min())
    ul = ulcer_index(level)
    out = {
        "start": str(r.index[0].date()), "end": str(r.index[-1].date()),
        "ending_value": float(level.iloc[-1]),
        "cagr": c,
        "max_dd": mdd,
        "avg_dd": avg_drawdown(level),
        "longest_dd_y": longest_drawdown_years(level),
        "vol": float(r.std(ddof=1) * np.sqrt(ppy)),
        "sharpe": float(exc.mean() / exc.std(ddof=1) * np.sqrt(ppy)),
        "sortino": float(exc.mean() * ppy / (np.sqrt((exc.clip(upper=0) ** 2).mean())
                                             * np.sqrt(ppy))),
        "calmar": float(c / abs(mdd)) if mdd < 0 else np.nan,
        "ulcer": ul,
        "upi": float((r.mean() - rfa.mean()) * ppy * 100 / ul) if ul > 0 else np.nan,
    }
    if bench is not None:
        out["beta"] = beta(r, bench)
    return out


def fmt_table(df: pd.DataFrame) -> str:
    """Markdown-ish fixed-width rendering used by the console reports."""
    d = df.copy()
    pct = ["CAGR", "vol", "MaxDD", "downside_dev", "worst_year", "best_year",
           "cagr", "max_dd", "avg_dd"]
    for c in pct:
        if c in d:
            d[c] = d[c].map(lambda x: f"{x * 100:6.2f}%" if pd.notna(x) else "  n/a ")
    for c in ["Sharpe", "Sortino", "Calmar", "sharpe", "sortino", "calmar", "upi",
              "ulcer", "beta", "longest_dd_y"]:
        if c in d:
            d[c] = d[c].map(lambda x: f"{x:5.2f}" if pd.notna(x) else "  n/a")
    return d.to_string(index=False)
