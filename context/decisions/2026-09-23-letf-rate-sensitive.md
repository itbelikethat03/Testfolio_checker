# 2026-09-23: Leveraged-ETF financing = 1.107 × fed funds + 0.43%, fitted to the real funds

Refines: [[2026-09-23-borrow-at-fed-funds]] (which used a flat fed funds + 0.69%).

**Decision.** The `letf` preset borrows at **1.107 × fed funds + 0.43%**, with a 0.91% TER
and a daily reset. `common/validate_leverage.py` fits it to live SSO (2006+) and UPRO (2009+)
by least squares on per-rate-regime CAGR errors. The **2020–21 regime is excluded from the
fit**. It is not excluded from validation.

## Evidence (user-supplied testfolio SSOSIM / UPROSIM, 1885–2026)

- **After launch, testfolio's sims *are* the real funds** (daily correlation 0.9997 / 1.0000).
  The two sources can only disagree before launch.
- **Testfolio's pre-launch financing is backed out exactly.** Both sims apply one model to one
  underlying index, so `3·SSOSIM − 2·UPROSIM + TER` = their borrowing rate. That rate is
  **1.27 × fed funds + 0.67pp** (R² 0.999, 1955–2005), about fed funds + 2pp at 5% rates.
  Their implied index (`2·SSOSIM − UPROSIM + TER`) tracks the Ken French market to a few
  tenths outside 1970–89, so **the financing rule is what separates the histories**.
- **The real funds decide between the rules.** Model minus real fund, pp/yr:

| | constant (ff + 0.69%) | **fitted (1.107·ff + 0.43%)** | testfolio (1.27·ff + 0.67%) |
|---|---:|---:|---:|
| SSO 2006–08 (ff 3.8%) | +0.18 | **+0.07** | −0.53 |
| SSO 2022+ (ff 4.0%) | +0.16 | **−0.04** | −1.06 |
| UPRO 2022+ (ff 4.0%) | +0.37 | **−0.02** | −2.07 |
| UPRO 2009–15 (ff 0.1%) | −0.66 | **+0.03** | −0.70 |

The testfolio rule is 0.5–2pp/yr too punitive at 4% rates. A flat spread is 0.2–0.4pp too
generous there. The fitted rule matches every regime within ~0.1pp except 2020–21.

## Why 2020–21 is excluded from the fit

During the COVID crash, swap financing and rebalancing costs spiked while fed funds sat near
0%. That is a crisis/volatility cost, not a rate effect. Left in the fit, it reads as "spreads
are high when rates are low" and drags the rate slope to 1.0 (overall RMS error 0.67pp; 0.06pp
without it). The cost of excluding it is that the model runs +0.09 (SSO) / +0.26 (UPRO)
pp/yr generous over the funds' full lives. `validate_leverage.py` prints all four fits
(slope free/fixed × with/without 2020–21) so the choice stays visible.

## Result

| 1955–2026 | before | now | testfolio |
|---|---:|---:|---:|
| SSO sim | 12.63% | **12.39%** | 12.37% |
| UPRO sim | 12.48% | **11.99%** | 11.25% |

The remaining UPRO gap is testfolio's heavier high-rate financing, which the real funds
contradict, so it is not chased. Full decomposition: `testfolio_check\COMPARISON.md`.

## Still unmodelled

Daily-rebalancing costs were higher in the 1970s–80s than in the 2006+ window the spread was
fitted on. Crisis cost spikes (like 2020) are not modelled either. Both mean pre-2000 LETF
history may still be somewhat generous.

## Links

[[leverage-cost-model]] · [[reconstructions]] · [[testfolio-cross-check]]
