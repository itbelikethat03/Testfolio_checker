"""
2x Leveraged Market vs Small-Cap Value (SCV) vs Market, 25-year horizon.

REUSED FROM backtest.py (verbatim formulas / defaults):
  - Leverage-cost model from simulate_leveraged_etf() / compute_leverage_grid_historical():
        daily_cost = (leverage - 1) * (RF + spread_daily) + expense_daily
        lev_ret    = leverage * Mkt_Total - daily_cost
        NAV        = cumprod(max(0, 1 + lev_ret))
    i.e. daily-rebalanced leverage, financing the borrowed (leverage-1) fraction at
    RF + spread, plus a drag for the fund's expense ratio. This bakes in volatility
    drag automatically via daily compounding (does NOT need a separate "drag" term).
  - UI defaults used as-is: leverage=2.0x, spread_annual=0.40%, expense_ratio_annual=0.95%
    (Streamlit sidebar defaults in backtest.py).
  - Moving-block bootstrap methodology (block_bootstrap_indices): resampling
    contiguous blocks of daily (Mkt-RF, RF) observations with replacement.
    Default block_size=20 trading days (~1 month), matching the backtest.py UI default.
  - Data loading/prep conventions from load_default_data()/prepare_returns_data()
    (skiprows=4, %Y%m%d dates, /100 to decimal, Mkt_Total = Mkt-RF + RF).

MODIFIED / EXTENDED for this comparison:
  - A third return series (SCV, the SMALL HiBM portfolio) is added and bootstrapped
    using the SAME block-start indices as Mkt-RF/RF (not redrawn independently), so
    the historical Market/SCV correlation is preserved in the simulation exactly as
    backtest.py's own model preserves Mkt-RF/RF correlation. backtest.py has no SCV
    concept at all, so this pairing is new.
  - The Monte Carlo loop is rewritten in chunked vectorized NumPy (not the numba
    @jit simulate_paths_jit) so it can hold 100,000 x 6,300-day x 3-series paths
    without exceeding memory -- simulate_paths_jit itself only carries two series
    (leveraged, market) and was not built for a third bootstrapped series.
  - Horizon changed from backtest.py's default 40yr Monte Carlo projection to 25yr,
    and the historical analysis is a NEW rolling-25-year-window scan (backtest.py's
    rolling-window tool sweeps a leverage GRID at one fixed window length via
    compute_rolling_window_analysis; this reuses that same fixed-window daily-
    compounding logic but compares Market/2x/SCV instead of a leverage grid).
"""
import numpy as np
import pandas as pd
import json

ROOT = r"c:\Python Datoteke"
SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"
OUT = {}
TRADING_DAYS = 252

# =============================================================================
# 1. LOAD DATA -- same conventions as backtest.py's load_default_data / prepare_returns_data
# =============================================================================
mkt = pd.read_csv(rf"{ROOT}\F-F_Research_Data_Factors_daily.csv", skiprows=4, encoding="utf-8-sig")
mkt.columns = ["date", "Mkt-RF", "SMB", "HML", "RF"]
mkt["date"] = pd.to_datetime(mkt["date"], format="%Y%m%d", errors="coerce")
mkt = mkt.dropna(subset=["date"])
for c in ["Mkt-RF", "SMB", "HML", "RF"]:
    mkt[c] = pd.to_numeric(mkt[c], errors="coerce")
mkt = mkt.dropna(subset=["Mkt-RF", "RF"]).reset_index(drop=True)
mkt["Mkt_RF_d"] = mkt["Mkt-RF"] / 100.0
mkt["RF_d"] = mkt["RF"] / 100.0
mkt["Mkt_Total"] = mkt["Mkt_RF_d"] + mkt["RF_d"]

sv = pd.read_csv(rf"{SCRATCH}\ff6\6_Portfolios_2x3_Daily.csv", skiprows=18, nrows=26293 - 19)
sv.columns = ["date", "SMALL_LoBM", "ME1_BM2", "SMALL_HiBM", "BIG_LoBM", "ME2_BM2", "BIG_HiBM"]
sv["date"] = pd.to_datetime(sv["date"], format="%Y%m%d", errors="coerce")
sv = sv.dropna(subset=["date"])
sv["SV_Total"] = pd.to_numeric(sv["SMALL_HiBM"], errors="coerce") / 100.0
sv = sv.dropna(subset=["SV_Total"]).reset_index(drop=True)

df = pd.merge(mkt[["date", "Mkt_RF_d", "RF_d", "Mkt_Total"]], sv[["date", "SV_Total"]], on="date", how="inner")
df = df.sort_values("date").reset_index(drop=True)
print(f"Daily merged: {df['date'].min().date()} to {df['date'].max().date()}, n={len(df)}")

# ---- leverage cost parameters, reused verbatim from backtest.py sidebar defaults ----
LEVERAGE = 2.0
SPREAD_ANNUAL = 0.004     # 0.40%
EXPENSE_ANNUAL = 0.0095   # 0.95%
spread_daily = SPREAD_ANNUAL / TRADING_DAYS
expense_daily = EXPENSE_ANNUAL / TRADING_DAYS

