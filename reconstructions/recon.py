"""
recon.py -- reconstructions of real leveraged / "return stacked" ETFs on the
common.backtest engine, each validated against the live fund.

For every fund two simulations run:

  live     the fund's own structure built from ETF proxies (SPY, EFA, EEM, GLD,
           DBMF, ...) with each proxy's expense ratio added back (the fund holds
           the underlying, not the ETF), over the fund's life, compared day by
           day with the fund's real total return. The CAGR gap and tracking
           error say whether the structure is right.
  history  the same structure on the longest research series available
           (Ken French indices, synthetic Treasury ladders, testfolio sims), so
           the validated structure can be looked at across decades.

STRUCTURES are taken from each fund's prospectus. TERs marked (verify) were not
re-read from a current prospectus for this version; the live gap absorbs any
error in them and is the check.

    python reconstructions/recon.py            all funds
    python reconstructions/recon.py NTSX GDE   selected funds

Writes reconstructions/output/<TICKER>.json and recon_summary.csv.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

SUITE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SUITE))
sys.path.insert(0, str(SUITE / "efficient_core"))

import ec_data as D                                              # noqa: E402
from common import assets, manifest, metrics as M, paths         # noqa: E402
from common import leverage as LV                                # noqa: E402
from common.backtest import Leg, backtest, on_calendar           # noqa: E402

OUT = paths.RECON_OUT
EC_REBAL = (2, 5, 8, 11)      # the WisdomTree Efficient Core schedule (ec_portfolios)

# Expense ratios of the ETF proxies, added back to their returns.
PROXY_ER = {"SPY": 0.000945, "EFA": 0.0032, "EEM": 0.0070, "GLD": 0.0040,
            "VT": 0.0006, "DBMF": 0.0085}


# --------------------------------------------------------------------------
# building blocks
# --------------------------------------------------------------------------
def dt_of(idx: pd.DatetimeIndex) -> pd.Series:
    return pd.Series(idx, index=idx).diff().dt.days.fillna(1) / 365.0


def proxy(ticker: str) -> pd.Series:
    """ETF total return with its own expense ratio added back."""
    r = assets.load(ticker)
    return r + PROXY_ER.get(ticker, 0.0) * dt_of(r.index)


def excess(r: pd.Series, over: str = "bill") -> pd.Series:
    """Total return -> excess return: what a futures position earns.
    over="bill"       for a fund whose return already includes T-bill collateral
                      income (DBMF): stripping the bill leaves the trend P&L.
    over="fed_funds"  for a spot holding (GLD) replaced by futures, whose price
                      embeds financing at an overnight rate (common/leverage.py)."""
    bill = assets.bill_on(r.index)
    if over == "fed_funds":
        bill = LV.benchmark_on(r.index, bill, "bill_3m")
    return (r - bill).dropna()


def borrow_on(cal: pd.DatetimeIndex) -> pd.Series:
    """What a loan costs per period before any spread: fed funds, accrued."""
    return LV.benchmark_on(cal, assets.bill_on(cal), "bill_3m")


def ust_ladder_fut() -> pd.Series:
    return assets.load("UST_LADDER_FUT")


@dataclass
class Fund:
    ticker: str
    name: str
    structure: str
    ter: float
    live_legs: Callable[[], dict]
    history_legs: Callable[[], dict] | None = None
    history_note: str = ""
    rebalance: object = EC_REBAL
    band: float | None = 0.05
    inception: str = "2000-01-01"
    assumptions: dict = field(default_factory=dict)


def with_cash(legs: dict, cal_from: str) -> dict:
    """Add the residual cash leg (bill) sized so funded weights sum to 1."""
    funded = sum(l.weight for l in legs.values() if l.funded)
    ref = legs[cal_from].returns
    legs["cash"] = Leg(assets.bill_on(ref.index), 1.0 - funded)
    return legs


# --------------------------------------------------------------------------
# the funds
# --------------------------------------------------------------------------
def _stack(equity: Callable[[], pd.Series], overlay: Callable[[], pd.Series],
           w_eq: float, w_ov: float):
    """Funded equity + an unfunded overlay + residual bills, all on the
    equity's trading calendar."""
    def legs():
        eq = equity().dropna()
        ov = on_calendar(overlay(), eq.index)
        return with_cash({"equity": Leg(eq, w_eq),
                          "overlay": Leg(ov, w_ov, funded=False)}, "equity")
    return legs


