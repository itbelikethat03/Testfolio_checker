# Methodology, sources and assumptions

Companion to [REPORT.md](REPORT.md). Everything here is reproducible: `python ec_data.py`
downloads and caches every series, then `ec_analysis.py`, `ec_montecarlo.py` and
`ec_charts.py` regenerate every number and figure in the report.

## Fact vs estimate — the honest inventory

| Input | Status | Source |
|---|---|---|
| 90/60/10 target weights | **documented** | WisdomTree Global Efficient Core Index Methodology, Oct 2025 |
| Quarterly rebalance, last business day Feb/May/Aug/Nov | **documented** | same |
| 5pp exceptional-rebalance trigger | **documented** | same |
| Equity universe: top 1,500 developed, free-float cap weighted, 10% cap, ESG screens | **documented** | same |
| Bond currency weights track equity currency weights, rescaled | **documented** | same |
| Equal weighting within each currency | **documented** | same |
| 8 futures contracts, USD/EUR/GBP/JPY, 2-30y | **documented** | same |
| TER 0.25% | **documented** | factsheet 31/07/2026 |
| Transaction costs 0.02%; total 0.27%/yr | **documented** | KID 07/11/2025 |
| Inception 2024-11-05 | **documented** | factsheet |
| **Which 8 contracts, exactly** | **ESTIMATE** | USD 4 (2/5/10/30), EUR 2 (Bobl, Bund), GBP 1 (Long Gilt), JPY 1 (10y JGB) — satisfies every documented constraint |
| **Numeric currency weights** | **ESTIMATE** | USD 78.1 / EUR 11.7 / JPY 6.8 / GBP 3.4, derived from published country weights at 31/07/2026, rescaled to the four bond currencies |
| **Cheapest-to-deliver maturities** | **ESTIMATE** | 2 / 4.5 / 7 / 18 for the US ladder, 4.5 / 8.5 EUR, 9 GBP, 9 JPY |
| **Currency weights held constant through history** | **ASSUMPTION** | tested in section 12; worth 0.02pp |
| **7.5%/yr forward equity return** (section 6b only) | **ESTIMATE** | stated where used; results are near-insensitive to it |
| Everything else | market data | see below |

Two documented details are deliberately **not** modelled, because no public proxy exists:
the ESG exclusions and the 10% single-stock cap on the equity sleeve. Their effect is
inside the ~1pp/yr spread between the two equity proxies used, which is stated in the
report rather than hidden.

## Data sources — all primary, all downloaded programmatically

| Series | Source | Coverage |
|---|---|---|
| Developed-market equity total return, USD | Ken French `Developed_3_Factors_Daily` (Mkt-RF + RF) | 1990-07-02 -> 2026-07-31 |
| Developed small-cap value | Ken French `Developed_6_Portfolios_ME_BE-ME_Daily`, SMALL HiBM, value-weighted | same |
| US market + 1-month T-bill | Ken French US daily factors (file already in the repo root) | 1926-07 -> 2026-04 |
| US small-cap value | Ken French US 6 portfolios (already in `SCV_leverage_analysis/ff6`) | 1926-07 -> 2026-06 |
| US Treasury curve (3m, 2y, 5y, 10y, 30y) | FRED `DTB3`, `DGS2`, `DGS5`, `DGS10`, `DGS30` | 1954 / 1962 / 1977 -> |
| Euro-area AAA government spot curve (3m-30y) | **ECB Data Portal**, `YC/B.U2.EUR.4F.G_N_A.SV_C_YM.*` | 2004-09-06 -> |
| UK gilt nominal par yields + Bank Rate | **Bank of England IADB**, `IUDSNPY/IUDMNPY/IUDLNPY/IUDBEDR` | 1975 / 1993 -> |
| JGB yield curve (1y-40y) | **Japan Ministry of Finance**, `jgbcme_all.csv` | 1974-09 -> |
| FX (EUR/GBP/JPY vs USD) | FRED `DEXUSEU`, `DEXUSUK`, `DEXJPUS` | 1971 -> |
| US CPI | FRED `CPIAUCSL` | 1947 -> |
| NTSG, NTSX, NTSI, URTH, ACWI, VT, SHY/IEI/IEF/TLT, SPY | Yahoo Finance, split- and dividend-adjusted closes | various |
| US annual stocks / 10y T-bond / 3m T-bill, 1928-2025 | Damodaran `histretSP.xls` (already in `SCV_leverage_analysis`) | 1928-2025 |

