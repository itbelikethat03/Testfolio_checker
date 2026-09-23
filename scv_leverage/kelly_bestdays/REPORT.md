# How much of the Kelly criterion rests on a handful of days?

Fama-French daily data, 1926-07-01 → 2026-04-30 (26,233 trading days, 99.83 years).
Methods and assumptions: [METHODOLOGY.md](METHODOLOGY.md). All 27 validation checks pass
(`kd_phase11_validate.py`), including the Monte Carlo reproducing the historical CAGR to
within 0.03pp.

---

## The short answer

**Yes, strongly — but the sensitivity is not special to the best days, and it is smaller
than two other sources of uncertainty that were already in the estimate.**

| | Broad market | Small-cap value |
|---|---|---|
| Full-sample Kelly f\* | **2.62×** | **2.78×** |
| after removing the 20 best days (0.076% of days) | 2.13× (−19%) | 2.40× (−14%) |
| after removing the 100 best days (0.38% of days) | 0.77× (−71%) | 1.31× (−53%) |
| 95% CI on f\* from ordinary sampling error alone | **1.36× – 3.98×** | 1.58× – 4.09× |
| range of f\* across the four 25-year blocks (Gaussian μ/σ²) | **1.65× – 4.98×** | 1.66× – 11.19× |

Removing the 20 best days moves Kelly by **0.72 bootstrap standard errors**. Ordinary
estimation noise and regime instability both move it further. The best-day effect is real
and monotone, but it is not an outlier among the things that make this number unreliable.

---

## Phase 1–2: what the data actually is

Two series, both already in the project and parsed exactly as `sv_full_analysis.py` and
`mf_and_kelly.py` parse them:

* **Broad market** — `F-F_Research_Data_Factors_daily.csv`, `Mkt-RF` (an **excess** return)
  plus `RF`. CRSP value-weighted total market.
* **Small-cap value** — `ff6/6_Portfolios_2x3_Daily.csv`, *Average Value Weighted Returns —
  Daily*, column `SMALL HiBM` (a **total** return). Small-ME / high-BE/ME.

Confirmed empirically rather than assumed: in 1980–89, when T-bills yielded 9.16%/yr,
`SMALL HiBM`'s daily mean sits above `Mkt-RF` by roughly the bill yield — it is a total
return. Kelly is computed on excess returns throughout (`scv_exc = SMALL HiBM − RF`).

**`SMALL HiBM` is a long-only portfolio, not a long-short factor**, so a Kelly number for it
is at least conceptually meaningful. It is still *not* an investable ETF: value-weighted,
gross of all costs, and holding microcaps. The project's own `dfsvx_compare.py` put the
DFSVX-implied drag at ≈1.09%/yr. **No drag is applied here**, so every Kelly level below is
optimistic. Its daily lag-1 autocorrelation is **+0.128** (market: +0.046) — stale microcap
pricing, which inflates measured geometric growth further.

### Problems found in the existing Kelly code

* `compute_kelly_metrics()` in `backtest.py` / `mf_and_kelly.py` maximises
  `E[log(1 + f·x)]`, dropping the `rf` term from the wealth relative. The correct form is
  `E[log(1 + rf + f·x)]`. **Measured impact at daily frequency: 0.000×** — daily `rf` ≈ 1e-4
  is negligible next to 1. Corrected in the new code; it changes nothing here.
* `f_kelly = np.clip(f_kelly, -1.0, 10.0)` silently caps. That cap would **bind** on one
  subsample used here: small-cap value's 1976–2000 block estimates at 11.19× (Gaussian), so
  the project's function would have reported 10.00× with no warning. The new code does not
  clip; it constrains `f ≥ 0` and to the no-bankruptcy region instead.
* The Gaussian formula `μ/σ²` is used without checking the distribution. Daily excess
  kurtosis is **16.1 (market) and 24.8 (small-cap value)**, so it is an approximation. The
  headline numbers here use the empirical log-optimal f\* instead; the two agree to ~0.05×
  at full sample, and diverge to ~3.4× in the fat-tailed 1976–2000 small-cap block.

---

## Phase 3: baseline

| | Broad market | Small-cap value |
|---|---|---|
| Ann. arithmetic mean (total) | 11.28% | 15.66% |
| CAGR (geometric) | 10.24% | 14.39% |
| Ann. volatility | 17.47% | 21.01% |
| Sharpe | 0.466 | 0.596 |
| Max drawdown | −84.07% | −88.95% |
| Worst / best day | −17.41% / +15.67% | −16.02% / +26.70% |
| Skew / excess kurtosis | −0.16 / 16.1 | +0.28 / 24.8 |
| **Full Kelly (empirical log-optimal)** | **2.62×** | **2.78×** |
| Full Kelly (Gaussian μ/σ²) | 2.67× | 2.83× |
| Half / quarter Kelly | 1.31× / 0.65× | 1.39× / 0.70× |
| Max feasible f before a wipe-out day | 5.74× | 6.24× |

