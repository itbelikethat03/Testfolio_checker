# SCV leverage analysis

**Location:** `portfolio_suite\scv_leverage\` (the maintained copy). The original
`C:\Python Datoteke\SCV_leverage_analysis\` is no longer maintained.
**Small-value source:** Ken French `SMALL HiBM` (`kd_data.SCV_SOURCE = "kf"`), never spliced;
see [[2026-09-23-scv-source-kf]].
**Leverage costs:** the frictionless Kelly headline is unchanged. Realistic financing is
reported alongside it via the futures / broker / LETF presets; see [[leverage-cost-model]].

Two generations of work exist. Only the second has surviving outputs.

## Generation 2 — Kelly / best days (current)

**Question:** how much of the Kelly criterion rests on a handful of days?

**Report:** `kelly_bestdays\REPORT.md` · **Methods:** `kelly_bestdays\METHODOLOGY.md`
**Data:** Fama-French daily, 1926-07-01 → 2026-04-30. 26,233 days, 99.83 years.
**Validation:** all 27 checks in `kd_phase11_validate.py` pass.

Note **262.78 observations/year, not 252** — the NYSE traded Saturdays until 1952. The
annualisation factor is computed from the sample rather than assumed.

### The answer

Yes, strongly — but the sensitivity is **not special to the best days**, and it is smaller
than two error sources already in the estimate.

| | US market | US small value |
|---|---|---|
| Full-sample Kelly f* | 2.62× | 2.78× |
| minus 20 best days (0.076% of days) | 2.13× | 2.40× |
| 95% CI on f* from ordinary sampling error | **1.36× – 3.98×** | 1.58× – 4.09× |
| range across four 25-year blocks | **1.65× – 4.98×** | 1.66× – 11.19× |

Removing the 20 best days is a **0.72 standard-error** move. Estimation noise and regime
instability both move it further. The honest framing is not "Kelly is fragile because of a
few good days" — it is *"Kelly is a mean-driven estimator, the mean is barely identified even
in 100 years of daily data, and best-day removal is one vivid way to demonstrate that."*

### Things worth not re-deriving

- **The counterfactual is physically incoherent.** 95% of the market's 20 best days occurred
  inside a >20% drawdown; 45% fell within 10 trading days of a worst-20 day; trailing 21-day
  vol on those days was 4.4× average. Best days and worst days are the *same volatility
  regime*. Single best day for both series: **1933-03-15** (market +15.67%, SCV +26.70%) —
  the reopening after the Bank Holiday. Treat Phase 4 as a sensitivity measurement, never a
  scenario.
- **Removing the worst days moves Kelly ~1.7× further, in the opposite direction.** Removing
  best *and* worst together still *raises* f*, because variance falls faster than the mean.
- **The i.i.d. bootstrap understates ruin risk by ~40%.** P(DD < −90%) at full Kelly:
  20.1% i.i.d. / 32.9% block-20 / 39.2% block-60. Any Kelly analysis sized off an i.i.d.
  simulation is systematically too aggressive. Block-20 (~1 month) is the primary DGP.
- **The risk-budget result is the substantive one.** Holding P(DD ≤ −50%) ≤ 25% fixed,
  optimal leverage falls only 0.90× → 0.50× across the whole experiment, while the
  growth-optimal answer falls to zero. Best-day sensitivity is largely a property of the
  *growth objective*, not of leverage chosen under a risk constraint.
- **Not even unlevered equity fits the risk budget.** The market's 0.90× means f = 1.0
  carries a 28.9% chance of a 50% drawdown over 25 years. Not an artifact — 1929–32, 1937,
  1973–74, 2000–02 and 2007–09 all qualified.
- **`f_p5` is degenerate. Do not use it.** Maximising the 5th percentile of 25-year CAGR
  pushes toward cash and binds on the grid's 0.10× floor from X = 20 onward.
- **Realistic financing moves Kelly but not the risk budget** (2026-09-23). Borrowing at fed
  funds + spread:

  | | frictionless | broker (ff + 1%) | LETF (1.107·ff + 0.43%) |
  |---|---:|---:|---:|
  | Market f\* | 2.62× | 2.12× | 2.17× |
  | Small value f\* | 2.78× | 2.44× | 2.48× |
  | Full-Kelly median 25y CAGR, market | 14.81% | 11.88% | 11.19% |
  | f_budget (P(DD ≤ −50%) ≤ 25%) | 0.9× / 0.7× | unchanged | unchanged |

  The risk-budgeted leverage sits below 1×, where nothing is borrowed.
- **Each series runs on its own calendar.** Use `series_frame(df, key)`, never
  `ann_factor(df)` on the union frame. `ann_factor` now raises on a frame with gaps. This bug
  sat in phase 13 until 2026-09-23 and would have fed NaN Saturdays into the bootstrap if the
  testfolio source were selected.

### Bugs it found in the older project code

Documented in Phase 2, worth remembering because the older scripts still contain them:

- `compute_kelly_metrics()` in `backtest.py` / `mf_and_kelly.py` maximises `E[log(1 + f·x)]`,
  dropping the `rf` term. Measured impact at daily frequency: **0.000×**. Harmless here.
- `np.clip(f_kelly, -1.0, 10.0)` silently caps. **Would bind** on SCV's 1976–2000 block,
  which estimates at 11.19× — the function would have reported 10.00× with no warning.
- Gaussian `μ/σ²` used without checking the distribution. Daily excess kurtosis is 16.1
  (market) / 24.8 (SCV). New code uses the empirical log-optimal f* instead.

### Run order

```
kd_data.py (library)
kd_phase2_validate.py -> kd_phase346_removal.py -> kd_phase5_control.py
kd_phase8_diag.py -> kd_phase79_mc.py (~27 min) -> kd_phase12_*.py
kd_phase13_optlev.py (~14 min) -> kd_phase14_fractions.py (~5 min)
-> kd_phase11_validate.py -> kd_charts.py
```

Each phase records its configuration in `kelly_bestdays\_manifest.json`.

## Generation 1 — leveraged portfolio series (outputs lost)

August 2026. `sv_*`, `lev25_*`, `div_*`, `mf_*`, `portfolios_*` — 2× levered market vs SCV,
SCV vs bonds as diversifiers for a 2× core, managed futures, 1.5× multi-asset portfolios.

**All outputs were written to a session scratchpad that is now empty.** The scripts also
cannot be re-run as-is: they read `ff6/`, `ie_data.xls`, `tsmom.xlsx`, `histretSP.xls` from
that dead path. Those four files now sit in the project folder, so **a path change at the top
of each script would fix it**. See [[gen1-scv-outputs-lost]].

## The cost caveat that matters most

`SMALL HiBM` is a Fama-French **research portfolio**, not a fund: value-weighted, gross of
all costs, holding untradeable microcaps. `dfsvx_compare.py` puts the DFSVX-implied drag at
**≈1.09%/yr** (1.03pp in the reconstructions' 1993–2026 check). It is **not applied** by
default; set `kd_data.SCV_HAIRCUT = 0.0109` to apply it. Its daily lag-1
autocorrelation is **+0.128** (market: +0.046) — stale microcap pricing, which inflates
measured geometric growth further.

**Every small-cap-value figure in this study, and on [[portfolio-dashboard]], is optimistic
by at least that much.** The *shape* of the curves is unaffected by a constant drag; the
intercept is not.

**Independently corroborated 2026-09-10.** Testfolio's `FFSCV` — a more liquid small-value
construction — runs **1.44pp/yr below** our `SMALL HiBM` (12.95% vs 14.39%), with lower
volatility and lower autocorrelation (0.078 vs 0.101). Same order of magnitude as the
≈1.09%/yr DFSVX drag, reached from a completely different direction. Our series is correctly
built and is the right measure of the factor premium *gross of implementation*. It also
matches Ken French's own monthly file (correlation 0.9999), which FFSCV does not. Full
analysis: [[testfolio-cross-check]]. The 2026-09-10 splice of FFSCV into this study was
reversed on 2026-09-23 ([[2026-09-23-scv-source-kf]]).

Also measured there for the first time: the **1,158 pre-1952 Saturday sessions average
+0.3145% each**, against +0.0073% for other days of that era — the documented weekend
effect. They are real sessions and must be kept; deleting them would drop the SCV CAGR to
10.41%.

## Links

- [[efficient-core-9060]] · [[portfolio-dashboard]] · [[data-schemas]] · [[chart-palette]]
