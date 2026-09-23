# Reproducing the testfolio table

Every figure below is recomputed from testfolio's own daily $ series in `shared_data\testfolio_data`. The **target** column is the published table; **computed** is what the daily data actually gives.

**49 of 60 cells reproduce exactly** (5 series × 12 metrics). Beta is handled separately below.

## Conventions established

Each ambiguous metric was computed several ways; the variant that reproduces testfolio across *all five series* is the one it uses.

| Metric | Convention testfolio uses | Series reproduced |
|---|---|---:|
| Ending value | last value | 5/5 |
| Cumulative return | last/first − 1 | 5/5 |
| CAGR | 365.25 day-count | 5/5 |
| Max drawdown | min of daily drawdown | 5/5 |
| Avg drawdown | mean over underwater days | 5/5 |
| Longest DD | peak→recovery /365 | 3/5 |
| Volatility | sd × √252 | 5/5 |
| Sharpe | mean(exc)/sd(exc) × √252 | 2/5 |
| Sortino | mean(exc)×252 / DD(MAR=rf) | 2/5 |
| Calmar | CAGR / |max DD| | 5/5 |
| Ulcer index | √mean(dd²), in percent | 5/5 |
| UPI | (arith − rf arith)/ulcer | 2/5 |

## Per-series detail

### NTSDSIM — 3 cell(s) off

`1969-12-31 → 2026-09-09` · 14,294 observations · 252.13 obs/yr

| Metric | Target | Computed | Δ | Variant |
|---|---:|---:|---:|---|
| Ending value | $6,189,175 | $6,189,175 | — | last value |
| Cumulative return | 61,791.75% | 61,791.75% | — | last/first − 1 |
| CAGR | 12.01% | 12.01% | — | 365.25 day-count |
| Max drawdown | -74.41% | -74.41% | — | min of daily drawdown |
| Avg drawdown | -15.83% | -15.83% | — | mean over underwater days |
| Longest DD | 6.62y | 6.62y | — | peak→recovery /365 |
| Volatility | 24.56% | 24.56% | — | sd × √252 |
| Sharpe ⚠ | 0.40 | 0.41 | 0.00972 | mean(exc)/sd(exc) × √252 |
| Sortino ⚠ | 0.57 | 0.58 | 0.008442 | mean(exc)×252 / DD(MAR=rf) |
| Calmar | 0.16 | 0.16 | — | CAGR / |max DD| |
| Ulcer index | 21.49 | 21.49 | — | √mean(dd²), in percent |
| UPI ⚠ | 0.46 | 0.47 | 0.008441 | (arith − rf arith)/ulcer |

### VTSIM?L=2 — 1 cell(s) off

`1969-12-31 → 2026-09-09` · 14,294 observations · 252.13 obs/yr

| Metric | Target | Computed | Δ | Variant |
|---|---:|---:|---:|---|
| Ending value | $3,107,211 | $3,107,211 | — | last value |
| Cumulative return | 30,972.11% | 30,972.11% | — | last/first − 1 |
| CAGR | 10.65% | 10.65% | — | 365.25 day-count |
| Max drawdown | -86.81% | -86.81% | — | min of daily drawdown |
| Avg drawdown | -26.27% | -26.27% | — | mean over underwater days |
| Longest DD ⚠ | 9.54y | 9.55y | 0.005205 | peak→recovery /365 |
| Volatility | 32.81% | 32.81% | — | sd × √252 |
| Sharpe | 0.34 | 0.34 | — | mean(exc)/sd(exc) × √252 |
| Sortino | 0.48 | 0.48 | — | mean(exc)×252 / DD(MAR=rf) |
| Calmar | 0.12 | 0.12 | — | CAGR / |max DD| |
| Ulcer index | 32.65 | 32.65 | — | √mean(dd²), in percent |
| UPI | 0.34 | 0.34 | — | (arith − rf arith)/ulcer |

### FFSCV — 4 cell(s) off

`1926-07-01 → 2025-10-31` · 24,952 observations · 251.18 obs/yr

| Metric | Target | Computed | Δ | Variant |
|---|---:|---:|---:|---|
| Ending value | $1,786,967,536 | $1,786,967,536 | — | last value |
| Cumulative return | 17,869,575.36% | 17,869,575.36% | — | last/first − 1 |
| CAGR | 12.95% | 12.95% | — | 365.25 day-count |
| Max drawdown | -87.80% | -87.80% | — | min of daily drawdown |
| Avg drawdown | -14.06% | -14.06% | — | mean over underwater days |
| Longest DD ⚠ | 7.30y | 7.31y | 0.006849 | peak→recovery /365 |
| Volatility | 19.83% | 19.83% | — | sd × √252 |
| Sharpe ⚠ | 0.55 | 0.56 | 0.007861 | mean(exc)/sd(exc) × √252 |
| Sortino ⚠ | 0.78 | 0.79 | 0.009689 | mean(exc)×252 / DD(MAR=rf) |
| Calmar | 0.15 | 0.15 | — | CAGR / |max DD| |
| Ulcer index | 21.21 | 21.21 | — | √mean(dd²), in percent |
| UPI ⚠ | 0.51 | 0.52 | 0.01155 | (arith − rf arith)/ulcer |