WisdomTree documents used: the **index methodology** (October 2025), the **factsheet**
(31/07/2026) and the **KID** (07/11/2025), all downloaded from wisdomtree.eu /
dataspanapi.wisdomtree.com and parsed rather than paraphrased from third-party summaries.

## Return conventions — applied identically to every strategy

- **Total returns throughout.** Dividends reinvested. Ken French market series are total
  returns by construction (Mkt-RF + RF); Yahoo closes are dividend-adjusted. No price
  return is ever compared with a total return.
- **Fund-level costs** are charged only where they exist: 0.27%/yr on the reconstructed
  90/60, 0.20%/yr on the NTSX model, nothing on raw index series. Index-level (zero-cost)
  variants are reported separately in section 12.
- **Sharpe and Sortino are computed on excess returns** over the USD 1-month T-bill, never
  on total returns. Sortino uses a zero-excess-return threshold.
- **CAGR is geometric over the true calendar span**, so it reconciles with the wealth
  charts rather than with a period count.
- **Worst/best calendar year** drops partial first and last years so the figures are
  comparable across strategies.
- **Max drawdown** is on the total-return NAV, daily.
- No survivorship filtering is applied anywhere; Ken French portfolios include delisted
  firms, and no start date was chosen to flatter a result — every window is set by data
  availability and is stated.

## The bond futures model

A futures position needs no funded capital, so its return is the underlying's return minus
the local short rate. That identity is what makes a 90/60 fund possible and is why
financing cost is not a free parameter.

For each currency and tenor the model holds a par bond of constant maturity `M`:

```
P(y, m, c) = c * (1 - (1+y)^-m) / y  +  (1+y)^-m         (annual coupons)
R_t        = P(y_t(M - dt), M - dt, y_{t-1}(M)) - 1 + y_{t-1}(M) * dt
futures_t  = R_t - local_short_rate * dt
```

Two details that matter:

1. **Roll-down is included.** The aged bond is repriced at the yield the curve shows for
   its *own* maturity `M - dt`, interpolated across observed tenors — not at the headline
   `M`-year yield. Omitting this understates a US 7-10y position by about 0.4pp/yr, and it
   is a common error in simplified bond backtests.
2. **The model never extrapolates past the long end.** A date is usable for maturity `M`
   only if the curve that day actually reaches out to `M` and has at least three points.
   That is why the JPY leg starts before the EUR leg — the ECB curve begins in 2004 while
   MoF JGB data begins in 1974.

**Validation** against traded Treasury ETFs (`ec_bonds.py`, run directly) shows the
synthetic series sits +0.25 to +0.35pp/yr above SHY/IEI/IEF/TLT across every maturity, with
correlations 0.90-0.96. About 0.15pp is those ETFs' expense ratio, which a futures position
does not pay. The residual ~0.15pp is a known upward bias, carried forward and disclosed
rather than calibrated away.

**Currency treatment.** Futures P&L arises in local currency and is converted to USD, so
the FX effect applies only to the P&L and is second-order. The 10% cash collateral, by
contrast, is held unhedged across four currencies per the methodology, so its FX exposure
(~2% of NAV) is modelled explicitly.

## Portfolio simulation

`ec_portfolios.simulate_efficient_core` runs a full path with **drifting weights**, not
constant ones:

- equity and cash legs compound at their own returns; futures P&L settles into the cash leg
- costs are deducted daily as `costs * dt`
- weights snap back to 90/10/60 on the documented rebalance dates, and additionally
  whenever the equity or bond weight has drifted more than 5 percentage points

Realised weights over 1990-2026 ranged from 0.861-0.936 (equity) and 0.526-0.702 (bond),
confirming the drift is material enough to be worth modelling.

