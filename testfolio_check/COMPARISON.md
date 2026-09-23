# Testfolio vs our series

Each section asks whether our series and testfolio's are the same underlying data, and where they are not, what accounts for it. Where a primary source exists (Ken French's own files, a live fund) it is the referee; testfolio is an independent second opinion, not the truth.

Both sides are measured with the conventions established in [VERIFY.md](VERIFY.md) — fixed 252 annualisation, 365.25 day-count — so no gap below is a measurement artefact.

---

## FFSCV vs our `scv` (Fama-French SMALL HiBM)

This is the pairing that matters: same nominal source, same 1926-07-01 start, and the largest gap of any pair on this page.

| | ours | testfolio |
|---|---:|---:|
| Window | 1926-07-01 → 2026-06-30 | 1926-07-02 → 2025-10-31 |
| Observations | 26,274 | 24,951 |
| Obs/yr | 262.75 | 251.19 |
| CAGR | 14.43% | 12.95% |
| Volatility | 20.57% | 19.83% |
| Max drawdown | -88.95% | -87.80% |

### Test 0 — are the daily returns the same numbers?

| | |
|---|---:|
| Shared trading days | 24,951 |
| Daily return correlation | 0.938267 |
| Days identical to 1e-9 | 0.00% |
| Max absolute daily difference | 7.01pp |
| Mean daily difference (ours − tf) | -0.900bp |
| Implied annual drift | -2.27pp/yr |

**No.** Not one of the 24,951 shared days matches, and the correlation is 0.94 rather than 1.00. Whatever the gap is, it is not a calendar artefact — these are two different portfolios. Tests 1–4 establish what kind of difference it is.

### Test 1 — the Saturday sessions are real, and ours are handled correctly

Our series carries **1,158 Saturday sessions**, all on or before 1952-05-24; testfolio's carries **0**. The NYSE traded Saturday mornings until 1952.

| | n | mean return |
|---|---:|---:|
| Saturdays (small value) | 1,158 | +0.3145% |
| All other pre-1952 days | 6,470 | +0.0073% |
| Saturdays (broad market) | 1,158 | +0.1435% |

Those Saturday returns are strongly positive on both series — this is the documented pre-1952 weekend effect (French, 1980: Monday returns negative, Saturday positive). **They are real sessions carrying real return**, so deleting them destroys return that actually happened:

| Our variant | Obs | CAGR | Vol | Max DD |
|---|---:|---:|---:|---:|
| Saturdays kept — as we build it | 26,274 | 14.43% | 20.57% | -88.95% |
| Saturdays deleted | 25,116 | 10.45% | 20.55% | -92.54% |
| **testfolio FFSCV** | 24,951 | **12.95%** | **19.83%** | **-87.80%** |

Testfolio's 12.95% sits **between** our two calendar treatments, so it is not simply dropping Saturdays either. Our handling is the correct one and is not the source of the gap.

### Test 2 — end-date alignment

Truncating ours to testfolio's last day (2025-10-31) moves CAGR from 14.43% to **14.26%** — -0.17pp. Not the explanation either.

### Test 3 — is it a different Fama-French portfolio?

Testfolio's series was correlated against **all twelve** series in the 6-portfolio 2×3 file — both the value-weighted and equal-weighted blocks. If FFSCV were any of them, one row would correlate at 1.000.

| Block | Column | Correlation | Identical days | CAGR | Vol |
|---|---|---:|---:|---:|---:|
| equal-weighted | ME2 BM2 | 0.94833 | 0.00% | 11.18% | 18.04% |
| value-weighted | SMALL HiBM ←ours | 0.93827 | 0.00% | 10.26% | 20.58% |
| equal-weighted | BIG HiBM | 0.93652 | 0.00% | 11.84% | 22.40% |
| value-weighted | ME1 BM2 | 0.93452 | 0.00% | 9.43% | 18.59% |
| value-weighted | BIG HiBM | 0.90298 | 0.00% | 9.28% | 22.31% |
| equal-weighted | ME1 BM2 | 0.90171 | 0.00% | 18.32% | 18.40% |
| value-weighted | ME2 BM2 | 0.89572 | 0.00% | 8.24% | 17.72% |
| equal-weighted | BIG LoBM | 0.87286 | 0.00% | 9.48% | 18.30% |
| equal-weighted | SMALL HiBM | 0.86367 | 0.00% | 30.17% | 18.85% |
| value-weighted | SMALL LoBM | 0.86181 | 0.00% | 5.88% | 20.33% |
| equal-weighted | SMALL LoBM | 0.83595 | 0.00% | 12.82% | 20.26% |
| value-weighted | BIG LoBM | 0.82330 | 0.00% | 8.83% | 17.75% |
| **testfolio FFSCV** | | | | **12.95%** | **19.83%** |