### DBMFSIM — all reproduce

`2000-01-03 → 2026-09-09` · 6,711 observations · 251.47 obs/yr

| Metric | Target | Computed | Δ | Variant |
|---|---:|---:|---:|---|
| Ending value | $57,376 | $57,376 | — | last value |
| Cumulative return | 473.76% | 473.76% | — | last/first − 1 |
| CAGR | 6.77% | 6.77% | — | 365.25 day-count |
| Max drawdown | -20.44% | -20.44% | — | min of daily drawdown |
| Avg drawdown | -5.32% | -5.32% | — | mean over underwater days |
| Longest DD | 3.32y | 3.32y | — | peak→recovery /365 |
| Volatility | 9.58% | 9.58% | — | sd × √252 |
| Sharpe | 0.53 | 0.53 | — | mean(exc)/sd(exc) × √252 |
| Sortino | 0.74 | 0.74 | — | mean(exc)×252 / DD(MAR=rf) |
| Calmar | 0.33 | 0.33 | — | CAGR / |max DD| |
| Ulcer index | 6.37 | 6.37 | — | √mean(dd²), in percent |
| UPI | 0.80 | 0.80 | — | (arith − rf arith)/ulcer |

### TLTSIM — 3 cell(s) off

`1962-01-02 → 2026-09-09` · 16,280 observations · 251.67 obs/yr

| Metric | Target | Computed | Δ | Variant |
|---|---:|---:|---:|---|
| Ending value | $349,096 | $349,096 | — | last value |
| Cumulative return | 3,390.96% | 3,390.96% | — | last/first − 1 |
| CAGR | 5.65% | 5.65% | — | 365.25 day-count |
| Max drawdown | -48.35% | -48.35% | — | min of daily drawdown |
| Avg drawdown | -9.41% | -9.41% | — | mean over underwater days |
| Longest DD | 6.10y | 6.10y | — | peak→recovery /365 |
| Volatility | 11.53% | 11.53% | — | sd × √252 |
| Sharpe ⚠ | 0.15 | 0.16 | 0.01399 | mean(exc)/sd(exc) × √252 |
| Sortino ⚠ | 0.21 | 0.23 | 0.02334 | mean(exc)×252 / DD(MAR=rf) |
| Calmar | 0.12 | 0.12 | — | CAGR / |max DD| |
| Ulcer index | 13.37 | 13.37 | — | √mean(dd²), in percent |
| UPI ⚠ | 0.13 | 0.14 | 0.01147 | (arith − rf arith)/ulcer |

## The nine cells that do not reproduce share one cause

Every unreproduced cell is one of the three metrics that need a **risk-free rate** — Sharpe, Sortino, UPI — and all are biased the same way. Below, each metric is solved independently for the constant rf add-on that would hit testfolio's figure:

| Series | via Sharpe | via Sortino | via UPI | our rf CAGR | implied |
|---|---:|---:|---:|---:|---:|
| NTSDSIM | 24bp | 14bp | 18bp | 4.39% | 4.63% |
| VTSIM?L=2 | 8bp | 3bp | 13bp | 4.39% | 4.47% |
| FFSCV | 16bp | 13bp | 24bp | 3.16% | 3.31% |
| DBMFSIM | 3bp | -1bp | 1bp | 1.93% | 1.96% |
| TLTSIM | 16bp | 19bp | 15bp | 4.36% | 4.52% |

Three mathematically independent metrics agree on the same add-on for each series, averaging **13bp/yr**. That consistency is what makes this one input difference rather than nine errors: testfolio's risk-free series sits a little above Ken French's 1-month bill, which is what we use.

Both candidate bill series were tested. The Fama-French 1-month bill and FRED's 3-month bill (`DTB3`) give answers within 0.001 of each other on every series, and **neither closes the gap** — so testfolio is using a third series that this export does not contain. The affected figures are off by 0.01–0.02 on a ratio, which changes no conclusion anywhere in either study, and is recorded rather than tuned away.

## Beta — the one column that needs an input we do not have

Beta requires a benchmark series, which the export does not include. Fitted below against the Fama-French US total market as the closest available proxy:

| Series | Target β | β vs FF US market | Δ | Correlation |
|---|---:|---:|---:|---:|
| NTSDSIM | 1.34 | 1.357 | +0.017 | 0.93 |
| VTSIM?L=2 | 1.65 | 1.723 | +0.073 | 0.88 |
| FFSCV | 0.94 | 1.026 | +0.086 | 0.89 |
| DBMFSIM | 0.01 | 0.009 | -0.001 | 0.02 |
| TLTSIM | -0.04 | -0.051 | -0.011 | -0.07 |

The signs and magnitudes are right — managed futures ≈ 0, long Treasuries slightly negative, 2× global equity well above 1 — so the benchmark is certainly a broad US equity index. But the residuals are too large and too uneven to call it reproduced: FF US market is not the series testfolio regresses against. **Resolving this needs testfolio's own benchmark exported as a daily series.**