*Chart: `charts/c1_kelly_vs_bestdays.png`, `charts/c2_metrics_vs_bestdays.png`.*

---

## Phase 4: removing the X best days

| X | Market CAGR | Market f\* | % of base | SCV CAGR | SCV f\* | % of base |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 10.24% | 2.62× | 100% | 14.39% | 2.78× | 100% |
| 1 | 10.08% | 2.58× | 99% | 14.12% | 2.75× | 99% |
| 5 | 9.62% | 2.47× | 95% | 13.38% | 2.64× | 95% |
| 10 | 9.13% | 2.35× | 90% | 12.82% | 2.56× | 92% |
| 20 | 8.30% | 2.13× | 81% | 11.90% | 2.40× | 86% |
| 50 | 6.35% | 1.56× | 60% | 9.56% | 1.96× | 71% |
| 100 | 3.94% | 0.77× | 29% | 6.50% | 1.31× | 47% |
| 200 | 0.16% | 0.00× | 0% | 1.72% | 0.10× | 4% |
| 500 | −7.69% | 0.00× | 0% | −7.95% | 0.00× | 0% |

Volatility barely moves (17.47% → 16.29% at X=100), so essentially the whole effect runs
through the mean. That is expected: `f* ≈ μ/σ²` is a mean-driven statistic.

**Is small-cap value more sensitive? It depends which way you ask.**

* **Relatively: no — the market is more fragile.** At X=100 the market retains 29% of its
  Kelly, small-cap value 47%. Small-cap value starts from a higher mean, so the same number
  of removed days eats a smaller share of it.
* **Absolutely: yes.** At X=100 small-cap value loses 7.46pp of annualised mean vs the
  market's 6.07pp.

Both are true; the relative reading is the one that matters for a leverage decision, and it
says the broad market is the more best-day-dependent of the two.

---

## Phase 5: random-removal control — the effect is entirely the positive tail

2,000 random removals per X, seed 20260907, scored on the same f-grid as the treatment.

| X | Market: best-removed f\* | random f\* mean (sd) | percentile | z |
|---:|---:|---:|---:|---:|
| 10 | 2.35× | 2.62× (0.011) | 0.00% | −23.6 |
| 20 | 2.13× | 2.62× (0.015) | 0.00% | −31.6 |
| 50 | 1.56× | 2.62× (0.024) | 0.00% | −44.5 |
| 100 | 0.77× | 2.62× (0.035) | 0.00% | −52.4 |
| 200 | 0.00× | 2.62× (0.049) | 0.00% | −53.6 |

Random removal is **unbiased and almost inert** — dropping 200 random days moves f\* by a
standard deviation of 0.049×. The best-day result sits below the **0th percentile** of the
null at every X, 7 to 66 standard deviations out. Small-cap value behaves identically.

So this is not a sample-size artifact. It is specifically the extreme positive observations.

*Chart: `charts/c3_random_control.png`.*

---

## Phase 6: the negative tail matters more than the positive tail

Empirical full Kelly f\*, broad market:

| X | remove best | remove worst | remove both |
|---:|---:|---:|---:|
| 0 | 2.62× | 2.62× | 2.62× |
| 20 | 2.13× (−0.49) | **3.48× (+0.86)** | 2.97× (+0.35) |
| 50 | 1.56× (−1.06) | **4.33× (+1.71)** | 3.24× (+0.62) |
| 100 | 0.77× (−1.85) | **5.52× (+2.90)** | 3.59× (+0.97) |

Removing the worst days moves Kelly **~1.7× further than removing the best days**, in the
opposite direction, at every X — through both a higher mean and a relaxed bankruptcy
constraint. Removing best *and* worst together still **raises** f\*, because variance falls
faster than the mean does.

*Chart: `charts/c4_tail_scenarios.png`.*

### Why the counterfactual is physically incoherent

The best days are not scattered through calm markets. For the broad market's 20 best days:

* **95% occurred inside a drawdown deeper than 20%**
* **45% fell within 10 trading days of one of the 20 worst days**
* trailing 21-day volatility on those days was **4.4× the sample average**
* they cluster in 1929–1939 (13 of 20), 1987, 2008, 2020, 2025

The single best day for both series is **1933-03-15** (market +15.67%, small-cap value
+26.70%) — the reopening after the Bank Holiday, deep inside the Depression drawdown.

Best days and worst days are the same volatility regime. A world without the 20 best days,
but with the 20 worst days intact, is not a world that could have existed. This is the main
reason to treat the Phase 4 result as a **sensitivity measurement, not a scenario**.

---

## Phase 7–8: Monte Carlo design