mkt_rf = df["Mkt_RF_d"].to_numpy()
rf = df["RF_d"].to_numpy()
mkt_total = df["Mkt_Total"].to_numpy()
sv_total = df["SV_Total"].to_numpy()
dates = df["date"].to_numpy()
n_days_total = len(df)

daily_cost = (LEVERAGE - 1.0) * (rf + spread_daily) + expense_daily
lev_ret = LEVERAGE * mkt_total - daily_cost
lev_factors = np.maximum(1.0 + lev_ret, 0.0)
mkt_factors = np.maximum(1.0 + mkt_total, 0.0)
sv_factors = np.maximum(1.0 + sv_total, 0.0)

lev_nav = np.cumprod(lev_factors)
mkt_nav = np.cumprod(mkt_factors)
sv_nav = np.cumprod(sv_factors)

n_zero_lev = int((lev_factors <= 0).sum())
print(f"2x-leveraged daily factor <= 0 (ruin day) count: {n_zero_lev}")

# =============================================================================
# 2. FULL-SAMPLE STATS (Market, 2x Market, SCV)
# =============================================================================
def full_sample_stats(nav, ret_series, name):
    # annualization convention reused verbatim from backtest.py's calc_stats():
    # ann_return = (1+total_return) ** (trading_days / len(returns_series)) - 1
    total_years = (dates[-1] - dates[0]).astype('timedelta64[D]').astype(float) / 365.25  # display only
    cagr = nav[-1] ** (TRADING_DAYS / len(nav)) - 1
    ann_vol = ret_series.std() * np.sqrt(TRADING_DAYS)
    peak = np.maximum.accumulate(nav)
    dd = nav / peak - 1.0
    mdd = dd.min()
    return dict(name=name, cagr=cagr, ann_vol=ann_vol, mdd=mdd, final=nav[-1], years=total_years)

avg_rf_ann = (1 + rf).prod() ** (TRADING_DAYS / n_days_total) - 1

s_mkt = full_sample_stats(mkt_nav, mkt_total, "Market")
s_lev = full_sample_stats(lev_nav, lev_ret, "2x Market")
s_sv = full_sample_stats(sv_nav, sv_total, "SCV")
for s in (s_mkt, s_lev, s_sv):
    s["sharpe"] = (s["cagr"] - avg_rf_ann) / s["ann_vol"]

print("\n=== FULL-SAMPLE STATS (99.8yr) ===")
print(f"{'Metric':<20}{'Market':>14}{'2x Market':>14}{'SCV':>14}")
print(f"{'CAGR':<20}{s_mkt['cagr']*100:>13.2f}%{s_lev['cagr']*100:>13.2f}%{s_sv['cagr']*100:>13.2f}%")
print(f"{'Ann. vol':<20}{s_mkt['ann_vol']*100:>13.2f}%{s_lev['ann_vol']*100:>13.2f}%{s_sv['ann_vol']*100:>13.2f}%")
print(f"{'Sharpe':<20}{s_mkt['sharpe']:>14.2f}{s_lev['sharpe']:>14.2f}{s_sv['sharpe']:>14.2f}")
print(f"{'Max drawdown':<20}{s_mkt['mdd']*100:>13.2f}%{s_lev['mdd']*100:>13.2f}%{s_sv['mdd']*100:>13.2f}%")
print(f"{'Final $1':<20}{s_mkt['final']:>14,.0f}{s_lev['final']:>14,.0f}{s_sv['final']:>14,.0f}")

OUT["full_sample"] = {k: {kk: (float(vv) if not isinstance(vv, str) else vv) for kk, vv in s.items()}
                       for k, s in [("mkt", s_mkt), ("lev", s_lev), ("sv", s_sv)]}
OUT["full_sample"]["rf_ann"] = float(avg_rf_ann)

np.save(rf"{SCRATCH}\l25_dates.npy", dates.astype('datetime64[D]').astype(np.int64))
np.save(rf"{SCRATCH}\l25_mkt_nav.npy", mkt_nav)
np.save(rf"{SCRATCH}\l25_lev_nav.npy", lev_nav)
np.save(rf"{SCRATCH}\l25_sv_nav.npy", sv_nav)

# =============================================================================
# 3. ROLLING 25-YEAR HISTORICAL WINDOWS (daily basis, stepped monthly ~21td for tractability)
# =============================================================================
WINDOW_DAYS = 25 * TRADING_DAYS  # 6300
STEP_DAYS = 21  # ~monthly step -- windows still overlap heavily but this keeps the scan fast
starts = np.arange(0, n_days_total - WINDOW_DAYS, STEP_DAYS)
n_windows = len(starts)
print(f"\nRolling 25yr windows: {n_windows} (window={WINDOW_DAYS}td, step={STEP_DAYS}td)")

mkt_cum = mkt_nav[starts + WINDOW_DAYS] / mkt_nav[starts]
lev_cum = lev_nav[starts + WINDOW_DAYS] / lev_nav[starts]
sv_cum = sv_nav[starts + WINDOW_DAYS] / sv_nav[starts]

mkt_ann = mkt_cum ** (1/25) - 1
lev_ann = lev_cum ** (1/25) - 1
sv_ann = sv_cum ** (1/25) - 1

