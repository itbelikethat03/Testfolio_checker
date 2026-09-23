# Kelly vs. best-days-removed — methodology and assumptions

Scripts live one level up (`kd_*.py`); every output in this folder is produced by them.
Run order:

```
python kd_phase2_validate.py     # data definition checks
python kd_phase346_removal.py    # baseline + best/worst/both removal
python kd_phase5_control.py      # random-removal null distribution
python kd_phase8_diag.py         # resampling-scheme diagnostics
python kd_phase79_mc.py          # Monte Carlo  (slow, ~15 min)
python kd_phase12_context.py     # estimation error, growth share, era stability
python kd_phase12_cluster.py     # when do the best days actually happen
python kd_phase13_optlev.py      # optimal-leverage sweep  (slow, ~8 min)
python kd_phase14_fractions.py   # fractional Kelly vs best-day removal (~5 min)
python kd_phase11_validate.py    # validation suite (run last)
python kd_charts.py              # all figures
```

## Data

| | Source | Definition |
|---|---|---|
| Broad market | `F-F_Research_Data_Factors_daily.csv` (202604 CRSP) | `Mkt-RF` = daily **excess** return of the CRSP value-weighted total market. Total = `Mkt-RF + RF`. |
| Small-cap value | `ff6/6_Portfolios_2x3_Daily.csv`, *Average Value Weighted Returns — Daily* block, column `SMALL HiBM` (202606 CRSP) | daily **total** (not excess) value-weighted return of the small-ME / high-BE/ME portfolio. Excess = `SMALL HiBM − RF`. |
| Risk-free | same factors file, `RF` | daily simple T-bill rate. |

Merged inner-join on date: **1926-07-01 → 2026-04-30, n = 26,233 daily observations, 99.83 years.**

Both files are parsed by `common/ff.py`, which finds each block by its title rather than
by row numbers. The series are identical to the earlier `skiprows=18, nrows=26274` parse.
Compounded to month-end, the daily `SMALL HiBM` matches Ken French's own monthly file
(correlation 0.9999; checked in `kd_phase2_validate.py`). The source is set by
`kd_data.SCV_SOURCE` (`"kf"` here; `"testfolio"` swaps in testfolio's FFSCV, a different
portfolio).

## Return-definition rules followed

* Kelly is computed **only on excess returns**; total returns are used only for
  NAV, CAGR, drawdown and "best day" ranking.
* `Mkt-RF` is never mixed with total market returns, and no long-short factor
  (SMB, HML) is used anywhere.
* French codes missing data as `-99.99 / -999`; those rows are dropped (none occur
  in the merged window).

## Kelly estimators

For excess return `x_t` and risk-free `rf_t`, wealth relative is
`W_{t+1}/W_t = 1 + rf_t + f·x_t`.

1. **Gaussian** `f* = μ/σ²` — identical to `compute_kelly_metrics()` in
   `backtest.py` / `mf_and_kelly.py`, kept for comparability.
2. **Quadratic** `f* = μ/E[x²]` — exact maximiser of the 2nd-order expansion.
3. **Empirical log-optimal** (headline) `f* = argmax_f mean(log(1 + rf + f·x))`,
   constrained to `f ≥ 0` and to the no-bankruptcy region
   `1 + rf_t + f·x_t > 0 ∀t`.

All three are frequency-invariant under i.i.d. returns, so daily estimates are
directly comparable with the monthly estimates in `mf_and_kelly.py`.

## Annualisation

The sample's own **262.78 observations per year** is used, not 252 — the NYSE traded
Saturdays until 1952, so 252 would misstate the full-sample CAGR. With 262.78, the
per-observation geometric mean scales back exactly to the calendar CAGR (verified in
`kd_phase11_validate.py`).

## The counterfactual

Removing X days does not shorten the horizon — it defines a **modified return
distribution**. All annualised statistics are per-observation moments scaled by
262.78, i.e. "the long-run behaviour of an investor drawing from the reduced
distribution". Max drawdown is the drawdown of the retained days re-concatenated in
chronological order.

Days are ranked by **total** daily return.

## Monte Carlo

* Moving-block bootstrap, **block = 20 trading days** (the default already used by
  `lev25_montecarlo.py`); `(x_t, rf_t)` resampled with the same index so the
  historical return/rate pairing survives.
* Horizon 25 years = 6,569 trading days; 20,000 paths; fixed seeds.
* Robustness variants at X ∈ {0, 50}: i.i.d. bootstrap, block = 60, and the
  `futures` / `broker` / `letf` financing presets of `common/leverage.py`
  (schemes `block20_<preset>`). The financing schemes reuse the block-20 seed, so they
  re-score the same paths. The model is `W'/W = 1 + rf + f·x − max(f − 1, 0)·(gap + spread·dt) −
  TER·dt`, where gap is the day's effective-fed-funds-minus-bill accrual (borrow at fed
  funds, lend at the bill; 0.53pp/yr before fed funds exists in 1954).
