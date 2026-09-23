# 2026-09-23: Small-cap value is Ken French SMALL HiBM, never spliced

Supersedes: the 2026-09-10 change that made `kd_data.py` splice testfolio's FFSCV (to
2025-10-31) with our `SMALL HiBM` tail. That splice is described in
[[2026-09-11-portfolio-suite]] and [[testfolio-cross-check]].

**Decision.** `scv_leverage\kd_data.py` takes one small-value source at a time:

- `SCV_SOURCE = "kf"` is the default: Ken French `SMALL HiBM`, value-weighted 2×3.
- `SCV_SOURCE = "testfolio"` uses testfolio's FFSCV only, ending 2025-10-31.
- `SCV_HAIRCUT` optionally subtracts a constant investability drag per year.

The two are **never joined** into one series.

## Why

- **Ours matches the primary source.** Our daily `SMALL HiBM` compounded to month-end matches
  Ken French's own separately built **monthly** file: correlation 0.9999, 14.29% vs 14.39%
  CAGR over 1926–2026. `kd_phase2_validate.py` now asserts this on every run.
- **FFSCV matches none of the Ken French 2×3 columns.** Monthly correlation with `SMALL HiBM`
  is 0.968, at 12.95% vs 14.15%. It is an undocumented, more liquid small-value
  construction, not a better copy of the same series.
- **A splice joins two different portfolios.** It puts a level break into every statistic
  that spans 2025-10.
- **The splice had left the study inconsistent.** Six phase outputs predated it (2026-09-07)
  and two postdated it, so the dashboard mixed the two. Every output now records its
  configuration in `_manifest.json` (see [[2026-09-23-suite-overhaul]]).

**Principle adopted:** where a primary source exists (Ken French's files, a live fund), it is
the referee. Testfolio is an independent second opinion, not the truth.

## Numbers

| | KF (default) | testfolio FFSCV |
|---|---:|---:|
| CAGR 1926–2026 | 14.39% | 12.95% (to 2025-10) |
| Full Kelly f\* | 2.78× | 2.79× |

Investable reality sits between them. DFSVX captured **1.03pp/yr** less than `SMALL HiBM`
over 1993–2026. AVUV beat it by 1.58pp/yr over 2019–2026, but seven years is too short to
read much into. See [[reconstructions]].

## Links

[[scv-leverage-analysis]] · [[testfolio-cross-check]] · [[portfolio-dashboard]]
