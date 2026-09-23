# 2026-09-11: A standalone portfolio suite

**Decision.** Copy everything behind [[portfolio-dashboard]] into one self-contained folder,
`C:\Python Datoteke\portfolio_suite\`, with every path relative to that folder. The original
project folders were **copied, not moved**, and are untouched.

## Why

The dashboard build reached into four sibling folders through hardcoded absolute paths
(`efficient_core_9060`, `SCV_leverage_analysis`, `testfolio_data`, and the repo root for
`F-F_Research_Data_Factors_daily.csv`). Renaming any of them broke the build. The user asked
for one organized folder that runs on its own.

## Choices worth knowing

- **Shared inputs go in `shared_data\`.** Ken French factors and 6 portfolios, Damodaran
  `histretSP.xls`, and testfolio series. Before this, `ec_data.py` read them out of
  `SCV_leverage_analysis`. See [[efficient-core-9060]].
- **Only the five real testfolio files were copied, under their correct names.** The
  `(1)`-suffixed files became `FFSCV_daily.csv` / `VTSIM_L2_daily.csv`, and the stale
  NTSDSIM duplicates were left behind. `tf_load` and `kd_data.load_ffscv` still verify by
  content, so this is safe. It closes the misleading-filename item in [[tech-debt]] *inside
  the suite only*.
- **Generation-1 SCV scripts are archived unchanged** in `scv_leverage\legacy_gen1\`. They
  still point at the dead scratchpad. See [[gen1-scv-outputs-lost]].
- **Paths are computed from `__file__`** rather than hardcoded. This is a deliberate departure
  from the repo's absolute-path convention, and it is the whole point of the suite.
- **`run.py` is the single entry point.** It rebuilds the dashboard and opens it. Set
  `RERUN_STUDIES = True` at the top to regenerate both studies.

## Found while doing it: the original dashboard was stale

The first suite build did **not** reproduce the original `data.json`. Every difference was in
`us_scv`: the monthly panel, its scored rows in all windows, and the Kelly-study tables.
Cause: the original `data.json` was built at 10:38 on 2026-09-10, but `kd_data.py` switched
`scv_total` to the testfolio FFSCV splice at 11:44 and `kelly_bestdays\` was regenerated at
11:45. The original `portfolio_dashboard.html`, and the artifact published from it, still show
the **pre-splice** SCV series. The suite's build is current. All Efficient Core data matched
exactly.

## Links

[[portfolio-dashboard]] · [[scv-leverage-analysis]] · [[testfolio-cross-check]] · [[tech-debt]]
