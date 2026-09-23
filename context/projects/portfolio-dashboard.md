# Portfolio dashboard

**Status:** current, rebuilt 2026-09-23.
**Location:** `portfolio_suite\dashboard\` (a git repo since 2026-09-23, pushed to GitHub so it
can be worked on from a second machine).
**Run:** `python run.py` rebuilds from the studies' outputs in seconds and serves
**http://localhost:8000** (bound to 127.0.0.1) in Chrome. `RERUN_STUDIES = True` regenerates
every study first, which takes ~45 min, mostly the Kelly Monte Carlo.
**Output:** `dashboard\index.html`. Edit `template.html`, never `index.html`.

The original `C:\Python Datoteke\portfolio_dashboard\` folder is stale and not maintained; see
[[2026-09-11-portfolio-suite]].

Combines [[efficient-core-9060]], [[scv-leverage-analysis]] and [[reconstructions]] into one
comparison surface. See [[2026-09-10-combining-two-studies]] for the reasoning.

## Sections

| # | Section | Source |
|---|---|---|
| 01–05 | Matrix, leverage, stress, Monte Carlo, sensitivity | both studies |
| 06 | NTSD, simulated from 1970 (drawn in ink: the palette has 8 slots) | `efficient_core\output\ntsd\` |
| 07 | Fractional Kelly vs best days; sensitivity selector includes the futures / broker / LETF cost presets | `kelly_bestdays\phase14_*` |
| 08 | **Real funds**: live validation, long histories with testfolio comparison, financing presets, SSO/UPRO fit, investable small value | `reconstructions\output\` |
| 09 | Notes | template |

## Build pipeline

`build_data.py` → `data.json` → `build_dashboard.py` + `template.html` → `index.html`.

- **Staleness guard.** `build_data.py` compares each output folder's `_manifest.json` with
  the current configuration (`kd_data.config()`, `ec_data.EC_CONFIG`, the LETF parameters). It
  prints `[stale]` lines, and the page shows a red banner when outputs from different settings
  would be mixed. This exists because the dashboard once silently mixed pre- and post-splice
  small-value outputs.
- Metrics are computed through `common/metrics.py`, one definition for every portfolio (see
  [[metric-conventions]]).
- **Verifying a build:** run headless Chrome with `--dump-dom` on `index.html` and check
  that the tables have rows. That catches a JS error that static checks would miss.

## Design notes

- Charts are hand-written inline SVG with no chart library, so the page works offline.
- The palette is [[chart-palette]], shared with `ec_charts.py`.
- Metric tables use **daily** data and charts a **monthly** panel. A table's max drawdown is
  therefore deeper than the chart's. This is footnoted rather than smoothed away.

## Open

- The risk/return scatter has no table view of its own; its values are in the matrix table.
- `montecarlo_paths.npz` and `phase79_terminal_wealth.npz` are unused. A terminal-wealth
  histogram would need them downsampled first.
- The Efficient Core `REPORT.md` has tables with no backing CSV. See [[tech-debt]].
