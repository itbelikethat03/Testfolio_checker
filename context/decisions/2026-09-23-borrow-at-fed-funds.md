# 2026-09-23: Borrow at fed funds, lend at the T-bill

**Decision.** Every leveraged position charges its borrowed part at **effective fed funds**
(FRED `DFF`, act/360) plus a spread. Cash and collateral still earn the **T-bill**. Before
fed funds exists (1954), the benchmark is the bill plus the average 1955–2008 gap. That gap
is 0.53pp over Ken French's 1-month bill and 0.33pp over the 3-month bill. The model is in
`common/leverage.py`; see [[leverage-cost-model]].

## Why

The user reported that SSO/UPRO sims and most levered results "might be slightly less than a
percentage point too high". Three candidate causes were measured:

| Candidate | Measured | Verdict |
|---|---:|---|
| Borrowing charged at the T-bill instead of fed funds | fed funds − 3m bill = **+0.33pp/yr** 1955–2008 (+0.6–0.8 in the 1970s–80s), −0.01 since 2009 | **the cause** |
| Compounding daily data | −0.09pp/yr (slightly *understates*) | ruled out |
| Ken French market vs the S&P 500 that LETFs track | +0.03pp/yr | ruled out |

The earlier LETF fit could not see the problem. It used only 2006+ data, and after 2009 fed
funds ≈ bills. Brokers (Interactive Brokers' benchmark is fed funds), LETF swaps and
equity-index futures all finance at overnight rates.

## Scope

- **Changed:** the broker, futures and letf presets; the 1.5× equity line (`lev15`); NTSD's
  equity futures; GDE's gold futures.
- **Not changed:** Treasury-futures sleeves (NTSG, NTSX, RSSB) still finance at the bill.
  Treasury futures price off Treasury repo, which sits nearer bills than fed funds, and NTSX
  matches its live fund within ~0.1pp/yr that way.

## Effect

NTSD synthetic 1970–2026 fell from 11.81% to 11.38%, `lev15` by −0.11pp/yr, and full-Kelly
median CAGR under the cost presets by a further 1–1.5pp. Unlevered and frictionless numbers
are unchanged. Refined the same day by [[2026-09-23-letf-rate-sensitive]].

## Links

[[leverage-cost-model]] · [[scv-leverage-analysis]] · [[reconstructions]] · [[2026-09-11-ntsd-synthetic]]