win_start_dates = pd.to_datetime(dates[starts])
win_end_dates = pd.to_datetime(dates[starts + WINDOW_DAYS])

lev_minus_mkt = lev_ann - mkt_ann
sv_minus_mkt = sv_ann - mkt_ann
lev_minus_sv = lev_ann - sv_ann

n_lev_beats_mkt = (lev_ann > mkt_ann).sum()
n_sv_beats_mkt = (sv_ann > mkt_ann).sum()
n_lev_beats_sv = (lev_ann > sv_ann).sum()
n_sv_beats_lev = (sv_ann > lev_ann).sum()

print(f"2x Market beats Market:   {n_lev_beats_mkt}/{n_windows} ({n_lev_beats_mkt/n_windows*100:.1f}%)")
print(f"SCV beats Market:         {n_sv_beats_mkt}/{n_windows} ({n_sv_beats_mkt/n_windows*100:.1f}%)")
print(f"2x Market beats SCV:      {n_lev_beats_sv}/{n_windows} ({n_lev_beats_sv/n_windows*100:.1f}%)")
print(f"SCV beats 2x Market:      {n_sv_beats_lev}/{n_windows} ({n_sv_beats_lev/n_windows*100:.1f}%)")

for name, arr in [("Market", mkt_ann), ("2x Market", lev_ann), ("SCV", sv_ann)]:
    print(f"{name}: worst={arr.min()*100:.2f}%  best={arr.max()*100:.2f}%  "
          f"p5={np.percentile(arr,5)*100:.2f}%  p25={np.percentile(arr,25)*100:.2f}%  "
          f"p50={np.percentile(arr,50)*100:.2f}%  p75={np.percentile(arr,75)*100:.2f}%  p95={np.percentile(arr,95)*100:.2f}%")

OUT["rolling25"] = dict(
    n_windows=int(n_windows), window_days=int(WINDOW_DAYS), step_days=int(STEP_DAYS),
    n_lev_beats_mkt=int(n_lev_beats_mkt), pct_lev_beats_mkt=round(n_lev_beats_mkt/n_windows*100,1),
    n_sv_beats_mkt=int(n_sv_beats_mkt), pct_sv_beats_mkt=round(n_sv_beats_mkt/n_windows*100,1),
    n_lev_beats_sv=int(n_lev_beats_sv), pct_lev_beats_sv=round(n_lev_beats_sv/n_windows*100,1),
    n_sv_beats_lev=int(n_sv_beats_lev), pct_sv_beats_lev=round(n_sv_beats_lev/n_windows*100,1),
    stats={}
)
for name, arr in [("mkt", mkt_ann), ("lev", lev_ann), ("sv", sv_ann)]:
    OUT["rolling25"]["stats"][name] = dict(
        worst=round(float(arr.min())*100,2), best=round(float(arr.max())*100,2),
        p5=round(float(np.percentile(arr,5))*100,2), p25=round(float(np.percentile(arr,25))*100,2),
        p50=round(float(np.percentile(arr,50))*100,2), p75=round(float(np.percentile(arr,75))*100,2),
        p95=round(float(np.percentile(arr,95))*100,2),
    )

worst_idx_lev = np.argmin(lev_ann); best_idx_lev = np.argmax(lev_ann)
worst_idx_sv = np.argmin(sv_ann); best_idx_sv = np.argmax(sv_ann)
worst_idx_mkt = np.argmin(mkt_ann); best_idx_mkt = np.argmax(mkt_ann)
print(f"\nStrongest SCV 25yr window: {win_start_dates[best_idx_sv].date()} to {win_end_dates[best_idx_sv].date()}, SCV ann={sv_ann[best_idx_sv]*100:.2f}%")
print(f"Strongest Market 25yr window: {win_start_dates[best_idx_mkt].date()} to {win_end_dates[best_idx_mkt].date()}, Mkt ann={mkt_ann[best_idx_mkt]*100:.2f}%")

OUT["rolling25"]["best_sv_window"] = dict(start=str(win_start_dates[best_idx_sv].date()), end=str(win_end_dates[best_idx_sv].date()), sv_ann=round(float(sv_ann[best_idx_sv])*100,2))
OUT["rolling25"]["best_mkt_window"] = dict(start=str(win_start_dates[best_idx_mkt].date()), end=str(win_end_dates[best_idx_mkt].date()), mkt_ann=round(float(mkt_ann[best_idx_mkt])*100,2))

np.save(rf"{SCRATCH}\l25_win_end_dates.npy", win_end_dates.astype('int64'))
np.save(rf"{SCRATCH}\l25_mkt_ann.npy", mkt_ann)
np.save(rf"{SCRATCH}\l25_lev_ann.npy", lev_ann)
np.save(rf"{SCRATCH}\l25_sv_ann.npy", sv_ann)
np.save(rf"{SCRATCH}\l25_starts.npy", starts)

print("\nStage 1 (data load, full-sample stats, rolling windows) complete.")
with open(rf"{SCRATCH}\l25_summary_partial.json", "w") as f:
    json.dump(OUT, f, indent=2, default=str)