The project's existing MC (`sv_full_analysis.py`, `lev25_montecarlo.py`) is a moving-block
bootstrap. **There is no GARCH or regime-switching model anywhere in the codebase** — a
case-insensitive grep for `garch|regime|arch_model|student` across the folder returns a
single hit, a comment in `sv_vs_mkt_analysis.py` explaining that 12-month blocks partially
preserve regime persistence. So there was no existing sophisticated model to evaluate.
Diagnostics
(`kd_phase8_diag.py`, Ljung-Box Q(20), 5% critical value 31.4):

| scheme | LB(returns) | LB(\|returns\|) | kurtosis | worst day |
|---|---:|---:|---:|---:|
| historical | 162 | **37,297** | 16.1 | −17.44% |
| i.i.d. bootstrap | 17 | **23** | 16.1 | −17.44% |
| block = 20 | 115 | 13,543 | 15.0 | −17.44% |
| block = 60 | 136 | 30,169 | 17.3 | −17.44% |

Resampling actual daily returns inherits the fat tails and the worst day for free, so a
GARCH-t would add parametric assumptions without adding the realism that matters. What the
i.i.d. bootstrap destroys is **volatility clustering**, and that turns out to matter a great
deal for tail risk. Block = 20 (the project default, ≈1 month) is the primary DGP; i.i.d.
and block = 60 are run as robustness.

20,000 paths × 25 years (6,569 trading days), fixed seeds, `(x_t, rf_t)` resampled together.

---

## Phase 9: Monte Carlo results

### Baseline world (X = 0), broad market

| Kelly multiple | f | median CAGR | 5th pct CAGR | median TW | 5th pct TW | median maxDD | P(DD < −90%) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0.25× | 0.65 | 8.10% | +3.90% | $7.0 | $2.60 | −29.5% | 0.0% |
| 0.50× | 1.31 | 11.77% | +3.18% | $16.2 | $2.19 | −55.3% | 0.1% |
| 0.75× | 1.96 | 14.04% | +0.94% | $26.7 | $1.26 | −73.6% | 7.2% |
| **1.00×** | 2.62 | **14.81%** | −2.72% | **$31.6** | $0.50 | −85.7% | **32.9%** |
| 1.25× | 3.27 | 13.98% | −7.69% | $26.3 | $0.14 | −93.0% | 64.8% |
| 1.50× | 3.92 | 11.61% | −13.87% | $15.6 | $0.02 | −97.0% | 86.5% |

Full Kelly does maximise median terminal wealth — the log-optimality check passes — but it
does so with a **one-in-three chance of a 90% drawdown** even in the untouched world.

### Stressed world (X = 50 best days deleted), median 25-year CAGR

| Kelly multiple | Market, sized on **full history** | Market, **re-estimated** | SCV, full history | SCV, re-estimated |
|---|---:|---:|---:|---:|
| 0.25× | 5.64% | 4.80% | 8.14% | 6.87% |
| 0.50× | **6.86%** | 5.98% | 11.16% | 9.63% |
| 0.75× | 6.78% | 6.71% | **12.02%** | 11.38% |
| 1.00× | 5.39% | **6.98%** | 10.64% | **12.03%** |
| 1.25× | 2.70% | 6.79% | 6.91% | 11.59% |
| 1.50× | −1.31% | 6.11% | 1.03% | 9.99% |

This is the operationally important result. An investor who sized at full Kelly from the
untouched history (2.62×) and then lived in the X=50 world gets **5.39%** median CAGR with
31.8% chance of losing money and 1.96% chance of ruin — **worse than sizing at half that
leverage** (6.86%). Re-estimating Kelly correctly on the stressed data recovers most of the
damage (6.98%), which is the point: the loss comes from *over-sizing on a stale estimate*,
not from the stress itself.

*Charts: `charts/c5_mc_terminal_wealth.png`, `c6_mc_cagr.png`, `c6b_mc_cagr_p5.png`,
`c7_mc_drawdown.png`, `c7b_mc_pdd50.png`, `c8_mc_risk_return.png`.*

### Robustness across simulation methodology

Median CAGR is essentially scheme-invariant (within ~0.3pp across i.i.d., block-20 and
block-60). Financing cost is not: re-scoring the same block-20 paths under the
`common/leverage.py` presets (borrowing at effective fed funds + a spread) moves full-Kelly
median CAGR (market, X=0) from 14.81% to 13.16% (futures, + 0.30%), 11.88% (broker,
+ 1.00%) and 11.43% (leveraged ETF, + 0.69% fitted, + 0.91% TER). See *Financing cost* below. **Tail risk is not scheme-invariant
either.** P(drawdown < −90%) at full Kelly, market, X=0:

* i.i.d. bootstrap: **20.1%**
* block = 20: **32.9%**
* block = 60: **39.2%**

The i.i.d. bootstrap understates ruin risk by roughly 40% because it destroys volatility
clustering. Any Kelly analysis that sizes leverage off an i.i.d. simulation is
systematically too aggressive. The *ordering* of the Kelly ladder is stable across all four
schemes.

