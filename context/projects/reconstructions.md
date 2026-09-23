# Fund reconstructions

**Location:** `portfolio_suite\reconstructions\recon.py` → `reconstructions\output\`
(one JSON per fund, `recon_summary.csv`, `investable_scv.json`). Built 2026-09-23.
Shown in dashboard section 08.

Each fund's structure comes from its prospectus and runs on `common/backtest.py` twice:

- **live:** built from ETF proxies (each proxy's expense ratio added back) and scored against
  the real fund over its life. This tests the structure.
- **history:** the same structure on the longest research series available. This is only
  meaningful when the live gap is small.

## Live validation (real minus model, pp/yr)

| Fund | Structure | Gap | Verdict |
|---|---|---:|---|
| NTSX | 0.9 US + 0.6 UST ladder | +0.08 | ✓ |
| NTSI | 0.9 EAFE + 0.6 UST ladder | +0.43 | ✓ roughly |
| RSSB | 1.0 global + 1.0 UST ladder | −0.22 | ✓ |
| SSO / UPRO | 2× / 3× S&P, daily reset | −0.10 / −0.24 | ✓ (fitted; see [[2026-09-23-letf-rate-sensitive]]) |
| GDE | 0.9 US + 0.9 gold futures | −0.88 | TE 9%, rough |
| **NTSE** | 0.9 EM + 0.6 UST ladder | **+2.05** | ✗ The real fund is also more volatile (20.0% vs 18.2%), so its equity sleeve is not a plain cap-weighted EM index. EEM and IEMG give the same gap. |
| **RSST** | 1.0 US + 1.0 trend | **−5.64** | ✗ DBMF is only a stand-in for RSST's own trend model |

## Things worth not re-deriving

- **Calendars.** The bond market (FRED) closes on days stocks trade. Put every leg on the
  equity calendar with `backtest.on_calendar`, which carries the level forward, never
  `index.intersection`. The intersection silently cost NTSX 0.77pp/yr of its real return
  before this was fixed.
- **SSO/UPRO histories start in 1954** (the first DTB3 date), not 1926.
- **Testfolio's SSOSIM/UPROSIM equal the real funds after launch.** Compare pre-launch only.
- **TERs marked "(verify)"** in `recon.py` (NTSI, NTSE, RSSB, RSST) were not re-read from
  current prospectuses. The live gap absorbs any error in them.
- **Investable small value:** DFSVX captured 1.03pp/yr less than `SMALL HiBM` (1993–2026).
  This is the evidence behind `kd_data.SCV_HAIRCUT`.

## Links

[[leverage-cost-model]] · [[portfolio-dashboard]] · [[2026-09-23-suite-overhaul]] · [[testfolio-cross-check]]
