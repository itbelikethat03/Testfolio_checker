"""
tf_metrics.py -- recompute the testfolio summary table from the daily $ paths.

Six of the thirteen columns have exactly one definition and are simply computed.
The other seven have more than one convention in common use, so each is computed
several plausible ways and the report names which variant reproduces testfolio's
published figure. That way a mismatch is attributed to a definition rather than
being tuned away.

The primitives (day-count, drawdowns, ulcer) come from common/metrics.py, so the
studies and this check cannot drift apart.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

SUITE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SUITE))
sys.path.insert(0, str(SUITE / "efficient_core"))
sys.path.insert(0, str(SUITE / "scv_leverage"))

import tf_load                  # noqa: E402
from common.metrics import (    # noqa: E402,F401  (re-exported for tf_verify / tf_compare)
    drawdown_path, periods_per_year as ppy, ulcer_index, underwater_episodes, years_of)


# --------------------------------------------------------- metric variants
def compute(nav: pd.Series, rf: pd.Series | None = None,
            bench: pd.Series | None = None) -> dict:
    """Every metric, with each ambiguous one computed all plausible ways."""
    r = nav.pct_change().dropna()
    idx = nav.index
    n_ppy = ppy(idx)
    yrs = years_of(idx)
    dd = drawdown_path(nav)
    eps = underwater_episodes(nav)

    cagr = float((nav.iloc[-1] / nav.iloc[0]) ** (1 / yrs) - 1)
    vol = float(r.std(ddof=1) * np.sqrt(n_ppy))
    mdd = float(dd.min())

    out = {
        # --- unambiguous
        "ending_value": float(nav.iloc[-1]),
        "cum_return": float(nav.iloc[-1] / nav.iloc[0] - 1),
        "cagr": cagr,
        "max_dd": mdd,
        "vol": vol,
        "calmar": float(cagr / abs(mdd)) if mdd < 0 else np.nan,
        "ulcer": ulcer_index(nav),
        # --- context
        "n": len(nav), "years": yrs, "ppy": n_ppy,
        "start": str(idx[0].date()), "end": str(idx[-1].date()),
    }

    # --- avg drawdown: mean of the daily path vs mean depth of episodes
    out["avg_dd__daily_path"] = float(dd.mean())
    out["avg_dd__daily_underwater"] = float(dd[dd < 0].mean()) if (dd < 0).any() else 0.0
    out["avg_dd__episode_depth"] = float(eps["depth"].mean()) if len(eps) else np.nan

    # --- longest drawdown: peak->recovery vs peak->trough
    if len(eps):
        out["longest_dd__to_recover"] = float(eps["len_to_recover_y"].max())
        out["longest_dd__to_trough"] = float(eps["len_to_trough_y"].max())
    else:
        out["longest_dd__to_recover"] = out["longest_dd__to_trough"] = np.nan

    # --- Sharpe / Sortino / UPI need a risk-free leg
    if rf is not None:
        rfa = rf.reindex(r.index).ffill().fillna(0.0)
        exc = r - rfa
        rf_cagr = float((1 + rfa).prod() ** (1 / yrs) - 1)
        sd = exc.std(ddof=1)
        out["rf_cagr"] = rf_cagr
        out["sharpe__excess_mean"] = float(exc.mean() / sd * np.sqrt(n_ppy)) if sd else np.nan
        # geometric variant: annualised excess CAGR over annualised excess vol
        out["sharpe__geometric"] = float((cagr - rf_cagr) / vol) if vol else np.nan

        neg = exc.clip(upper=0.0)
        dsd = float(np.sqrt((neg ** 2).mean()) * np.sqrt(n_ppy))
        out["sortino__mar_rf"] = float(exc.mean() * n_ppy / dsd) if dsd else np.nan
        neg0 = r.clip(upper=0.0)
        dsd0 = float(np.sqrt((neg0 ** 2).mean()) * np.sqrt(n_ppy))
        out["sortino__mar_zero"] = float(r.mean() * n_ppy / dsd0) if dsd0 else np.nan

        out["upi__excess_over_ulcer"] = float((cagr - rf_cagr) * 100 / out["ulcer"])
        out["upi__cagr_over_ulcer"] = float(cagr * 100 / out["ulcer"])

    # --- beta against a supplied benchmark
    if bench is not None:
        b = bench.pct_change().dropna()
        j = r.index.intersection(b.index)
        if len(j) > 60:
            x, y = b.loc[j].values, r.loc[j].values
            out["beta"] = float(np.polyfit(x, y, 1)[0])
            out["beta_n"] = len(j)
            out["beta_corr"] = float(np.corrcoef(x, y)[0, 1])

    return out


# --------------------------------------------------------------- rf source
def french_rf() -> pd.Series:
    """Ken French daily 1-month T-bill -- the only daily rf reaching 1926."""
    import kd_data
    return kd_data.load_daily(verbose=False)["rf"]


if __name__ == "__main__":
    ser = tf_load.load_all()
    rf = french_rf()
    print()
    for tic, nav in ser.items():
        m = compute(nav, rf=rf)
        e = tf_load.EXPECTED[tic]
        print(f"{e['label']:<12} cagr {m['cagr']*100:6.2f} (tgt {e['cagr']*100:5.2f})"
              f"  vol {m['vol']*100:6.2f} (tgt {e['vol']*100:5.2f})"
              f"  mdd {m['max_dd']*100:7.2f} (tgt {e['max_dd']*100:6.2f})"
              f"  ulcer {m['ulcer']:6.2f} (tgt {e['ulcer']:5.2f})")