---

## Addendum: what *is* the optimal leverage? (`kd_phase13_optlev.py`)

Added after the original 12-phase brief. The Phase 7–9 tables express leverage as a multiple
of a reference Kelly; this asks the question directly. Four objectives, swept on a common
grid of f from 0.1× to 4.0× in steps of 0.1, 5,000 paths per point, block-20 bootstrap,
seed 90210, with the same bootstrap draws reused across every f so the curves are smooth and
the argmax is not chasing simulation noise.

| X best removed | Mkt Kelly | Mkt max-median-CAGR | Mkt risk budget | SCV Kelly | SCV max-median-CAGR | SCV risk budget |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 2.62× | 2.70× | 0.90× | 2.78× | 2.80× | 0.70× |
| 5 | 2.47× | 2.40× | 0.90× | 2.64× | 2.70× | 0.70× |
| 10 | 2.35× | 2.40× | 0.80× | 2.56× | 2.60× | 0.70× |
| 20 | 2.13× | 2.10× | 0.80× | 2.40× | 2.40× | 0.60× |
| 50 | 1.56× | 1.60× | 0.70× | 1.96× | 1.90× | 0.60× |
| 100 | 0.77× | 0.80× | 0.60× | 1.31× | 1.30× | 0.50× |
| 200 | 0.00× | 0.10× | 0.50× | 0.10× | 0.20× | 0.40× |
| **change 0→200** | **−100%** | **−96%** | **−44%** | **−96%** | **−93%** | **−43%** |

*Risk budget = largest f with P(max drawdown ≤ −50%) ≤ 25% over 25 years.*

**The two growth-optimal columns agree to within one grid step at every X, on both series.**
The Kelly fraction derived analytically from the reduced *daily* distribution is exactly the
leverage that 25-year simulated paths reward on median CAGR — two independent routes, same
answer. The sweep also reproduces the main Monte Carlo on shared points despite independent
seeds and a quarter of the path count: at f=1.0, X=0, market, P(DD ≤ −50%) = 0.289 vs 0.295,
median CAGR 10.28% vs 10.21%.

**The risk-budget column is the substantive finding.** Holding the constraint fixed, optimal
leverage falls only 0.90× → 0.50× across the entire experiment while the growth-optimal
answer falls to zero. The best-days sensitivity is largely a property of the **growth
objective**, not of leverage chosen under a risk constraint.

Two things worth stating plainly:

* **The 5th-percentile objective is degenerate and should not be used.** Maximising the 5th
  percentile of 25-year CAGR pushes toward cash, because T-bills have almost no downside
  dispersion. It lands at 0.60× at X=0 and hits the grid's 0.10× floor by X=20, where the
  "optimal" portfolio is 10% equities and the 3.1% CAGR is essentially the T-bill return.
  The floor binds, so those figures are a grid lower bound, not a located optimum. Charted
  for completeness only.
* **Not even unlevered equity fits the risk budget.** The market's 0.90× means f = 1.0
  carries a 28.9% chance of a 50% drawdown over 25 years. Not an artifact — 1929–32, 1937,
  1973–74, 2000–02 and 2007–09 all qualified.

An inversion worth noting: at X=0 small-cap value has the **higher** growth-optimal leverage
(2.78× vs 2.62×) but the **lower** risk-budget leverage (0.70× vs 0.90×). Its extra return
justifies more leverage on a pure growth objective and less once drawdowns are constrained,
because its 21.0% volatility breaches the budget sooner.

*Chart: `charts/c9_optimal_leverage.png`. Data: `phase13_leverage_sweep.csv` (full grid),
`phase13_optimal_leverage.csv` (derived optima).*

---

## Phase 14: fractional Kelly vs best-day removal (`kd_phase14_fractions.py`)

**Question.** Is the risk reduction from Half or Quarter Kelly comparable to stress-testing
Full Kelly by deleting its 10, 25 or 100 best days? This was tested as a hypothesis, not
assumed.

### Conclusion

**No. Quarter Kelly does not resemble any of the best-day-removal stress tests.** The two
transformations move *different* metrics, often in opposite directions, so no single number
of removed days reproduces Quarter Kelly's profile.

- **They agree only on CAGR.** Quarter Kelly's CAGR (and terminal wealth) equals Full Kelly
  with about 31 best days removed (market) or 38 (small-cap value).
- **On risk they never agree.** Removing best days leaves volatility almost unchanged, makes
  drawdowns deeper and longer, and cuts Sharpe. Quarter Kelly cuts volatility by 75%, the
  worst month by two-thirds and drawdown length by 44–71%, and leaves Sharpe exactly
  unchanged.