The best match is 0.948 — nowhere near 1.000, and **zero identical days against any of the twelve**. Testfolio's FFSCV is not a column of this file.

### Test 4 — monthly frequency, and where the divergence sits

Aggregating both to month-end removes every intra-month calendar difference, including the Saturdays. If the two were the same portfolio sampled differently, monthly returns would agree.

| | |
|---|---:|
| Months compared | 1,192 |
| Monthly correlation | 0.967991 |
| Months matching to 1e-4 | 0.84% |
| Max absolute monthly difference | 27.98pp |
| Mean difference | +2.19pp/yr |

| Decade | Mean difference (ours − tf) | Months |
|---|---:|---:|
| 1920s | -4.13pp/yr | 42 |
| 1930s | +9.66pp/yr | 120 |
| 1940s | +5.58pp/yr | 120 |
| 1950s | -0.35pp/yr | 120 |
| 1960s | +2.36pp/yr | 120 |
| 1970s | +2.15pp/yr | 120 |
| 1980s | +0.11pp/yr | 120 |
| 1990s | +1.30pp/yr | 120 |
| 2000s | +1.70pp/yr | 120 |
| 2010s | -0.20pp/yr | 120 |
| 2020s | +1.51pp/yr | 70 |

The gap is **not a constant drag** — it is concentrated in the 1930s (+9.7pp/yr) and 1940s (+5.6pp/yr), the microcap-heavy, thinly-traded era, and runs around +1.5 to +2pp/yr through most of the modern period. A fee would be flat across decades and would not touch volatility; this does both.

### Test 5 — Ken French's own monthly file decides it

Ken French publishes the 2×3 portfolios **monthly** as well as daily, built separately. If our daily parse were wrong, compounding it to month-end would not reproduce the monthly file.

| | vs KF monthly: correlation | CAGR |
|---|---:|---:|
| KF monthly file, SMALL HiBM | — | 14.15% |
| **ours** (KF daily, compounded) | **0.99991** | 14.26% |
| testfolio FFSCV (compounded) | 0.96788 | 12.95% |

Over 1,192 months ours tracks the official monthly series almost exactly; testfolio's does not. **FFSCV is not Ken French's SMALL HiBM**, and ours is.

### Fingerprint

| | ours | testfolio |
|---|---|---|
| Best single day | 1933-03-15 +26.70% | 1933-03-15 +24.63% |
| Worst single day | 1933-07-21 -16.02% | 1933-07-21 -13.89% |
| Daily skew | 0.258 | 0.128 |
| Excess kurtosis | 25.79 | 22.22 |
| Lag-1 autocorrelation | 0.1012 | 0.0781 |

The extremes land on **the same two dates** — 1933-03-15 (the reopening after the Bank Holiday) and 1933-07-21 — so this is unmistakably the same market over the same history. But testfolio's version is damped at every extreme: lower skew, lower kurtosis, and **lower lag-1 autocorrelation (0.078 vs 0.101)**.

Lower autocorrelation is the informative one. The Kelly study attributes our +0.128 daily autocorrelation to stale microcap pricing. Testfolio's series shows materially less of it, which points at a small-value portfolio with **larger, more liquid holdings** — a screened or investable-universe construction rather than the raw research portfolio.

### Verdict

**Neither series is wrong; they are different portfolios, and ours is correctly built.** Our `scv` is the documented `SMALL HiBM` column of the value-weighted block, parsed correctly, on a calendar whose Saturday sessions are genuine. Testfolio's FFSCV is a different, more liquid small-value construction that testfolio does not document.

**There is no bug to fix on our side.** What this does provide is independent corroboration of a caveat the Kelly study already makes about itself: `SMALL HiBM` is a research portfolio holding untradeable microcaps, and `dfsvx_compare.py` puts the implied investable drag at ≈1.09%/yr. Testfolio's more liquid construction runs **1.48pp/yr below ours** — the same order of magnitude, arrived at independently.

