# 2026-09-10 — Combining two studies without inventing comparability

**Decision.** Build one dashboard over [[efficient-core-9060]] and
[[scv-leverage-analysis]] that scores every portfolio with a single metric
implementation, but never displays a number on a window the underlying series does not
actually cover.

## The problem

The two studies share almost nothing structurally:

| | Efficient Core | Kelly / best days |
|---|---|---|
| Window | 1990-07-03 → 2026-07-31 | 1926-07-01 → 2026-04-30 |
| Universe | 22 developed markets, USD | US only |
| Costs | 0.27%/yr modelled | none — research portfolios |
| Question | is levered *bonds* worth it? | how much of levered *equity* rests on tail days? |

A naive merged leaderboard would rank a 99-year US gross-of-cost research portfolio against
an 18-year live global ETF and call the difference performance. Both source reports go out of
their way to prevent exactly that — the Efficient Core report writes *"Rows use different
windows and must not be compared vertically"* and prints `n/a` rather than silently
substituting a shorter period. A dashboard that threw that away would be worse than either
report alone.

## What was done instead

1. **Five fixed windows**, each a real boundary in the data, not a round number: 1926, 1990
   (reconstruction start), 2008 (ACWI), 2018 (NTSX), 2024 (NTSG live). One selector scopes
   the whole page.
2. **A 90% coverage rule.** A portfolio is scored on a window only if it covers ≥90% of it.
   Below that it renders as *"n/a — series does not span this window"*, with its actual
   coverage shown. Constant is `MIN_COVERAGE` in `build_data.py`.
3. **A `truncated` flag** for series that span a window but stop before its edge — the Kelly
   data ends 2026-04-30, the Efficient Core data 2026-07-31. Shown as a "short" badge rather
   than left implicit.
4. **One metric implementation.** Both studies' portfolios are scored with
   `efficient_core_9060/ec_metrics.py`, imported directly rather than reimplemented. This is
   the actual gain from combining: the US market and US small-value series now have a
   Sortino and a Calmar on the Efficient Core windows, which the Kelly study never computed.
   See [[metric-conventions]].
5. **The leverage bridge.** The one axis both studies genuinely share is *notional exposure*.
   The Kelly sweep (f = 0.1…4.0) is drawn as lines; the Efficient Core portfolios are plotted
   as **hollow diamonds** at their notional, so they never read as points on a curve. The
   footnote says explicitly: read the vertical gap as a difference in markets, not as alpha.

## Alternatives rejected

- **A single merged leaderboard.** Rejected: it is the failure mode both reports were written
  to avoid.
- **Clipping every series to the common intersection** (2024-11-11 → 2026-04-30, ~1.4 years).
  Rejected: it would be genuinely comparable and completely uninformative. 1.4 years cannot
  support any metric on this page.
- **Restating Kelly-study series in developed-market terms.** Not possible — no such data
  exists, and constructing a proxy would be inventing the comparability rather than measuring it.

## What this still does not license

Scoring two series with the same function makes the **metrics** comparable. It does not make
the **markets** comparable. The sharpest instance: US small-cap value carries no cost drag at
all, and the Kelly study's own estimate of that drag is ≈1.09%/yr. Called out on the page and
in [[scv-leverage-analysis]].

## Links

- [[portfolio-dashboard]] — the implementation.
- [[2026-09-10-obsidian-vault]] — the other decision made the same day.