- **The "equivalent X" is inconsistent across metrics.** Matching Quarter Kelly needs X = 0 on
  Sharpe, about 11–22 on Calmar, 31–38 on CAGR, and no X in 0–500 on volatility, max drawdown,
  worst month or drawdown duration.

**What the evidence does support is narrower.** Quarter Kelly is *robust to* best-day
removal, but it is not *equivalent to* it:
- **Lowest dependence on the best days.** Its share of total log wealth creation from the best
  100 days is 50% (market), against 106% for Full Kelly.
- **Positive growth even at the harshest cut.** It still compounds at 4.00% with the best 100
  days gone, where Full Kelly goes negative (−0.80%).
- **The price.** The robustness costs 6.8pp/yr (market) and 10.3pp/yr (small-cap value) of
  CAGR in the untouched history.

That makes Quarter Kelly a defensible **robustness-oriented** leverage level. It is not
evidence that Quarter Kelly "prices in" the loss of the best days, and it is not evidence
that it is optimal.

### Design (fixed before running)

| | |
|---|---|
| Sizing (primary) | `f* = kelly_emp()` on the **original** full sample: market 2.616×, small-cap value 2.789×. Applied unchanged to every dataset. Full / Half / Quarter = 1 / 0.5 / 0.25 × f*. Daily rebalanced, financed at rf, frictionless. |
| Sizing (sensitivity) | Walk-forward expanding window: f* re-estimated at each month-end on the scenario's own retained history, clipped to 0–4×. 10-year warm-up, trading from 1936-07. |
| Removal | Top X by **unlevered total** return over the full sample; the observations are **dropped** and the rest stay in date order. |
| Annualisation | Per-observation moments × the series' own apy (262.8 market, 251.2 small-cap value), exactly as in Phase 4. CAGR = exp(mean log(1+r) · apy) − 1. |
| Final wealth | (1+CAGR)^99.83 from $1: same start date, end date and capital in every scenario. |
| Similarity | RMS of z-scored gaps (each metric scaled by its SD across the 12 scenarios) over CAGR, vol, Sharpe, Sortino, max DD, Calmar, max-DD duration and log final wealth. Equal weights, declared in advance. A risk-only and a return-only version are also reported. |

**Validation, all passing:**
- f* reproduces Phase 4's `kelly_emp`.
- The unlevered rows reproduce Phase 4's CAGR, volatility and Sharpe at every X to 1e-9.
- Removal counts are exact.
- Sharpe and Sortino are identical across Kelly fractions at every X.

### Results, broad market (f* = 2.62×)

| Scenario | Lev | CAGR | Vol | Sharpe | Max DD | Worst month | Max-DD length | $1 → |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Full, original | 2.62× | 14.90% | 45.7% | 0.466 | −99.7% | −61.0% | 24.4 y | 1,054,301 |
| Full, −10 | 2.62× | 12.11% | 44.8% | 0.413 | −99.8% | −66.6% | 26.0 y | 90,596 |
| Full, −25 | 2.62× | 9.07% | 44.2% | 0.351 | −100.0% | −66.6% | 36.1 y | 5,816 |
| Full, −100 | 2.62× | −0.80% | 42.6% | 0.127 | −100.0% | −77.3% | 96.7 y | 0.45 |
| Half, original | 1.31× | 11.82% | 22.9% | 0.466 | −91.8% | −36.5% | 16.1 y | 69,786 |
| Half, −100 | 1.31× | 3.61% | 21.3% | 0.127 | −99.7% | −50.0% | 56.2 y | 34 |
| **Quarter, original** | 0.65× | **8.12%** | **11.4%** | 0.466 | **−68.1%** | **−20.0%** | **13.8 y** | 2,437 |
| Quarter, −10 | 0.65× | 7.40% | 11.2% | 0.413 | −72.3% | −22.2% | 16.4 y | 1,243 |
| Quarter, −25 | 0.65× | 6.61% | 11.0% | 0.351 | −79.3% | −22.2% | 24.7 y | 597 |
| Quarter, −100 | 0.65× | 4.00% | 10.7% | 0.127 | −93.5% | −28.5% | 42.6 y | 50 |

Small-cap value (f* = 2.79×) has the same shape:
- **Full Kelly:** 20.72% CAGR, 55.2% vol, −99.9% max DD, falling to 0.82% at −100.
- **Quarter Kelly:** 10.44% CAGR, 13.8% vol, −75.9% max DD, 7.0-year max-DD length, still
  5.22% at −100.

All 24 rows plus the unlevered reference are in `phase14_scenarios.csv`.

### How close is Quarter (and Half) Kelly to Full Kelly minus X?

RMS z-distance; 0 = identical. For scale, Full vs Full −10 is 0.5 and Full vs Full −100 is
2.9.