**What the Kelly study does with this.** The two are never spliced into one series (they are different portfolios, so a join would put a level break into every statistic). `scv_leverage/kd_data.py` takes one source at a time: `SCV_SOURCE = "kf"` (default: documented, reproducible, matches the monthly file) or `"testfolio"` (ends 2025-10-31), and `SCV_HAIRCUT` can subtract a constant investability drag from the KF series.

---

## NTSDSIM vs our `ntsd_synth`

NTSD (WisdomTree Efficient U.S. Plus International Equity) holds **0.90 US equity + 0.60 notional developed ex-US equity futures + 0.10 bills**: 1.5× equity, which is why its beta is 1.34 and its volatility sits well above the market's. It is *not* the stock/bond 90/60 (`rec9060`), and an earlier version of this page wrongly compared it with that. `efficient_core/ec_ntsd.py` rebuilds it from the Ken French US market, testfolio's VEASIM and the 1-month bill, net of the 0.35% TER, 0.02% trading costs and a 0.30% futures financing spread, with quarterly + 5pp-drift rebalancing. A gap of a few tenths of a percent a year is the whole cost/spread uncertainty.

On the 14,203 shared trading days (1970-01-02 → 2026-04-30):

| | ours | testfolio | Δ |
|---|---:|---:|---:|
| CAGR | 11.38% | 11.92% | -0.54pp |
| Volatility | 24.07% | 24.59% | -0.52pp |
| Max drawdown | -74.40% | -74.41% | +0.01pp |

| | |
|---|---:|
| Shared trading days | 14,203 |
| Daily return correlation | 0.983478 |
| Days identical to 1e-9 | 0.00% |
| Max absolute daily difference | 5.47pp |
| Mean daily difference (ours − tf) | -0.242bp |
| Implied annual drift | -0.61pp/yr |

---

## VTSIM?L=2 vs our `lev15`

**Different leverage: testfolio is 2×, ours is 1.5×**, and ours is developed-markets while testfolio's is global. Not comparable head-to-head; no gap below is an error. Recorded to place both on the leverage axis. (The leverage-cost model itself is validated against live SSO/UPRO by `common/validate_leverage.py`.)

On the 9,084 shared trading days (1990-07-05 → 2026-07-31):

| | ours | testfolio | Δ |
|---|---:|---:|---:|
| CAGR | 9.70% | 9.51% | +0.20pp |
| Volatility | 22.01% | 35.85% | -13.84pp |
| Max drawdown | -72.39% | -86.81% | +14.42pp |

| | |
|---|---:|
| Shared trading days | 9,084 |
| Daily return correlation | 0.893984 |
| Days identical to 1e-9 | 0.00% |
| Max absolute daily difference | 14.77pp |
| Mean daily difference (ours − tf) | -1.530bp |
| Implied annual drift | -3.86pp/yr |

---

## TLTSIM vs our `futures sleeve`

Our `futures` column is the **excess** return on 1.0 notional of the four-currency bond ladder; TLTSIM is a **total-return** US long Treasury. They differ by the whole financing leg by construction, so the CAGR gap should be roughly the cash rate — and it is.

On the 9,085 shared trading days (1990-07-03 → 2026-07-31):

| | ours | testfolio | Δ |
|---|---:|---:|---:|
| CAGR | 2.13% | 5.43% | -3.31pp |
| Volatility | 4.66% | 12.97% | -8.31pp |
| Max drawdown | -21.92% | -48.35% | +26.43pp |

| | |
|---|---:|
| Shared trading days | 9,085 |
| Daily return correlation | 0.883731 |
| Days identical to 1e-9 | 0.00% |
| Max absolute daily difference | 6.32pp |
| Mean daily difference (ours − tf) | -1.556bp |
| Implied annual drift | -3.92pp/yr |

---

## DBMFSIM — no counterpart

The managed-futures work in `SCV_leverage_analysis` (`mf_and_kelly.py`, `mf_solve_cost.py`) lost its outputs to a dead scratchpad and its scripts still point at that path, so there is nothing to compare against. DBMFSIM 2000-2026 — 6.77% CAGR, 9.58% volatility, −20.44% max drawdown, beta 0.01 — is a usable external benchmark if that work is revived. See `context/reference/tech-debt.md`.