def _efficient_core(equity: Callable[[], pd.Series], w_eq=0.90, w_fut=0.60):
    return _stack(equity, ust_ladder_fut, w_eq, w_fut)


def _letf(L: float, equity: Callable[[], pd.Series]):
    def legs():
        eq = equity().dropna()
        return {"equity": Leg(eq, L),
                "cash": Leg(borrow_on(eq.index), 1.0 - L,
                            spread=LV.PRESETS["letf"].spread)}
    return legs


FUNDS = [
    Fund("NTSX", "WisdomTree U.S. Efficient Core",
         "0.90 US large-cap + 0.60 UST futures (2/5/10/30y ladder) + 0.10 bills",
         ter=0.0020, inception="2018-08-02",
         live_legs=_efficient_core(lambda: proxy("SPY")),
         history_legs=_efficient_core(lambda: assets.load("US_MKT")),
         history_note="US equity = Ken French US market (1962+, ends 2026-04)"),
    Fund("NTSI", "WisdomTree International Efficient Core",
         "0.90 developed ex-US equity + 0.60 UST futures ladder + 0.10 bills",
         ter=0.0026, inception="2021-05-21", assumptions={"ter": "0.26% (verify)"},
         live_legs=_efficient_core(lambda: proxy("EFA")),
         history_legs=_efficient_core(lambda: assets.load("DM_EXUS")),
         history_note="equity = Ken French Developed ex-US (1990+)"),
    Fund("NTSE", "WisdomTree Emerging Markets Efficient Core",
         "0.90 emerging-market equity + 0.60 UST futures ladder + 0.10 bills",
         ter=0.0032, inception="2021-05-21", assumptions={"ter": "0.32% (verify)"},
         live_legs=_efficient_core(lambda: proxy("EEM")),
         history_legs=_efficient_core(lambda: proxy("EEM")),
         history_note="equity = EEM (2003+); Ken French has no daily EM file"),
    Fund("GDE", "WisdomTree Efficient Gold Plus Equity Strategy",
         "0.90 US large-cap + 0.90 gold futures + 0.10 bills",
         ter=0.0020, inception="2022-03-18",
         live_legs=_stack(lambda: proxy("SPY"), lambda: excess(proxy("GLD"), over="fed_funds"), 0.90, 0.90),
         history_legs=_stack(lambda: assets.load("US_MKT"), lambda: excess(proxy("GLD"), over="fed_funds"),
                             0.90, 0.90),
         history_note="gold = GLD (2004+) as excess return over fed funds"),
    Fund("RSSB", "Return Stacked Global Stocks & Bonds",
         "1.00 global equity + 1.00 UST futures ladder",
         ter=0.0036, inception="2023-12-05", assumptions={"ter": "0.36% (verify)"},
         live_legs=_stack(lambda: proxy("VT"), ust_ladder_fut, 1.00, 1.00),
         history_legs=_stack(lambda: assets.load("DM_MKT"), ust_ladder_fut, 1.00, 1.00),
         history_note="equity = Ken French Developed (no EM before VT exists)"),
    Fund("RSST", "Return Stacked U.S. Stocks & Managed Futures",
         "1.00 US large-cap + 1.00 managed-futures trend overlay",
         ter=0.0099, inception="2023-09-05",
         assumptions={"ter": "0.99% (verify)",
                      "trend": "DBMF (live) / testfolio DBMFSIM (history) as the trend "
                               "leg; RSST runs its own trend model"},
         live_legs=_stack(lambda: proxy("SPY"), lambda: excess(proxy("DBMF")), 1.00, 1.00),
         history_legs=_stack(lambda: assets.load("US_MKT"),
                             lambda: excess(assets.load("TF_DBMFSIM")), 1.00, 1.00),
         history_note="trend = testfolio DBMFSIM (2000+)"),
    Fund("SSO", "ProShares Ultra S&P 500 (2x daily)",
         "2.0x S&P 500, reset daily, swap spread = letf preset",
         ter=0.0091, inception="2006-06-21", rebalance="daily", band=None,
         live_legs=_letf(2.0, lambda: proxy("SPY")),
         history_legs=_letf(2.0, lambda: assets.load("US_MKT")),
         history_note="US market 1954+, borrowing at fed funds + fitted LETF spread"),
    Fund("UPRO", "ProShares UltraPro S&P 500 (3x daily)",
         "3.0x S&P 500, reset daily, swap spread = letf preset",
         ter=0.0091, inception="2009-06-25", rebalance="daily", band=None,
         live_legs=_letf(3.0, lambda: proxy("SPY")),
         history_legs=_letf(3.0, lambda: assets.load("US_MKT")),
         history_note="US market 1954+, borrowing at fed funds + fitted LETF spread"),
]


