# Metric conventions

Defined once, in `portfolio_suite\common\metrics.py` (moved from `ec_metrics.py` on
2026-09-23). Used by [[efficient-core-9060]], [[portfolio-dashboard]], [[reconstructions]], the
backtester and `testfolio_check`. The Kelly study ([[scv-leverage-analysis]]) keeps its own
per-observation set in `kd_kelly.py`. The two agree where they overlap, and the dashboard
re-scores everything through `common.metrics`.

**testfolio's conventions** are one flag away: `ppy=TESTFOLIO_PPY` (a fixed 252) or
`metrics.testfolio_table()`, which gives their full summary-table columns (ulcer in percent,
UPI on arithmetic excess return). See [[testfolio-cross-check]]. The backtester CLI prints in
these conventions.

## The conventions

| Metric | Definition | Gotcha |
|---|---|---|
| **CAGR** | Geometric, over the **true calendar span** — `(1+r).prod() ** (1/years) − 1` where `years = (last − first).days / 365.25` | Not `periods / ppy`. This is why it reconciles exactly with a wealth chart. |
| **Volatility** | `std(ddof=1) × √ppy`, on **total** returns | `ppy` is inferred from the index, not assumed to be 252. |
| **Sharpe** | On **excess** returns over the supplied risk-free series | Never on total returns. |
| **Sortino** | `mean(excess) × ppy / downside_dev`, MAR = rf | Threshold is **zero excess**, not zero total return. |
| **Downside deviation** | `√(mean(min(excess,0)²)) × √ppy` | Divides by the **full** count, not the count of negatives. |
| **Max drawdown** | Minimum of `NAV / NAV.cummax() − 1`, on **daily** total-return NAV | Monthly data gives a shallower number — see below. |
| **Calmar** | `CAGR / abs(MaxDD)` | |
| **Worst / best year** | Worst complete **calendar** year | Partial first and last years are dropped, so the figure is comparable across strategies with different start dates. |

## Observations per year is computed, never assumed

```python
def periods_per_year(idx):
    years = (idx[-1] - idx[0]).days / 365.25
    return (len(idx) - 1) / years
```

This matters more than it looks. The Kelly study's sample runs at **262.78 obs/year**, not
252, because the NYSE traded Saturdays until 1952. Hardcoding 252 would misannualise a
century of volatility by about 2%.

## Daily vs monthly drawdown

The dashboard computes **metric tables from daily data** and **draws charts from a monthly
panel**. A max drawdown in a table is therefore deeper than the same drawdown read off a
chart — a month-end series cannot see an intra-month trough. This is a real difference, not
a rounding artifact, and it is footnoted on the page rather than reconciled.

The drawdown chart additionally resets its peak at the **window start**, so selecting a
shorter window shows shallower drawdowns for the same series. Both behaviours are intended.

## Risk-free rate

USD 1-month T-bill throughout. Each study carries its own daily series (`rf` in both panels)
and the dashboard uses the study's own rather than splicing them — they agree closely over
the overlap but are sourced differently (Ken French `RF` vs the Efficient Core panel's `rf`).

## Links

- [[data-schemas]] — where these values land on disk.
- [[portfolio-dashboard]] · [[efficient-core-9060]] · [[scv-leverage-analysis]]