* Sizing regimes: `full` (leverage set from the **untouched** history, then run in
  the stressed world) and `stressed` (leverage re-estimated on the reduced sample),
  plus fixed 1.0× and 2.0× benchmarks.

## Optimal-leverage sweep (addendum)

`kd_phase13_optlev.py` sweeps f from 0.1× to 4.0× in steps of 0.1 (5,000 paths per point,
block-20, seed 90210, X ∈ {0, 5, 10, 20, 50, 100, 200}) and reports four optima:

| Objective | Definition |
|---|---|
| `f_kelly` | argmax of daily `E[log(1 + rf + f·x)]` — analytic, no simulation |
| `f_growth` | argmax of **median** 25-year CAGR |
| `f_meanlog` | argmax of mean log terminal wealth |
| `f_budget` | largest f with `P(max drawdown ≤ −50%) ≤ 25%` |

The same bootstrap indices are reused across every f within a config, so the curves are
paired and the argmax is not chasing simulation noise. `f_kelly` and `f_growth` agreeing to
within one grid step is a cross-validation of the analytic and simulated routes.

A fifth objective, argmax of 5th-percentile CAGR, is computed but is **degenerate** — it
pushes toward cash and binds on the grid's 0.10× floor from X=20 onward. Reported, not used.

## Fractional Kelly vs best-day removal (Phase 14)

`kd_phase14_fractions.py` crosses three Kelly fractions (1, ½, ¼ × f*) with four datasets
(original, −10, −25, −100 best days). A finer X grid (0 … 500) is used only for the
equivalent-X interpolation.

* **Sizing.** f* = `kelly_emp` on the original full sample, applied unchanged to every dataset,
  so only the distribution differs. Portfolio return is `rf + f·x`, rebalanced daily and
  financed at rf.
* **Removal.** Days are ranked by unlevered total return on the full sample. Removing them
  means **dropping the observations**; the retained days keep their real dates and order.
  Annualised statistics use per-observation moments × the series' own apy. Final wealth is
  `(1+CAGR)^years` over the unchanged calendar span, so capital and period are identical in
  every scenario.
* **Three readings of "without the best days", kept distinct:**

  | Reading | What it means | Where it is reported |
  |---|---|---|
  | drop | a different distribution | primary |
  | 0% day | the raw product of retained days | `final_wealth_raw` |
  | cash day | removed dates kept, excess = 0, the portfolio earns rf | `cash_day` sensitivity |

  At X ≤ 100 of ~26,000 days they differ by ≤ 0.01pp of CAGR.
* **Similarity.** RMS of z-scored gaps across the 12 scenarios of a series, with equal
  weights. Three vectors, fixed before running:

  | Vector | Metrics |
  |---|---|
  | all | CAGR, vol, Sharpe, Sortino, max DD, Calmar, max-DD duration, log final wealth |
  | risk | vol, max DD, max-DD duration, worst month |
  | return | CAGR, Sharpe, Sortino, log final wealth |

* **Equivalent X.** For each metric, the first crossing of the Full-Kelly X-curve with the
  Half or Quarter value, by linear interpolation. It is reported as "none" when the target
  lies outside the curve's range. It measures equivalence and is not used to choose X.
* **Sensitivities:**
  * `walkforward`: month-end expanding-window f* on the scenario's own retained history,
    10-year warm-up, clipped to [0, 4].
  * `fixed_1936`: primary sizing on the walk-forward window.
  * `cash_day`: see the table above.
  * `cost_futures` / `cost_broker` / `cost_letf`: the `common/leverage.py` presets
    (fed funds + 0.30% / + 1.00% / + the spread fitted to SSO and UPRO on the borrowed portion; the
    letf preset adds a 0.91% TER on NAV).
* **Identity.** With constant f, Sharpe and Sortino are invariant to the fraction. The
  script asserts it rather than assuming it.

## Known limitations

1. **These are Fama-French research portfolios, not investable funds.** `SMALL HiBM`
   is value-weighted and gross of trading costs, spreads, taxes and fund fees, and
   it holds microcaps that are expensive or impossible to trade at scale. The prior
   `dfsvx_compare.py` work in this project put the DFSVX-implied drag at ≈1.09%/yr;
   **no cost drag is applied here**, so the level of every Kelly estimate is
   optimistic. The *shape* of the best-days curve is unaffected by a constant drag,
   but the intercept is not.
2. `SMALL HiBM` daily lag-1 autocorrelation is **+0.128** (vs +0.046 for the market)
   — microcap stale pricing. This inflates measured geometric growth relative to
   what a tradeable fund could capture, and biases the small-cap-value Kelly upward.
3. Block bootstrapping the *reduced* series creates ~X seams where deleted days used
   to be; with X = 200 out of 26,233 this is a minor distortion of local dependence.
4. Deleting the best days is a **full-sample, look-ahead operation** by construction.
   It is a counterfactual stress test, not a strategy and not a forecast.
5. Frictionless borrowing at the T-bill rate is assumed in the primary results.
   Real leverage costs more; the cost-adjusted MC variant bounds this.
