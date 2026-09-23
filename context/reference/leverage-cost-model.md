# Leverage cost model

Defined once in `common/leverage.py` and used by the Kelly study, `lev15`, NTSD, the
reconstructions and the backtester CLI.

```
r = rf + L·x − max(L−1, 0) · (gap + (β−1)·ff_acc + spread·dt) − TER·dt

x       excess return of the asset over rf (the bill)
gap     fed-funds accrual − rf accrual, per period      (borrow at fed funds, lend at the bill)
ff_acc  fed-funds accrual (act/360), per period          (for β ≠ 1)
```

| Preset | Borrowing rate | TER | Reset | Basis |
|---|---|---:|---|---|
| `frictionless` | rf (the bill) | 0 | — | the textbook Kelly case |
| `futures` | fed funds + 0.30% | 0 | periodic | assumption, equity-index futures |
| `broker` | fed funds + 1.00% | 0 | periodic | Interactive Brokers Pro tiers: +1.5% below $100k, +1.0% to $1M, +0.5% to $50M |
| `letf` | **1.107 × fed funds + 0.43%** | 0.91% | daily | **fitted** to live SSO/UPRO, see [[2026-09-23-letf-rate-sensitive]] |

## Facts worth not re-deriving

- **Fed funds − bill gap:** +0.33pp/yr over the 3-month bill and +0.53pp over Ken French's
  1-month bill for 1955–2008; about 0 since 2009. Before 1954-07 (no daily fed funds), the
  bill plus that average is used (`PRE_DFF_GAP`).
- **Treasury-futures sleeves finance at the bill**, not fed funds, because they price off
  Treasury repo. The NTSX live match supports this.
- **Testfolio's leveraged sims** charge ≈ 1.27 × fed funds + 0.67% before launch. The real
  funds say that is too punitive at 4% rates. See [[testfolio-cross-check]].
- **Refit when new fund data arrive:** run `python common\validate_leverage.py` and copy its
  suggested `LETF_SPREAD` / `LETF_RATE_BETA` into `leverage.py`. The manifests then flag every
  output that needs re-running.
- In the Kelly scripts, costs enter as one per-day **borrow premium** array per preset
  (`Financing.borrow_premium`). It is resampled with the same bootstrap indices as the
  returns, so the cost presets re-score identical paths.

## Links

[[2026-09-23-borrow-at-fed-funds]] · [[2026-09-23-letf-rate-sensitive]] · [[scv-leverage-analysis]] · [[reconstructions]]
