# Tech debt

Known problems, worst first. Not a backlog: a list of things that will bite if forgotten.
Items in `C:\Python Datoteke` outside the suite are listed separately at the end.

## Portfolio suite

### NTSE and RSST do not reconstruct

**Severity: medium.** See [[reconstructions]]. NTSE misses its live fund by +2.05pp/yr, and the
real fund is more volatile than the model, so its equity sleeve is not a plain EM index. RSST
misses by −5.6pp/yr because DBMF is only a stand-in for its own trend model. Their long
histories on the dashboard are therefore not trustworthy.

### Pre-2000 leveraged history may still be generous

**Severity: medium.** The LETF cost model is fitted on 2006+ fund data. It cannot see the
higher daily-rebalancing costs of the 1970s–80s, or crisis cost spikes like 2020–21, which is
excluded from the rate fit. See [[2026-09-23-letf-rate-sensitive]].

### Unverified TERs in `recon.py`

**Severity: low.** NTSI, NTSE, RSSB and RSST expense ratios are marked "(verify)". They were
not re-read from current prospectuses. The live gaps absorb any error in them.

### Not every Kelly phase is importable

**Severity: low.** `kd_phase2_validate` and `kd_phase13_optlev` have a `main()`. The other
`kd_phase*.py` scripts still run their work at import time, so importing one to reuse a helper
runs a multi-minute job.

### Report tables with no backing CSV (Efficient Core)

**Severity: low.** These sections of `output\REPORT.md` are printed but never written to a
CSV, so [[portfolio-dashboard]] can only quote them:

- 2: bond ETF validation
- 5: break-even grids
- 7: volatility drag
- 8: underperformance spells
- 9: recovery times
- 10: inflation regimes
- 12: currency coverage

Adding `to_csv` calls in `ec_analysis.py` would fix it. `REPORT.md` also predates the
2026-09-23 changes (see [[efficient-core-9060]]).

### Generation-1 SCV outputs are unrecoverable

**Severity: low** (archived). `scv_leverage\legacy_gen1\` writes to a dead scratchpad. See
[[gen1-scv-outputs-lost]].

### Palette divergence

**Severity: cosmetic.** `kd_charts.py` uses its own two-colour pair. See [[chart-palette]].

### Closed 2026-09-23

- **Misleading duplicate testfolio files:** closed inside the suite; everything is loaded by
  content.
- **Fragile `skiprows`/`nrows` Ken French parsing:** closed by `common/ff.py`.
- **Stale outputs mixed silently:** closed by the manifests.

See [[2026-09-23-suite-overhaul]].

## Outside the suite (`C:\Python Datoteke`)

### Secrets in source

**Severity: high.** `asana_QR.py` holds an Asana token and `personalfinance.py` holds an API
key `AZJNgh…eoKd`. Move both to `.env`, **rotate the keys**, and keep them out of any git repo.

### `backtest.py` is misfiled

**Severity: low.** `Error list,Q,A,P,S\backtest.py` is a Streamlit GARCH backtester in the
service-desk folder, containing the Kelly bugs documented in [[scv-leverage-analysis]].

### Duplicate downloads in `testfolio_data`

**Severity: low.** The original `C:\Python Datoteke\testfolio_data` still holds misnamed
NTSDSIM copies. The suite's `shared_data\testfolio_data` is clean.

## Links

- [[MOC]] · [[portfolio-dashboard]]