| From → Full Kelly at | X = 0 | X = 10 | X = 25 | X = 100 |
|---|---:|---:|---:|---:|
| Market, Quarter — all metrics | 1.60 | 1.44 | 1.47 | 2.73 |
| Market, Quarter — risk only | 2.20 | 2.27 | 2.30 | 3.02 |
| Market, Quarter — return only | 1.15 | 0.75 | **0.68** | 2.43 |
| Market, Half — all metrics | 0.77 | **0.68** | 0.94 | 2.71 |
| SCV, Quarter — all metrics | 1.71 | 1.54 | 1.54 | 2.58 |
| SCV, Quarter — risk only | 2.21 | 2.30 | 2.42 | 2.94 |
| SCV, Half — all metrics | 0.82 | **0.74** | 0.97 | 2.56 |

**Quarter Kelly is at least 1.4 SDs (RMS) from every Full −X scenario.** Its *risk* distance:
- is 2.2–3.0 everywhere;
- is *smallest* at X = 0;
- grows as days are removed, because removal makes Full Kelly riskier, not safer.

The closest match anywhere is return-only: Quarter vs Full −25 (0.68). That is a match on
level of return, not on profile. Half Kelly sits closest to Full −10, again because of CAGR.

**Equivalent X** (`phase14_equivalent_x.csv`) is the number of best days Full Kelly must lose
to match each metric:

| | CAGR / log wealth | Calmar | Sharpe / Sortino | Vol | Max DD | Worst month | DD length |
|---|---:|---:|---:|---:|---:|---:|---:|
| Market, Quarter | 31 | 11 | 0 | none | none | none | none |
| Market, Half | 11 | 7 | 0 | none | none | none | none |
| SCV, Quarter | 38 | 22 | 0 | none | none | none | none |
| SCV, Half | 13 | 10 | 0 | none | none | none | none |

"None" means no X in 0–500 reaches the target. Full −X never gets as calm as Quarter Kelly,
however many days are removed. If the two transformations were related, these columns would
agree; they span 0 to "never".

### What drives the result (`charts/c19_p14_fingerprint.png`)

% change vs Full-original, market:

| | CAGR | Vol | Sharpe | Max DD | Worst month | DD length |
|---|---:|---:|---:|---:|---:|---:|
| Quarter Kelly | −45% | **−75%** | **0%** | −32% | **−67%** | **−44%** |
| Full −25 | −39% | −3% | **−25%** | 0% | +9% | **+48%** |
| Full −100 | −105% | −7% | **−73%** | 0% | +27% | **+296%** |

1. **Leverage reduction and lower volatility are the same effect here.** With constant f,
   volatility scales exactly with f. Quarter Kelly's risk gains all come from exposure.
2. **Sharpe is invariant to the fraction by construction.** Levered excess return = f·x, so
   Sharpe and Sortino cannot change (verified to 1e-9). Best-day removal cuts Sharpe by 11%,
   25% and 73%. **A leverage change can never reproduce a loss of edge.** This is the main
   reason the two cannot be equivalent.
3. **Drawdown behaves differently in each case.** Fractional Kelly shortens and shallows
   drawdowns. Removal lengthens them: the recovery rallies are exactly the days removed. The
   market's 100 best days include 47 rebounds from 1929–33.
4. **Tail dependence is where fractional Kelly genuinely helps** (`phase14_growth_share.csv`).
   The share of all compounded log growth that came from the best X days:

   | Best X days | Full | Half | Unlevered | Quarter |
   |---|---:|---:|---:|---:|
   | Market 10 | 17.7% | 11.7% | 10.4% | 8.7% |
   | Market 25 | 37.6% | 24.6% | 21.8% | 18.1% |
   | Market 100 | **105.8%** | 68.4% | 60.5% | **50.0%** |
   | SCV 100 | 95.7% | 63.8% | 56.0% | 48.9% |

   At Full Kelly, the best 100 days account for *more than all* of the market's growth:
   without them the path loses money. Leverage amplifies tail dependence because
   log(1 + f·x) is concave. Quarter Kelly halves that dependence.

**So the result is a combination of effects:**
- **Leverage reduction** explains the volatility, worst-month and drawdown improvements.
- **Tail dependence** explains why Quarter Kelly *survives* removal (−4.1pp CAGR at −100)
  while Full Kelly does not (−15.7pp).
- **Neither** explains a similarity, because there isn't one.

**The secondary question: the relationship changes as more days are removed.**
- **The CAGR gap narrows, then inverts.** Full leads Quarter by 6.8pp in the original
  history, 2.5pp at −25, and trails by 4.8pp at −100.
- **Half Kelly is overtaken first.** Half and Full are level by −25 (8.80% vs 9.07%), and at
  −100 Quarter beats Half on the market (4.00% vs 3.61%).
- **Why:** each removal lowers the reduced-sample optimum (0.77× for the market at −100, from
  Phase 4). The fraction closest to it wins.

### Sensitivities (`phase14_sensitivity.csv`)

