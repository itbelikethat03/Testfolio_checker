# Efficient Core 90/60

**Question:** does the WisdomTree Global Efficient Core UCITS ETF (NTSG, ISIN IE00077IIPQ8)
— 0.90 equity + 0.10 cash + 0.60 notional bond futures — actually beat 100% global equities?

**Location:** `portfolio_suite\efficient_core\` (the maintained copy; the original
`C:\Python Datoteke\efficient_core_9060\` is no longer maintained).
**Report:** `output\REPORT.md` · **Methods:** `output\METHODOLOGY.md`
**Last full run:** 2026-09-23.

**Changes since the report was written (2026-09-23):**

- **DTB3 converted from discount basis to bond-equivalent.** The bond-futures excess return is
  −0.07pp/yr, `rec9060` 9.27% → 9.23%, and the NTSX gap +0.02 → −0.05pp/yr.
- **Semi-annual coupons for USD/GBP/JPY.** Effect < 0.01pp.
- **`lev15` borrows USD at fed funds + 0.30%.** It used to borrow at the FX-exposed cash
  basket, and a drift-check bug is also fixed. See [[2026-09-23-borrow-at-fed-funds]].
- **The simulations run on `common/backtest.py`**, which reproduces the original loop
  bit-for-bit.
- **NTSD synthetic 1970–2026 is now 11.38%** (was 11.81%) after fed-funds financing of its
  equity futures.

Some figures in `REPORT.md` predate these changes; the CSVs and the dashboard are current.

## The answer in one identity

```
r(90/60) − r(100% equities) = 0.60 × BOND TERM PREMIUM
                            − 0.10 × EQUITY RISK PREMIUM
                            − costs

break-even term premium = (ERP / 6) + (costs / 0.6)
                        = 1.28%/yr  at 5% ERP and the fund's 0.27% costs
```

The fund is **not** betting bonds beat equities. It gives up one tenth of the equity risk
premium to buy six tenths of the bond term premium. That 6:1 multiplier is why the
break-even bar is low — and why the bond row of every sensitivity grid decides everything
while the equity column barely matters.

## What survives and what does not

- **Return edge: sample-dependent.** Global 1990–2026: +0.78pp/yr. US 1928–2025: −0.02pp/yr,
  a dead heat. The 36-year window is very nearly the greatest bond bull market in history.
- **Risk result: survives both samples.** Sharpe 0.55 vs 0.45 global; 0.441 vs 0.428 US.
  Lower vol, shallower drawdowns, faster recoveries, better left tail everywhere.
- **Failure mode: stagflation.** 0% win rate over 98 years of US data. 2022 was its worst
  relative year in 98 (−10.21pp) and the one crisis where it lost *more* than unlevered equities.
- **Today:** implied term premium +0.88%, below the 1.28% break-even, and stock/bond
  correlation has been positive since 2023.

## Run order

```
ec_data.py -> ec_validate.py -> ec_analysis.py -> ec_montecarlo.py -> ec_charts.py -> ec_ntsd.py
```

`ec_montecarlo.py` is the slow one (20,000 paths × 4 horizons × 2 samples).

## Judgment calls that are load-bearing

These are the choices that would change the conclusion if made differently, and they are
**not** obvious from the code.

1. **Cheapest-to-deliver ladder (2 / 4.5 / 7 / 18y), not nominal (2 / 5 / 10 / 30y).**
   Chosen *before* looking at fit, on the grounds that a bond future tracks the cheapest
   bond in its delivery basket — the 10-year Note future delivers a ~7-year note. It
   reproduces the ~7y sleeve duration WisdomTree publishes, and it happens to fit better
   (+0.02pp/yr vs actual NTSX over 8.1 years). It is also the **conservative** choice: the
   nominal ladder would have shown +1.03pp instead of +0.78pp.
2. **Roll-down is modelled.** The aged bond is repriced at its own maturity, not at the
   headline tenor. Worth ~0.4pp/yr on a 7–10y position. Omitting it is a common and material
   modelling error.
3. **Bond currency weights are an estimate** (USD 78.1 / EUR 11.7 / JPY 6.8 / GBP 3.4),
   derived from published country weights because the exact split is not disclosed. This is
   the least certain input in the whole study and it moves the answer by **0.02pp**.
4. **The synthetic bond engine runs +0.25 to +0.35pp/yr rich** against SHY/IEI/IEF/TLT across
   every maturity, and +0.3–0.4pp against testfolio's TLTSIM. About 0.15pp is those ETFs' own
   expense ratio, which a futures position does not pay. The remaining ~0.15pp is a known
   upward bias, carried forward rather than tuned away. The DTB3 and coupon-frequency fixes
   did not close it.
5. **Treasury futures finance at the bill, not fed funds.** They price off Treasury repo.
   Unlike equity futures and LETFs, they were deliberately left at the bill in
   [[2026-09-23-borrow-at-fed-funds]].

## Known discrepancy, reported not resolved

WisdomTree's factsheet of 2026-07-31 shows YTD 7.14%, 1-year 16.80%, since-inception
14.83% p.a. **These do not reconcile with the fund's own price history in any of its three
listing currencies, nor with justETF's independent NAV series.** The study uses the
price-derived series, which two independent sources agree on (Xetra EUR line +20.31%
cumulative from inception, matching justETF exactly). Flagged, not reconciled away.

## Links

- [[portfolio-dashboard]] — reads this study's outputs.
- [[scv-leverage-analysis]] — the other leverage study; shares data files with this one.
- [[data-schemas]] · [[metric-conventions]] · [[chart-palette]]
