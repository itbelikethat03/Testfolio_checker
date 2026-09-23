# Portfolio suite

Everything behind the portfolio dashboard: the Efficient Core 90/60 study, the SCV Kelly/best-days
study, reconstructions of real leveraged and return-stacked ETFs, the testfolio cross-check, a
testfolio-style backtester, and the dashboard that combines them. Every path is relative to this
folder, so it can be moved or zipped as a unit.

## Run

```
pip install -r requirements.txt
python run.py
```

This rebuilds the dashboard from the studies' outputs (seconds), then serves it at
**http://localhost:8000** and opens it in Chrome. Press Ctrl+C to stop the server. To serve the
last build without rebuilding, run `python -m http.server 8000 --bind 127.0.0.1 -d dashboard`.
The server is bound to 127.0.0.1, so it is not reachable from the network.

To regenerate every study first, set `RERUN_STUDIES = True` at the top of `run.py` (slow: the Monte
Carlo steps take ~40 min). Every study script records the configuration it ran under in its output
folder's `_manifest.json`; if outputs from different configurations are mixed, the dashboard build
prints `[stale]` lines and the page shows a warning banner.

Ken French, FRED and testfolio inputs are cached in `shared_data\` and `efficient_core\data_cache\`.
ETF prices come from Yahoo on first use and are cached from then on.

## The backtester

```
python -m common.backtest --list
python -m common.backtest "US_MKT:0.9,UST_LADDER_FUT:0.6u,CASH:0.1" --rebal quarterly --band 0.05 --ter 0.002
python -m common.backtest "US_MKT:1.5,CASH:-0.5" --financing broker --rebal monthly --start 1990
python -m common.backtest "SPY:0.6,TLT:0.4" --rebal annual
```

`name:weight` is a funded leg; a trailing `u` marks an unfunded (futures) leg, whose returns must be
excess returns (the `*_FUT` assets). A negative `CASH` weight is a loan, charged the `--financing`
preset's borrowing rate (e.g. `broker` = fed funds + 1%, `letf` = 1.107 × fed funds + 0.43%). Any name that is not in the registry is loaded as a Yahoo ticker. Output uses
testfolio's metric conventions (see `testfolio_check\VERIFY.md`).

## Configuration switches

| Where | Switch | Effect |
|---|---|---|
| `scv_leverage\kd_data.py` | `SCV_SOURCE = "kf"` / `"testfolio"` | Small-cap value series for the Kelly study. `kf` (default) is Ken French SMALL HiBM, which matches Ken French's own monthly file; `testfolio` is FFSCV (a different, undocumented construction ending 2025-10-31). They are never spliced. |
| `scv_leverage\kd_data.py` | `SCV_HAIRCUT` | Annual investability drag subtracted from small value (DFSVX implies ~1.0%/yr) |
| `common\leverage.py` | `PRESETS`, `LETF_SPREAD` | What borrowing costs. Loans are charged **effective fed funds** plus a spread (cash earns the T-bill; fed funds ran ~0.33pp/yr above the 3-month bill before 2009): `frictionless` (borrow at rf), `futures` (+0.30%), `broker` (+1.00%), `letf` (1.107 × fed funds + 0.43%, fitted to live SSO/UPRO across rate regimes, + 0.91% TER, daily reset) |

## Layout

| Folder | What |
|---|---|
| `common\` | Shared code: `paths`, `ff` (the one Ken French parser), `metrics` (every statistic, testfolio conventions included), `backtest` (the portfolio engine and CLI), `assets` (named return series), `leverage` (financing cost model), `validate_leverage` (fits the LETF spread to live SSO/UPRO), `manifest` |
| `shared_data\` | Inputs used by more than one study: Ken French factors + 6 portfolios, Damodaran `histretSP.xls`, testfolio daily series |
| `efficient_core\` | `ec_*.py`, `data_cache\`, `output\` (REPORT.md, METHODOLOGY.md, CSVs, charts) |
| `scv_leverage\` | `kd_*.py`, `dfsvx_compare.py`, `kelly_bestdays\` (REPORT.md, METHODOLOGY.md, CSVs, charts) |
| `scv_leverage\legacy_gen1\` | Generation-1 SCV scripts, **archived as-is**. They read and write a dead scratchpad path, so they will not run without editing |
| `reconstructions\` | `recon.py`: NTSX, NTSI, NTSE, GDE, RSSB, RSST, SSO, UPRO rebuilt on the engine and checked against the live funds; investable small-value drag. Output in `reconstructions\output\` |
| `testfolio_check\` | External validation against testfol.io (`tf_*.py`, COMPARISON.md, VERIFY.md) |
| `dashboard\` | `build_data.py` → `data.json` → `build_dashboard.py` + `template.html` → `index.html` (the page the server serves) |

Edit `dashboard\template.html`, never `index.html`. The HTML is regenerated on every build.

## Checking a change

```
python verify_suite.py              # recompute ~90 load-bearing numbers, diff against verify_baseline.json
python verify_suite.py --snapshot   # accept the current numbers as the new baseline
```

A refactor must reproduce every number to 1e-9. A change meant to move numbers is re-snapshotted
deliberately, and the diff printed before that is the record of what moved.

## Study run order (what `RERUN_STUDIES` does)

```
efficient_core:   ec_data -> ec_validate -> ec_analysis -> ec_montecarlo -> ec_charts -> ec_ntsd
scv_leverage:     kd_phase2_validate -> kd_phase346_removal -> kd_phase5_control -> kd_phase8_diag
                  -> kd_phase79_mc -> kd_phase12_cluster -> kd_phase12_context
                  -> kd_phase13_optlev -> kd_phase14_fractions -> kd_phase11_validate -> kd_charts
common:           validate_leverage
reconstructions:  recon
testfolio_check:  tf_verify -> tf_compare
dashboard:        build_data -> build_dashboard
```

Context, reasoning, and caveats live in the Obsidian vault in `context\` (open it in Obsidian with *Open folder as vault*; start at `context\MOC.md`). It is part of the repo, so it syncs with the code.

## Moving this to another machine

This folder is self-contained (data caches and study outputs included), so a plain copy
works, but git gives you version history and easy two-way sync. At ~48 MB it's small enough
to commit as-is, cached data and outputs included, so the new machine can run `python run.py`
immediately without re-downloading anything from FRED / Ken French / Yahoo.

**On this machine:**

```
cd "C:\Python Datoteke\portfolio_suite"
git init
git add -A
git commit -m "Initial commit"
```

Then create an empty **private** repo on GitHub (github.com/new — don't add a README,
license or .gitignore there, since you already have files) and push:

```
git remote add origin https://github.com/<your-username>/<repo-name>.git
git branch -M main
git push -u origin main
```

GitHub will prompt for credentials on push; a personal access token (Settings → Developer
settings → Personal access tokens) is easier than a password, or use `gh auth login` if you
have the GitHub CLI installed.

**On the home PC:**

```
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
pip install -r requirements.txt
python run.py
```

**Keeping both machines in sync afterwards:**

```
git pull            # before you start working, on whichever machine
... make changes ...
git add -A
git commit -m "what changed"
git push            # before you switch machines
```

If you edit the suite from both machines without always pushing/pulling first, git will
tell you about a conflict rather than silently losing anything — just don't skip the pull.