- **Walk-forward sizing (no look-ahead in f\*).**
  - **Leverage path:** mean Full-Kelly leverage is 2.20× (market; range 0.34–2.87×) and
    2.36× (small-cap value).
  - **Resizing in the removal worlds:** the estimator also cuts leverage in those worlds. At
    −100, market Full Kelly averages 0.28×.
  - **Same qualitative answer:** Quarter vs Full −X distances are 1.29–2.24 (market
    1.52–2.24), still nowhere near 0.
  - **Same pattern:** return-only distance is smallest at X = 25 and risk distance stays
    ≥ 1.8.
- **Window matters for the stress.** On the 1936–2026 window with fixed f*, the same
  full-sample-ranked days remove far less: 49 of the market's 100 best days (57 for
  small-cap value) fall before 1936-07. Full −100 still compounds at 8.94% there.
  - Max drawdowns are also much shallower from 1936: Quarter −38%, Full −95%. **Every
    primary-run maximum drawdown is the 1929–32 crash.**
- **Drop vs cash day.** Keeping the removed dates but earning rf changes CAGR by ≤ 0.01pp.
  With 100 of 26,000 days, the three readings (drop / 0% / cash) are practically identical
  here.
- **Financing cost** (`common/leverage.py` presets). Money is lent at the T-bill but
  borrowed at **effective fed funds** plus a spread, on the borrowed portion max(f − 1, 0).
  The leveraged-ETF preset also charges its 0.91% TER on the whole position. Fed funds ran
  0.53pp/yr above the 1-month bill over 1955–2008, and 0.8–1.1pp in the 1970s–80s. The two
  were close after 2009. Before fed funds exists (1954) the gap is set to that 0.53pp
  average. CAGR change against frictionless borrowing, X = 0:

  | | futures (+ 0.30%) | broker (+ 1.00%) | leveraged ETF (+ 0.69%, + 0.91% TER) |
  |---|---:|---:|---:|
  | Full Kelly, market | −1.65pp | −2.92pp | −3.38pp |
  | Half Kelly, market | −0.31pp | −0.55pp | −1.45pp |
  | Quarter Kelly, market | 0 | 0 | −0.98pp (TER only) |
  | Full Kelly, small value | −1.94pp | −3.44pp | −3.87pp |

  Quarter Kelly never borrows, so only a fund's TER touches it. The LETF spread is not
  assumed: `common/validate_leverage.py` fits it to live SSO and UPRO (0.69% over fed funds
  for both, each matching its fund within 0.03pp/yr). The fed-funds benchmark rather than
  the bill is chosen on evidence: SSO's fitted spread in 2006–08 is 0.95% over fed funds but
  1.48% over the bill, against 0.35–1.05% in the later regimes.
- **Costs move the Kelly fraction, not the risk budget.** Phase 13 re-run with the same draws
  (`phase13_optimal_leverage_costs.csv`):

  | | frictionless | broker | leveraged ETF |
  |---|---:|---:|---:|
  | Market f\* (analytic) | 2.62× | 2.12× | 2.22× |
  | Small value f\* | 2.78× | 2.44× | 2.51× |
  | Market f_budget (P(DD ≤ −50%) ≤ 25%) | 0.9× | 0.9× | 0.9× |
  | Small value f_budget | 0.7× | 0.7× | 0.7× |

  Realistic borrowing takes 0.3–0.5× off full Kelly and about 1.5–3.5pp/yr off its median
  CAGR. It leaves the drawdown-budgeted leverage unchanged, because that sits below 1×, where
  nothing is borrowed.

### Limitations of the inference

1. **f\* is in-sample** in the primary run; the walk-forward check changes levels but not the
   conclusion.
2. **The removal ranking uses full-sample look-ahead** by construction, and the removed days
   cluster inside crashes (see *Why the counterfactual is physically incoherent*).
3. **Max drawdown saturates.** Every Full Kelly scenario sits at −99.7% to −100%, so max DD
   cannot discriminate among them. Duration, worst month and volatility carry that load
   instead.
4. **This is one historical path per series.** The distances describe this history; they are
   not confidence statements.
5. **These are research portfolios, gross of costs.** Small-cap value's +0.128 autocorrelation
   inflates its growth, which flatters its Full Kelly the most.
6. **Quarter Kelly is below 1× here** (0.65× market, 0.70× small-cap value). "Quarter Kelly"
   on these series is a *de-levered* equity position, so the comparison is partly equities
   vs equity-plus-cash.

*Charts: `c10`–`c19` (`c10_p14_equity_fractions` … `c19_p14_fingerprint`). Data:
`phase14_*.csv`, `phase14_summary.json`.*

---

## Phase 12: interpretation

**1. How much does Full Kelly fall?** Market 2.62× → 2.13× (20 days) → 1.56× (50) → 0.77×
(100) → 0 (200). Small-cap value 2.78× → 2.40× → 1.96× → 1.31× → 0.10×. Monotone, and
steeper than linear.

