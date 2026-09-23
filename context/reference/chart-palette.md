# Chart palette

One categorical palette across matplotlib PNGs and the web dashboard, so a portfolio is the
same colour wherever it appears.

## The eight slots

Colourblind-validated as an ordered set — **the ordering is the safety mechanism, not
cosmetic**. Adjacent slots are guaranteed separable; non-adjacent pairs are not, which is why
series must be assigned in slot order rather than picked freely.

| Slot | Hue | Light | Dark | Portfolio |
|---|---|---|---|---|
| 1 | blue | `#2a78d6` | `#3987e5` | Reconstructed 90/60 |
| 2 | orange | `#eb6834` | `#d95926` | Developed equities |
| 3 | aqua | `#1baf7a` | `#199e70` | Developed equities 1.5× |
| 4 | yellow | `#eda100` | `#c98500` | Developed small-cap value |
| 5 | magenta | `#e87ba4` | `#d55181` | ACWI |
| 6 | green | `#008300` | `#008300` | US total market |
| 7 | violet | `#4a3aa7` | `#9085e9` | Actual NTSG (live) |
| 8 | red | `#e34948` | `#e66767` | US small-cap value |

`build_data.py` sorts the portfolio registry by slot for exactly this reason:

```python
PORTFOLIOS.sort(key=lambda p: p["slot"])
```

## Supporting roles

| Role | Light | Dark |
|---|---|---|
| Diverging positive / negative | `#2a78d6` / `#e34948` | `#3987e5` / `#e66767` |
| Diverging midpoint (neutral) | `#f0efec` | `#383835` |
| Chart surface | `#fcfcfb` | `#1a1a19` |
| Primary ink | `#0b0b0b` | `#ffffff` |
| Secondary ink | `#52514e` | `#c3c2b7` |
| Muted (axis, labels) | `#898781` | `#898781` |
| Gridline | `#e1e0d9` | `#2c2c2a` |
| Baseline / axis | `#c3c2b7` | `#383835` |

Status colours are **reserved** and never reused as a series: good `#0ca30c`,
warning `#fab219`, serious `#ec835a`, critical `#d03b3b`.

## Where it is used

- `efficient_core_9060/ec_charts.py` — slots 1–5 and 7, same hexes.
- `SCV_leverage_analysis/kd_charts.py` — a **different** pair (`#3c6b8f` market,
  `#a8792f` small value) plus a blue sequential ramp. Not aligned with the table above; the
  dashboard remaps those two series to slots 6 and 8. Worth reconciling if the PNGs are ever
  regenerated alongside the dashboard.
- `portfolio_dashboard/template.html` — as CSS custom properties `--s1` … `--s8`, redefined
  under both `@media (prefers-color-scheme: dark)` and `[data-theme="dark"]`.

## Rules worth not relearning

- **Never a dual-axis chart.** Two measures of different scale get two charts, small
  multiples, or indexing to a common base.
- **Sequential = one hue, light→dark. Diverging = two hues + a neutral grey midpoint.**
  Never a rainbow; never a hue at the diverging midpoint.
- **Colour follows the entity, never its rank.** Filtering a series out must not repaint the
  survivors.
- **Past 8 categories**, fold the tail into "Other" or facet into small multiples. Never
  generate a 9th hue.
- A legend is always present for ≥2 series; direct-label selectively, never a number on
  every point.

## Links

- [[portfolio-dashboard]] · [[efficient-core-9060]] · [[scv-leverage-analysis]]
