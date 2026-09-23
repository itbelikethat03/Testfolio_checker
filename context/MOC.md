# Map of content

The index. Every note in the vault is reachable from here.

## Active work

- [[portfolio-dashboard]]: the combined comparison surface (`python run.py`). **Current.**
- [[reconstructions]]: real leveraged / return-stacked ETFs rebuilt and checked against the live funds.

## Studies

- [[efficient-core-9060]]: does levering bonds pay? WisdomTree 90/60 reconstructed and tested.
- [[scv-leverage-analysis]]: how much of the Kelly criterion rests on a handful of days?

## Decisions (newest first)

- [[2026-09-23-letf-rate-sensitive]]: LETF financing = 1.107 × fed funds + 0.43%, fitted to live SSO/UPRO; testfolio's rule is too punitive.
- [[2026-09-23-borrow-at-fed-funds]]: borrow at fed funds, lend at the T-bill; the cause of the "slightly too optimistic" levered results.
- [[2026-09-23-scv-source-kf]]: small value = Ken French SMALL HiBM by default, testfolio switchable, never spliced. *Supersedes the FFSCV splice.*
- [[2026-09-23-suite-overhaul]]: correctness audit, bugs fixed, `common/` package, backtester, manifests, regression harness.
- [[2026-09-23-vault-in-repo]]: the vault moved into `portfolio_suite\context`. *Supersedes the location in 2026-09-10-obsidian-vault.*
- [[2026-09-11-ntsd-synthetic]]: NTSD simulated 1970+ with the NTSG drift engine. (Financing since refined by 2026-09-23-borrow-at-fed-funds.)
- [[2026-09-11-portfolio-suite]]: everything behind the dashboard copied into one standalone folder. (Its splice remarks are superseded.)
- [[2026-09-10-combining-two-studies]]: how the two studies were joined without inventing comparability.
- [[2026-09-10-obsidian-vault]]: why this vault exists and what shape it takes.

## Reference

- [[leverage-cost-model]]: the financing presets, the fed-funds gap, how to refit.
- [[testfolio-cross-check]]: testfolio's metric conventions; why FFSCV and SSOSIM/UPROSIM differ from ours.
- [[data-schemas]]: exact column names and units of the output files.
- [[metric-conventions]]: how CAGR, Sharpe, Sortino and max drawdown are defined here.
- [[chart-palette]]: the validated categorical palette, shared by matplotlib and the dashboard.
- [[tech-debt]]: known problems worth fixing, with severity.

## Not yet written

Links below point nowhere yet. Each is a note worth writing.

- [[gen1-scv-outputs-lost]]: the August 2026 analyses whose outputs went to a dead scratchpad.
- [[data-sources]]: where FRED / Ken French / Damodaran / Yahoo / testfolio inputs come from and how they refresh.