# --------------------------------------------------------------------------
# running and scoring
# --------------------------------------------------------------------------
def simulate(fund: Fund, legs: dict, start=None) -> pd.Series:
    res = backtest(legs, rebalance=fund.rebalance, band=fund.band, ter=fund.ter,
                   floor=1e-12)
    r = res["ret"]
    return r.loc[start:] if start else r


def live_check(fund: Fund) -> dict:
    real = assets.load(fund.ticker).loc[fund.inception:]
    legs = fund.live_legs()
    synth = simulate(fund, legs, start=real.index[0])
    j = real.index.intersection(synth.index)
    lost = len(real.loc[:synth.index[-1]]) - len(j)
    if lost > 5:
        raise ValueError(f"{lost} fund trading days missing from the model calendar")
    a, b = real.loc[j], synth.loc[j]
    wk = lambda s: (1 + s).resample("W-FRI").prod() - 1
    g = a - b
    yrs = (j[-1] - j[0]).days / 365.25
    return dict(start=str(j[0].date()), end=str(j[-1].date()), years=round(yrs, 2),
                n_days=len(j),
                cagr_real=float((1 + a).prod() ** (1 / yrs) - 1),
                cagr_synth=float((1 + b).prod() ** (1 / yrs) - 1),
                gap_pp_per_yr=float(((1 + a).prod() ** (1 / yrs) - (1 + b).prod() ** (1 / yrs)) * 100),
                tracking_error=float(g.std(ddof=1) * np.sqrt(252)),
                corr_daily=float(a.corr(b)), corr_weekly=float(wk(a).corr(wk(b))),
                vol_real=float(a.std(ddof=1) * np.sqrt(252)),
                vol_synth=float(b.std(ddof=1) * np.sqrt(252)),
                maxdd_real=M.max_drawdown(a), maxdd_synth=M.max_drawdown(b))


def history(fund: Fund) -> dict | None:
    if fund.history_legs is None:
        return None
    r = simulate(fund, fund.history_legs())
    tbl = M.testfolio_table(r, assets.load("CASH"))
    tbl["worst_year"], tbl["best_year"], tbl["worst_year_when"], tbl["best_year_when"] = \
        M.worst_best_year(r)
    tbl["note"] = fund.history_note
    return tbl, r


