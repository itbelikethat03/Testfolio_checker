# Testfolio cross-check

External validation of our return series against testfol.io, first run 2026-09-10 and
extended 2026-09-23. Harness: `portfolio_suite\testfolio_check\` → `VERIFY.md`,
`COMPARISON.md`. Data: `shared_data\testfolio_data\`, where every file is identified by
content, not name (`tf_load.py`).

**Outcome: no defect found in our data.** Testfolio is a second opinion, not the referee.
Where a primary source exists (Ken French's own files, a live fund), that decides. That
principle reversed the 2026-09-10 FFSCV splice ([[2026-09-23-scv-source-kf]]) and set the LETF
financing model ([[2026-09-23-letf-rate-sensitive]]).

## Testfolio's metric conventions (established, not guessed)

49 of 60 cells reproduce exactly from testfolio's own daily $ series, using **one**
convention per metric across all five series. (Letting the convention vary per series
scores 51/60, but a convention that changes per series is not a convention — the stricter
choice is the honest one.) The conventions:

| Metric | Convention |
|---|---|
| CAGR | 365.25 day-count on the calendar span |
| Volatility | daily sd × **√252** — a fixed 252, not the sample's own obs/yr |
| Avg drawdown | mean of the daily drawdown path **over underwater days only** |
| Longest DD | peak → **recovery** (not peak → trough) |
| Ulcer index | `√mean(dd²)`, expressed in percent |
| Sharpe | `mean(excess)/sd(excess) × √252` |
| Sortino | `mean(excess) × 252 / downside deviation`, MAR = rf |
| UPI | `(arithmetic annual excess) / ulcer` |

## The things that do not reproduce

**Longest DD**, 2 cells, off by 0.01y — pure day-count rounding between 365 and 365.25 on a
~9-year drawdown. Immaterial.

**Sharpe / Sortino / UPI** — the other nine are exactly the three rf-dependent metrics.
Solving each independently for the risk-free add-on that would close it gives a *consistent*
answer per series, averaging **~13bp/yr**. Three mathematically independent metrics agreeing
on one number is what makes this a single input difference rather than nine errors.

Both candidate bill series were tested — Ken French's 1-month bill (what we use) and FRED
`DTB3` — and they land within 0.001 of each other on every series. **Neither closes the
gap**, so testfolio uses a third series not present in the export. The affected figures are
off by 0.01–0.02 on a ratio and change no conclusion anywhere.

**Beta** — needs a benchmark series the export does not include. Fitted against the FF US
total market the signs and magnitudes are right (managed futures ≈0, long Treasuries
slightly negative) but residuals are uneven, so the benchmark is a broad US equity index
that is *not* the FF market series.

**To close either, testfolio would need to export its risk-free and benchmark series.**

## FFSCV vs our `scv` — different portfolios, both correct

| | ours | testfolio |
|---|---:|---:|
| CAGR | 14.39% | 12.95% |
| Volatility | 20.58% | 19.83% |
| Max drawdown | −88.95% | −87.80% |
| Lag-1 autocorrelation | 0.101 | 0.078 |

Not one of the 24,951 shared days matches; daily correlation is 0.94, monthly 0.97.
Correlating testfolio's series against **all twelve** columns of
`6_Portfolios_2x3_Daily.csv` (both value- and equal-weighted blocks) gives a best match of
0.948 and **zero identical days anywhere** — so FFSCV is not a column of that file.

The extremes land on the *same two dates* (1933-03-15, 1933-07-21) at smaller magnitudes,
and testfolio's series is damped at every tail: lower skew, lower kurtosis, and lower
autocorrelation. Lower autocorrelation is the tell — the Kelly study attributes our +0.128
to stale microcap pricing, so testfolio's construction holds **larger, more liquid** names.

The divergence is concentrated in the 1930s (+9.7pp/yr) and 1940s (+5.6pp/yr) — the
microcap-heavy era — and runs +1.5 to +2pp/yr in the modern period. A fee would be flat
across decades and would not move volatility; this does both, so it is a construction
difference, not a cost difference.

**This independently corroborates the study's own caveat.** `dfsvx_compare.py` puts the
investable drag on `SMALL HiBM` at ≈1.09%/yr; testfolio's more liquid construction runs
1.44pp/yr below ours. Same order of magnitude, reached from a different direction. See
[[scv-leverage-analysis]].

**Decisive test (2026-09-23): Ken French's own monthly file.** Our daily `SMALL HiBM`
compounded to month-end matches Ken French's separately published monthly series at
correlation **0.9999** (14.29% vs 14.39% CAGR). FFSCV correlates with that monthly series at
only 0.968. **FFSCV is not Ken French's SMALL HiBM, and ours is.** So the Kelly study uses ours
by default and never splices the two ([[2026-09-23-scv-source-kf]]).

## The Saturday sessions are real — keep them

Previously unmeasured, and load-bearing for the Kelly study's 262.78 obs/yr figure.

| | n | mean return |
|---|---:|---:|
| Saturdays (small value) | 1,158 | **+0.3145%** |
| All other pre-1952 days | 6,470 | +0.0073% |
| Saturdays (broad market) | 1,158 | +0.1435% |

The NYSE traded Saturday mornings until 1952-05-24. Those returns are strongly positive on
both series — the documented pre-1952 weekend effect (French, 1980: Monday negative,
Saturday positive). **They are real sessions carrying real return.** Deleting them drops
our SCV CAGR from 14.39% to 10.41%, discarding return that actually happened.

Testfolio's 12.95% sits *between* our two calendar treatments, so testfolio is not simply
dropping them either. **Do not "fix" our calendar to match testfolio's** — ours is right.

## NTSDSIM is an equity-on-equity 90/60, not a comparison for `rec9060`

*Corrected 2026-09-11. The original wording said NTSDSIM was "not a 90/60", which was the wrong framing.*

NTSDSIM simulates **WisdomTree NTSD**, the Efficient U.S. Plus International Equity Fund
(launched 2026-03, 0.35% ER). It holds **0.90 US large-cap equity plus 0.60 developed
international equity via index futures**, so it is 150% equity with no bond leg. The US leg is the S&P 500 and the international leg is MSCI EAFE futures, collateralised by 10% T-bills. It
**rebalances quarterly, plus a 5% drift trigger**. That is the same rule `rec9060` already
implements, and it is not a daily reset. (Source: optimizedportfolio.com/ntsd, since WisdomTree's
own page returned a 403.) That is a
different product from NTSG / `rec9060`, which layers *bond* futures on equity.

The risk profile fits that construction. Take US beta 1.0 and developed ex-US beta ≈ 0.71
(testfolio's VEASIM). Then 0.90 × 1.0 + 0.60 × 0.71 ≈ **1.33**. The published beta is 1.34,
and our fit against the FF US market gives 1.357. The 24.56% volatility and 12.01% CAGR since
1969 fit 1.5× equity as well. The user's hypothesis is that testfolio builds it as roughly
0.9 × SPY + 0.6 × VEASIM. That is consistent, but not yet verified by regression.

**Coverage.** NTSDSIM starts 1969-12-31, the same date MSCI EAFE history begins, which suggests
VEASIM is EAFE-based. Our developed-market equity (Ken French) starts only 1990-07-02, so any
NTSD simulation of ours stops at 1990 unless a pre-1990 developed ex-US daily series is added.

Checked 2026-09-11: Ken French **Developed ex US 3 Factors [Daily]** covers 22 countries and
excludes the US. It is in USD, includes dividends, and is value-weighted. It starts on
**1990-07-02**, the same date as the Developed file, and it **includes Canada**, which MSCI EAFE
does not. Ken French international data before 1990 is monthly only, from 1975, sourced from
MSCI. A cached copy is at `portfolio_suite\efficient_core\data_cache\Developed_ex_US_3_Factors_Daily_CSV.zip`.

**Reproduced 2026-09-11** by `ec_ntsd.py` ([[2026-09-11-ntsd-synthetic]]): 11.81% vs NTSDSIM's
11.92% over 1970–2026. After fed-funds financing of the futures (2026-09-23) ours is 11.38%,
because testfolio's equity-futures financing is lighter than fed funds + 0.30%.

## SSOSIM / UPROSIM: testfolio's leveraged-ETF financing (2026-09-23)

User-supplied `SSOSIM_daily.csv` and `UPROSIM_daily.csv` cover 1885-03-20 → 2026-09-22.

- **After launch they *are* the real funds.** SSO correlates 0.9997 (15.85% vs 15.84%), UPRO
  1.0000. Compare pre-launch only.
- **The pair identifies testfolio's model exactly.** Both apply `bill + L·(u − bill) − (L−1)·(R −
  bill) − TER` to one index `u`, so every day `R = 3·SSOSIM − 2·UPROSIM + TER` and
  `u = 2·SSOSIM − UPROSIM + TER`.
- **R ≈ 1.27 × fed funds + 0.67pp** (R² 0.999 on 1955–2005 annual averages). That is about fed
  funds + 2pp at 5% rates and + 3.4pp at 10%. The implied `u` tracks the Ken French market to
  a few tenths outside 1970–89.
- **Before 1952 the `u` comparison is meaningless.** Ken French has Saturday sessions and
  testfolio does not, and intersecting the calendars deletes real Saturday returns from ours.
- **The live funds reject R** at 4% rates: 0.5–2pp/yr too punitive in 2006–08 and 2022+. We
  use 1.107 × fed funds + 0.43% instead, fitted to the same funds
  ([[2026-09-23-letf-rate-sensitive]]).
- **Result, 1955–2026:** SSO ours 12.39% vs testfolio 12.37%; UPRO 11.99% vs 11.25%. The
  UPRO gap is their heavier high-rate financing.

## Links

- [[scv-leverage-analysis]] · [[efficient-core-9060]] · [[leverage-cost-model]] · [[data-schemas]] · [[tech-debt]]
