# 2026-09-23: Correctness audit, shared `common/` package, backtester, fund reconstructions

**Decision.** Audit the suite's numbers against primary data and testfolio, fix what was
wrong, consolidate the duplicated code into `common/`, and add three features: a
testfolio-style backtester, reconstructions of real leveraged ETFs, and a data-backed
leverage cost model.

## What the audit found correct

- **Metric conventions vs testfolio:** 49/60 cells match exactly. The other 11 all use the
  risk-free rate, and testfolio's rf is ~13bp higher than ours.
- **NTSX reconstruction vs the live fund:** within ~0.05pp/yr over 8 years.
- **Ken French daily data:** it matches Ken French's own monthly files. `SMALL HiBM` has
  correlation 0.9999; for the market, daily compounding runs 0.09pp/yr *below* monthly.

## Bugs fixed

| Bug | Effect |
|---|---|
| SCV series spliced from two different portfolios; six outputs predated the splice | see [[2026-09-23-scv-source-kf]] |
| `kd_phase13_optlev` / `phase2` / `phase11` used one obs/yr for the union of two calendars | a re-run would have fed NaN Saturdays into the bootstrap. `ann_factor` now refuses gappy frames |
| `levered_equity` drift check used the pre-move exposure | `lev15` +0.09pp/yr too high |
| `lev15` borrowed at the FX-exposed 4-currency cash basket, no spread | now USD fed funds + 0.30% |
| DTB3 (discount basis) mixed with bond-equivalent yields | 90/60 −0.04pp, US 90/60 −0.07pp |
| `tf_compare.py` pointed at a non-existent `scv_leverage\ff6` path | it would have crashed |
| COMPARISON.md said NTSD "is not a 90/60" | NTSD is 0.9 US + 0.6 *equity* futures |
| Reconstructions intersected stock and bond-market calendars | this deleted Columbus/Veterans Day stock returns. Fixed with `backtest.on_calendar` (level carry-forward) |
| Borrowing charged at bills, not fed funds | see [[2026-09-23-borrow-at-fed-funds]] |

## Structure added

- `common/`:
  - `paths` and `ff`: one Ken French parser that finds blocks by title, not row numbers.
  - `metrics`: `ec_metrics` moved here, plus testfolio's conventions via `ppy=252` and
    `testfolio_table`.
  - `backtest`: the engine plus a CLI. It reproduces the original 90/60 loop bit-for-bit.
  - `assets` (named return series), `leverage`, `validate_leverage` and `manifest`.
- `_manifest.json` in every output folder. The dashboard shows a banner when outputs come
  from different configurations.
- `verify_suite.py`: recomputes 88 load-bearing numbers and diffs them against
  `verify_baseline.json`. A refactor must reproduce all of them to 1e-9.
- `reconstructions/recon.py`: see [[reconstructions]].
- Dashboard section 08, "Real funds".

## Mistake worth remembering

The regression baseline was once re-snapshotted **after** the engine swap instead of before.
That left the harness unable to prove the refactor. It was recovered by running the original
loop verbatim against the engine (max difference 0.0). **Snapshot, then refactor.**

## Links

[[MOC]] · [[portfolio-dashboard]] · [[reconstructions]] · [[leverage-cost-model]] · [[tech-debt]]