**2. Is small-cap value more sensitive?** Not proportionally — it retains more of its Kelly
at every X. It loses more in absolute percentage points, because it has more mean to lose.

**3. Versus random removal?** Not comparable. Random removal is unbiased with sd ≤ 0.08×;
the best-day result is 7–66 sd below it and outside the entire null at every X. The effect
is specifically the positive tail.

**4. How much of compounded growth came from the best days?** Exactly, in log space:

| X best days | % of trading days | share of total log growth (market) | $1 becomes |
|---:|---:|---:|---:|
| 10 | 0.038% | 10.4% | $6,157 (vs $16,924) |
| 20 | 0.076% | 18.4% | $2,851 |
| 50 | 0.191% | 37.0% | $468 |
| 100 | 0.381% | 60.5% | $48 |
| 200 | 0.762% | 98.3% | $1 |

**5. Does it change the simulated future?** Substantially. At X=50 with unchanged leverage,
median 25-year CAGR falls 14.81% → 5.39% and P(ruin) rises 0.07% → 1.96%.

**6. Does fractional Kelly become more attractive?** **Yes, decisively.** Even at X=0, half
Kelly gives 80% of full Kelly's median CAGR with P(DD<−90%) of 0.1% instead of 32.9%, and a
5th-percentile CAGR of +3.18% instead of −2.72%. Under stress the case gets stronger: at
X=50 with stale sizing, half Kelly *beats* full Kelly outright on median CAGR. Fractional
Kelly is the correct response to parameter uncertainty, and this experiment is one more
measurement of how large that uncertainty is.

**7. How robust?** The direction and ordering hold across every X, both series, all three
resampling schemes, both Kelly estimators, and with or without borrowing costs.

### The finding that reframes everything else

Two benchmarks put the best-day sensitivity in proportion:

* **Sampling error.** SE(f\*) = 1/√(n·σ²) = 0.573 analytically; 0.669 by block bootstrap.
  The 95% CI on the market's Kelly is **1.36× to 3.98×** from a century of data. Removing
  the 20 best days is a 0.72-SE move — inside the noise. Removing 50 is 1.6 SE.
* **Regime instability.** 25-year block estimates of the empirical f\* (1926–50 / 1951–75 /
  1976–2000 / 2001–25): market **1.65× / 4.90× / 3.75× / 2.34×**; small-cap value **1.67× /
  6.94× / 7.76× / 1.86×**. The spread across eras dwarfs the best-day effect at any X below
  ~100.

So the honest conclusion is not "Kelly is fragile because of a few good days." It is
**"Kelly is a mean-driven estimator, the mean is barely identified even in 100 years of daily
data, and best-day removal is one of several ways to demonstrate that."** The best-day
experiment happens to be the most vivid demonstration, not the largest source of error.

### Keeping the categories straight

* **Historical evidence** — the baseline statistics, the growth-share decomposition, and the
  observation that best days cluster in crises. These are facts about 1926–2026.
* **Counterfactual stress testing** — Phases 4–6. Selecting "the best days" uses full-sample
  look-ahead by construction. It measures the estimator's sensitivity to positive-tail
  observations. It is **not** evidence that such days will be absent in future, and the
  scenario is internally incoherent anyway (§Phase 6).
* **Monte Carlo assumptions** — the block bootstrap assumes the future resembles a
  reshuffling of the past at ~1-month dependence scale. It cannot produce a regime the
  sample never contained, and it has no valuation or mean-reversion mechanism.
* **Forecasting** — none of this is a forecast. Nothing here estimates future returns.

### Limitations

1. Fama-French research portfolios, **not investable funds**: gross of costs, spreads,
   taxes, fees; `SMALL HiBM` holds untradeable microcaps. A ≈1.09%/yr DFSVX-implied drag
   would lower every small-cap-value Kelly level; the *shape* of the curves is unaffected by
   a constant drag, the intercept is not.
2. Small-cap value's +0.128 daily autocorrelation inflates its measured growth and biases
   its Kelly upward relative to what a fund could capture.
3. Frictionless borrowing at the T-bill rate in the primary results. The futures, broker
   and leveraged-ETF financing presets (fed funds + spread) cut full-Kelly median CAGR by
   ≈1.7, 2.9 and 3.4pp (market) and pull f\* from 2.62× down to 2.12–2.22×. See *Financing
   cost*.
4. Block bootstrapping the reduced series introduces ~X seams; minor at X ≤ 200.
5. Daily rebalancing is assumed throughout, matching the leveraged-ETF mechanics used
   elsewhere in this project. Real implementations rebalance imperfectly.
6. **Full Kelly is not a recommendation.** Even in the untouched sample it carries a 32.9%
   probability of a 90% drawdown over 25 years.