def run(fund: Fund) -> dict:
    print(f"\n== {fund.ticker}  {fund.name}\n   {fund.structure}")
    out = dict(ticker=fund.ticker, name=fund.name, structure=fund.structure,
               ter=fund.ter, rebalance=str(fund.rebalance), band=fund.band,
               assumptions=fund.assumptions)
    try:
        lv = live_check(fund)
        out["live"] = lv
        print(f"   live  {lv['start']}..{lv['end']} ({lv['years']}y)  real {lv['cagr_real']*100:6.2f}%"
              f"  model {lv['cagr_synth']*100:6.2f}%  gap {lv['gap_pp_per_yr']:+.2f}pp/yr"
              f"  TE {lv['tracking_error']*100:.2f}%  weekly corr {lv['corr_weekly']:.3f}")
    except Exception as exc:
        out["live_error"] = f"{type(exc).__name__}: {exc}"
        print(f"   live  unavailable: {out['live_error']}")
    h = history(fund)
    if h is not None:
        tbl, r = h
        out["history"] = tbl
        mo = (1 + r).resample("ME").prod() - 1
        out["history_monthly"] = dict(dates=[str(d.date()) for d in mo.index],
                                      ret=[round(float(v), 6) for v in mo])
        print(f"   hist  {tbl['start']}..{tbl['end']}  CAGR {tbl['cagr']*100:6.2f}%  "
              f"vol {tbl['vol']*100:5.1f}%  maxDD {tbl['max_dd']*100:6.1f}%  "
              f"Sharpe {tbl['sharpe']:.2f}   ({fund.history_note})")
    return out


def investable_scv() -> dict:
    """How much of the Ken French SMALL HiBM return did real small-value funds
    capture? The gap is the SCV_HAIRCUT the Kelly study can apply."""
    kf = assets.load("US_SCV")
    out = {}
    for tic in ("DFSVX", "AVUV"):
        try:
            f = assets.load(tic)
        except Exception as exc:
            out[tic] = dict(error=str(exc))
            continue
        j = f.index.intersection(kf.index)
        yrs = (j[-1] - j[0]).days / 365.25
        cf = (1 + f.loc[j]).prod() ** (1 / yrs) - 1
        ck = (1 + kf.loc[j]).prod() ** (1 / yrs) - 1
        out[tic] = dict(start=str(j[0].date()), end=str(j[-1].date()), years=round(yrs, 2),
                        cagr_fund=float(cf), cagr_kf=float(ck),
                        drag_pp_per_yr=float((ck - cf) * 100),
                        corr_weekly=float(((1 + f.loc[j]).resample("W-FRI").prod() - 1).corr(
                            (1 + kf.loc[j]).resample("W-FRI").prod() - 1)))
        print(f"   {tic}: {out[tic]['start']}..{out[tic]['end']}  fund {cf*100:.2f}%  "
              f"KF SMALL HiBM {ck*100:.2f}%  drag {out[tic]['drag_pp_per_yr']:+.2f}pp/yr")
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    OUT.mkdir(parents=True, exist_ok=True)
    funds = [f for f in FUNDS if not argv or f.ticker in argv]
    rows = []
    for f in funds:
        res = run(f)
        (OUT / f"{f.ticker}.json").write_text(json.dumps(res, indent=1, default=str),
                                              encoding="utf-8")
        lv, h = res.get("live", {}), res.get("history", {})
        rows.append(dict(ticker=f.ticker, name=f.name, structure=f.structure, ter=f.ter,
                         live_start=lv.get("start"), live_years=lv.get("years"),
                         live_cagr_real=lv.get("cagr_real"), live_cagr_model=lv.get("cagr_synth"),
                         live_gap_pp=lv.get("gap_pp_per_yr"), live_te=lv.get("tracking_error"),
                         live_corr_weekly=lv.get("corr_weekly"),
                         hist_start=h.get("start"), hist_end=h.get("end"),
                         hist_cagr=h.get("cagr"), hist_vol=h.get("vol"),
                         hist_maxdd=h.get("max_dd"), hist_sharpe=h.get("sharpe"),
                         hist_note=f.history_note))
    if not argv:
        print("\n== Investable small-cap value vs Ken French SMALL HiBM")
        (OUT / "investable_scv.json").write_text(json.dumps(investable_scv(), indent=1),
                                                 encoding="utf-8")
        pd.DataFrame(rows).to_csv(OUT / "recon_summary.csv", index=False)
        manifest.record(OUT, "recon.py", funds=[f.ticker for f in funds],
                        letf_spread=LV.LETF_SPREAD, borrow_benchmark="fed funds",
                        **D.EC_CONFIG)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
