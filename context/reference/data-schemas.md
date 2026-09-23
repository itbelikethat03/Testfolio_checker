# Data schemas

Exact column names and units for the output files the studies write. Units are **decimal
fractions** (0.0927 = 9.27%) unless a column name ends in `_pp` (percentage points) or is a
`p_*` / `win_rate` probability (0–1). Drawdowns are negative. Kelly and leverage are plain
multipliers.

Paths below are relative to `portfolio_suite\`. Every output folder also holds a
`_manifest.json` (script → run time + configuration; see [[portfolio-dashboard]]).

## Efficient Core — `efficient_core\output\`

### `panel_global_daily.csv` — the master panel, 9,414 rows, 1990-07-03 → 2026-07-31

```
date, equity_dm, rf, cash, futures, duration, n_ccy, scv_dm,
rec9060, w_equity, w_bond, lev15, acwi, ntsg, equity_dm_exc
```

| Column | Meaning |
|---|---|
| `equity_dm` | Developed-market equity total return, USD (Ken French) |
| `rf` | USD 1-month T-bill |
| `cash` | Four-currency collateral sleeve |
| `futures` | **Excess** return on 1.0 notional of the bond ladder |
| `duration` | Sleeve duration, years |
| `n_ccy` | 2 / 3 / 4 — currencies live that day (GBP curve starts 1993, EUR 2004) |
| `scv_dm` | Developed small-cap value |
| `rec9060` | Reconstructed fund, net of 0.27%/yr |
| `w_equity`, `w_bond` | **Drifted** weights, not the 0.90/0.60 targets |
| `lev15` | 1.5× equity, borrowing 0.5 in USD at fed funds + 0.30% (since 2026-09-23) |
| `acwi`, `ntsg` | Actual ETF returns — **mostly NaN**. ACWI from 2008-03-31, NTSG from 2024-11-11 |

### Table 1 family — identical 15-column schema

`table1_common_window.csv` · `table1_own_windows.csv` · `table1_ntsg_window.csv`

```
strategy, start, end, years, CAGR, vol, Sharpe, Sortino, MaxDD, Calmar,
downside_dev, worst_year, worst_year_when, best_year, best_year_when
```

Strategy labels contain commas and are therefore quoted in the CSV:
`Global equities, All World (ACWI)` · `Developed equities (index NTSG tracks)` ·
`Developed equities, 1.5x levered` · `Developed small-cap value` · `Reconstructed 90/60`.

### Others

| File | Shape | Notes |
|---|---|---|
| `table_annualised_windows.csv` | 4 rows | **Wide** — strategy names are column headers. Empty cell = n/a |
| `table_subperiods.csv` | 4 rows | `sub_period, equities, p9060, bond_leg, vol_9060, vol_eq, diff_pp` |
| `crisis_returns.csv` | 6 rows | **Cumulative** returns per episode, one column per strategy |
| `regimes.csv` | 7 rows | Returns **annualised within bucket**. Labels have **two spaces** after the letter: `A  Equities up (bull months)` |
| `long_us_periods.csv` | 7 rows | 1928–2025 by era. `diff_pp` in pp |
| `long_us_annual.csv` | 98 rows | `year, stocks, bills, bonds, p9060, lev15, diff, term_premium, erp, infl`. **`diff` here is a decimal, not pp.** `infl` NaN before 1948 |
| `robustness.csv` | 7 rows | Modelling variants |
| `financing_sensitivity_historical.csv` | 5 rows | Spreads 0, 0.0025, 0.005, 0.01, 0.02 |
| `financing_sensitivity_forward.csv` | 5 rows | Financing 0.02 → 0.06 |
| `sensitivity_return_grid.csv` | 5 rows | **First column header is EMPTY.** Row keys `bond_0.0`…`bond_0.06`, cols `eq_0.04`…`eq_0.1`. Values are **pp/yr** |
| `sensitivity_correlation.csv` | 6 rows | ρ ∈ {−0.6, −0.3, 0, 0.3, 0.6, 0.9} |
| `rolling_differences.csv` | 9,154 rows | `date, diff_1y, diff_3y, diff_5y, diff_10y` — decimals, leading NaNs by window |
| `rolling_correlation.csv` | 8,659 rows | `date, corr_3y` |
| `montecarlo_A_global_monthly.csv` / `_B_us_annual.csv` | 4 rows each | 29 columns, horizons 10/20/30/40 |
| `montecarlo_summary.json` | — | **Identical data, easier to consume.** Keys `A_global_monthly`, `B_us_annual` |
| `montecarlo_sensitivity.csv` | 7 rows | Term-premium shifts −0.020 → +0.010. At shift 0 the `p_win` values come from an 8,000-path sweep and differ slightly from the 20,000-path table (0.7039 vs 0.6988 at 10y) |
| `headline_stats.json` | flat | Ideal for KPI tiles |
| `montecarlo_paths.npz` | 6 MB | 48 arrays, key `f"{tag}_{h}_{k}"`, 20,000 floats each. **Not used by the dashboard** |

## Kelly / best days — `scv_leverage\kelly_bestdays\`

Since 2026-09-23:

- `phase79_montecarlo.csv` has schemes `block20_futures` / `block20_broker` / `block20_letf`
  (they replace `block20_cost`).
- `phase14_sensitivity.csv` variants are `cost_futures` / `cost_broker` / `cost_letf` (they
  replace `cost_40bp`).
- New files `phase13_leverage_sweep_costs.csv` and `phase13_optimal_leverage_costs.csv` have a
  `financing` column. The frictionless files keep their old schema.
- `kd_data.load_daily()` adds `gap` (fed-funds minus bill accrual) and `ff_acc`, returned by
  `series_frame(..., with_gap=True)`.

| File | Shape | Notes |
|---|---|---|
| `phase346_removal.csv` | 54 rows, 25 cols | Keyed `series ∈ {mkt,scv}` × `mode ∈ {best,worst,both}` × `X ∈ {0,1,5,10,20,50,100,200,500}`. `n_removed = 2X` when mode is `both`. `kurt` is **excess** kurtosis |
| `removed_days_log.csv` | 80 rows | `series, kind, rank, date, total_ret` — the top and bottom 20 days per series |
| `phase5_random_control.csv` | 16 rows | `treat_pctile_in_null` is a **percentage 0–100**, not a fraction. `kelly_emp` values are snapped to the 0.01 f-grid so treatment and null score identically |
| `phase5_random_draws.csv` | 32,000 rows | Raw null draws, for violin plots |
| `phase79_montecarlo.csv` | 280 rows, 30 cols | `frac` is **empty (NaN)** when `regime == "fixed"`. `f_base` = Kelly from untouched sample; `f_stressed` = re-estimated on X-removed. `p_ruin_99` = P(terminal wealth < $0.01) |
| `phase13_leverage_sweep.csv` | 560 rows | f = 0.1…4.0 step 0.1 × X ∈ {0,5,10,20,50,100,200} × 2 series. `mean_log_growth` is mean log terminal wealth ÷ 25 |
| `phase13_optimal_leverage.csv` | 14 rows | **`f_p5` is degenerate — do not use.** Binds on the 0.10× grid floor from X = 20 |
| `phase12_context.json` | — | `estimation_error`, `growth_share`, `era_stability`. Drop keys are **strings** (`"20"`, not `20`) |
| `phase12_clustering.json` | — | X ∈ {10,20,50,100}; first two fields are fractions 0–1 |
| `phase8_diagnostics.json` | — | `min_pct` in **percent** (e.g. −17.44) |
| `phase79_terminal_wealth.npz` | 2.4 MB | Key format `"{series}\|{X}\|{level}"`, `(20000,) float32`. Only `block20` paths. **Not used by the dashboard** |

## Reconstructions — `reconstructions\output\`

| File | Notes |
|---|---|
| `<TICKER>.json` | `live` (real vs model: CAGRs, `gap_pp_per_yr` = real − model, TE, weekly corr), `history` (testfolio-convention table), `history_monthly`, and `vs_testfolio` for SSO/UPRO (overall + `eras`) |
| `recon_summary.csv` | one row per fund; `tf_*` columns for the testfolio comparison |
| `leverage_validation.json` | LETF fits: `rate_fits` (four variants), `rate_sensitive`, `model_errors_by_regime` (model − real, decimal) |
| `investable_scv.json` | DFSVX / AVUV vs KF `SMALL HiBM`, `drag_pp_per_yr` |

## Raw inputs — `shared_data\`

- `F-F_Research_Data_Factors_daily.csv`: `date,Mkt-RF,SMB,HML,RF`, values in **percent**.
- `ff6\6_Portfolios_2x3_Daily.csv` and `ff6\6_Portfolios_2x3_CSV.zip` (the monthly file, for the
  daily-vs-monthly check). Ken French codes missing data as −99.99 / −999. **All Ken French
  parsing goes through `common/ff.py`**, which finds blocks by title. Do not use `skiprows` /
  `nrows`.
- `F-F_Research_Data_Factors_CSV.zip`: the monthly market file.
- `histretSP.xls`: Damodaran annual returns.
- `testfolio_data\*.csv`: `date,value` dollar paths, identified by content in `tf_load.py`.
  SSOSIM / UPROSIM go through `load_letf_sims()`; VEASIM is read by `ec_ntsd.py`.
- FRED series (incl. `DFF` fed funds, `DTB3` stored as raw discount quotes and converted to
  bond-equivalent on load) and Yahoo prices are cached in `efficient_core\data_cache\`.

## Links

- [[metric-conventions]] · [[portfolio-dashboard]] · [[efficient-core-9060]] · [[scv-leverage-analysis]]