The 1.5x levered-equity comparator borrows 0.5 of NAV in USD at the 1-month bill rate plus
0.30%/yr (the `futures` preset in `common/leverage.py`, the implied financing of equity index
futures) and is rebalanced on the same schedule, so it is a like-for-like alternative use of
leverage. It is deliberately *not* financed at the four-currency collateral sleeve: that basket
carries unhedged EUR/GBP/JPY moves that a USD borrower does not have.

Both simulations run on the general engine in `common/backtest.py`, which reproduces the
original 90/60 loop bit-for-bit.

## Monte Carlo

- **Stationary circular block bootstrap.** Blocks preserve the persistence of rate cycles,
  which is precisely the thing that determines whether the bond leg pays. An i.i.d.
  bootstrap would destroy it and a fitted Gaussian would discard the left tail that 2022
  occupies.
- **Paired draws.** Both strategies are simulated on the same resampled history, month for
  month. `P(90/60 beats All World)` is therefore a genuine paired probability rather than a
  comparison of two independently drawn distributions, which would badly overstate the
  dispersion of the difference.
- **Two source samples, deliberately.** Sample A (global 1990-2026 monthly, 12-month
  blocks) matches the actual product but is dominated by a bond bull market. Sample B (US
  1928-2025 annual, 4-year blocks) is only 98 observations and US-only, but contains the
  1950-1981 rate rise and a real stagflation. They disagree, and that disagreement is the
  finding rather than something to average away.
- 20,000 paths per horizon; 8,000 for the sensitivity sweep.
- Sample B is an annual approximation that ignores intra-year rebalancing. It is a check on
  the **economics**, not a substitute for the daily reconstruction.

## Known limitations

1. **NTSG has 1.8 years of live history.** The replication claim rests on NTSX (8.1 years,
   same construction), not on NTSG.
2. **The equity proxies are imperfect.** Neither URTH nor Ken French Developed replicates
   NTSG's ESG screen and 10% cap; they differ from each other by ~1pp/yr.
3. **The 1990-2026 window is not regime-neutral.** It is close to the greatest bond bull
   market in history. This is why the 98-year US sample carries equal weight in the verdict.
4. **The euro leg is absent before 2004** and the sterling leg before 1993, because the
   underlying curves do not exist. The sleeve rescales across available currencies rather
   than leaving a hole; section 12 shows the currency mix is worth ~0.04pp/yr at fund level.
5. **Pre-1993 sleeve returns rest on two currencies** and are unusually high (+8.31%/yr on
   1990-1993). That is 9% of the window; its influence is visible in the sub-period table.
6. **The synthetic bond model runs ~0.15pp/yr rich** after allowing for ETF fees. On 0.60
   notional that flatters the 90/60 result by roughly 0.09pp/yr — smaller than the effects
   being measured, but not zero.
7. **The WisdomTree factsheet's performance table does not reconcile** with the fund's own
   price history in any listing currency or with justETF's NAV series. This is reported in
   REPORT.md section 2 and left unresolved rather than assumed away.
8. **Taxes are not modelled.** Withholding tax on dividends, and any investor-level tax
   treatment of an accumulating Irish UCITS versus direct equity holdings, are outside
   scope and could matter for a real decision.

## Files

| File | Purpose |
|---|---|
| `ec_data.py` | download and cache every series; run it first |
| `ec_bonds.py` | synthetic constant-maturity bonds and the futures sleeve; run directly for the ETF validation |
| `ec_metrics.py` | risk/return statistics, defined once |
| `ec_portfolios.py` | the 90/60 simulator and comparators |
| `ec_validate.py` | replication tests against NTSX and NTSG |
| `ec_analysis.py` | sections 1-12 of the report; writes CSV/JSON to `output/` |
| `ec_montecarlo.py` | Table 2, distributions and the sensitivity sweep |
| `ec_charts.py` | the nine charts |

Run order: `ec_data.py` -> `ec_validate.py` -> `ec_analysis.py` -> `ec_montecarlo.py` ->
`ec_charts.py`. Logs of the last full run are in `output/analysis_run.log` and
`output/montecarlo_run.log`.
