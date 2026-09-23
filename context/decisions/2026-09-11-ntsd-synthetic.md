# 2026-09-11: How NTSD is simulated

**Decision.** WisdomTree NTSD is simulated in `portfolio_suite\efficient_core\ec_ntsd.py`
with the same drifting-weight engine as the NTSG reconstruction
(`ec_portfolios.simulate_efficient_core`). Only the futures leg changes: it holds international
equity futures instead of bond futures. Outputs go to `efficient_core\output\ntsd\`.

```
r = w_us·r_us + w_c·rf + w_fut·(r_intl + ER_backout − rf − spread) − TER − txn
targets 0.90 / 0.10 / 0.60, quarter-end rebalance + 5pp drift trigger
```

## Inputs

- **US leg:** Ken French US market, daily. It ends 2026-04-30, so the history ends there.
- **International leg:** testfolio **VEASIM** (1970+). User-supplied 2026-09-11 and stored as
  `shared_data\testfolio_data\VEASIM_daily.csv` (header lower-cased for `tf_load`).
- **Cash and financing:** Ken French 1-month T-bill.

## Assumptions (labelled in code)

| | Value | Status |
|---|---|---|
| TER | 0.35% | prospectus |
| Transaction costs | 0.02% | **assumed**, borrowed from NTSG's KID |
| Futures financing spread over T-bills | 0.30% | **assumed**; grid 0–1.00% in `ntsd_spread_sensitivity.csv` |
| VEA ER backed out | 0.03% | futures carry no ETF fee |

**No separate "volatility drag" is subtracted.** It is already in the compounding, so
subtracting it would count it twice.

## Why not the testfolio LETF formula as-is

`L·r − SW·(L−1)·(FR+SP)/252 − E/252` gets the **financing** right. With L = 1.5 and SW = 1,
the 0.5 borrowed equals 0.60 of futures minus 0.10 of cash. But the formula **resets daily on
one underlying**, and NTSD holds two underlyings and drifts between quarterly rebalances.
Over 1970–2026 the daily-reset form runs +0.19pp/yr above the drift model, and the gap
ranges from −1.17 to +0.72pp over rolling 5-year windows. So the drift model is kept. The
formula's **slippage diagnostics** are adopted instead: the mean real-minus-synthetic gap, its
standard error, and the regressions.

## Results (first run)

- **1970-01 → 2026-04:** synthetic 11.81% CAGR vs testfolio NTSDSIM 11.92%. Cost-free, the
  synthetic makes 12.40%. Volatility 24.1% vs 24.6%, max drawdown −74.3% vs −74.4%.
- **NTSDSIM regressed on its ingredients:** US 0.94, intl 0.57, rf −0.41, R² 0.968. That is
  consistent with the user's "0.9 SPY + 0.6 VEASIM" hypothesis. The US leg differs (SPYSIM vs
  the FF total market), which is why R² falls short of 1.
- **Testfolio's implied all-in cost** is about 0.3%/yr lower than ours. Ours is the more
  conservative of the two.
- **Live check, real NTSD vs SPY + EFA synthetic (2026-03-20 → 09-10, 120 days):** cumulative
  +20.30% vs +20.27%, correlation 0.987, fitted exposures 0.85 US / 0.60 intl. The mean gap is
  −0.01%/yr **± 5.2%** (one standard error), so six months cannot identify costs at all.
  **Do not calibrate a tracking-error fudge from it.**
- **EFA fits better than VEA** (VEA: intl 0.48, TE 5.2%). EAFE is the fund's actual futures
  index. VEASIM (FTSE Developed: includes Canada, Korea and small caps) is used only because it
  is the one daily series that reaches 1970. That source difference is part of any tracking gap.
- **Ken French Developed ex US vs VEASIM (1990+):** daily correlation only 0.65, monthly
  0.978. KF uses local-market closes, while EAFE futures trade at US hours, so KF is the wrong
  timing for a daily simulation. This is a second reason to prefer VEASIM.

## Links

[[efficient-core-9060]] · [[testfolio-cross-check]] · [[portfolio-dashboard]] · [[2026-09-11-portfolio-suite]]
