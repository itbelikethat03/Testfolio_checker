"""
dfsvx_compare.py -- how much of the Ken French SMALL HiBM return could an
investor actually have captured? Compared with DFSVX (DFA US Small Cap Value),
the longest-running fund that targets the same corner. The CAGR gap is the
investability drag that kd_data.SCV_HAIRCUT can apply (~1.09%/yr).
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import ff  # noqa: E402

sv = ff.us_small_value_daily()


def cagr(series, start, end):
    sub = series.loc[start:end]
    nav = (1 + sub).prod()
    years = (sub.index[-1] - sub.index[0]).days / 365.25
    return nav ** (1/years) - 1, years, sub.index[0], sub.index[-1]


# DFSVX inception Mar 2, 1993. totalrealreturns.com window: 1993-02-26 to 2026-01-13 -> 11.168%
c1, y1, s1, e1 = cagr(sv, "1993-02-26", "2026-01-13")
print(f"Raw FF SMALL HiBM, {s1.date()} to {e1.date()} ({y1:.2f}yr): CAGR = {c1*100:.3f}%")
print(f"DFSVX (totalrealreturns.com, dividends reinvested), same window: 11.168%")
print(f"Implied annual drag needed: {(c1-0.11168)*100:.3f} pp/yr\n")

# Fact sheet window: inception Mar 2 1993 to Dec 31 2025
c2, y2, s2, e2 = cagr(sv, "1993-03-02", "2025-12-31")
print(f"Raw FF SMALL HiBM, {s2.date()} to {e2.date()} ({y2:.2f}yr): CAGR = {c2*100:.3f}%")

# trailing windows as of Dec 31 2025 (fact sheet: 1y 8.38%, 3y 12.19%, 5y 13.76%, 10y 10.38%)
for yrs, dfsvx_val in [(1, 8.38), (3, 12.19), (5, 13.76), (10, 10.38)]:
    start = pd.Timestamp("2025-12-31") - pd.DateOffset(years=yrs)
    c, y, s, e = cagr(sv, start, "2025-12-31")
    print(f"Trailing {yrs}yr ({s.date()} to {e.date()}): Raw FF CAGR = {c*100:.3f}%   "
          f"DFSVX = {dfsvx_val:.2f}%   gap = {(c*100-dfsvx_val):.3f}pp")
