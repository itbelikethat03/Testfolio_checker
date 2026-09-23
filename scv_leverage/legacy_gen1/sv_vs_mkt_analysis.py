"""
Small-Cap Value vs. Market: rolling 10-year historical analysis + Monte Carlo.

Data sources (Ken French Data Library, CRSP-based, value-weighted, daily, in %):
  - F-F_Research_Data_Factors_daily.csv   -> Mkt-RF, RF        (market factor)
  - 6_Portfolios_2x3_Daily.csv            -> SMALL HiBM        (Small-Cap Value portfolio,
                                              i.e. small-ME / high book-to-market, value-weighted)

Both series are converted from daily arithmetic % returns to decimal daily returns,
then compounded to MONTHLY returns (21-trading-day-ish calendar-month compounding)
before running the rolling-window and Monte Carlo analysis. Monthly frequency is used
because 10-year rolling windows over ~26,000+ daily overlapping observations would be
extremely serially correlated and because block-bootstrap block sizes are far more
interpretable in months (e.g. "1-year blocks" = 12 months) than in trading days.
"""
import numpy as np
import pandas as pd

ROOT = r"c:\Python Datoteke"
SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"

# ---------------------------------------------------------------------------
# 1. Load and align data
# ---------------------------------------------------------------------------
mkt = pd.read_csv(rf"{ROOT}\F-F_Research_Data_Factors_daily.csv", skiprows=4, encoding="utf-8-sig")
mkt.columns = ["date", "Mkt-RF", "SMB", "HML", "RF"]
mkt["date"] = pd.to_datetime(mkt["date"], format="%Y%m%d", errors="coerce")
mkt = mkt.dropna(subset=["date"])
for c in ["Mkt-RF", "SMB", "HML", "RF"]:
    mkt[c] = pd.to_numeric(mkt[c], errors="coerce")
mkt = mkt.dropna(subset=["Mkt-RF", "RF"]).reset_index(drop=True)
mkt["Mkt_Total"] = (mkt["Mkt-RF"] + mkt["RF"]) / 100.0  # total market return, decimal

sv = pd.read_csv(rf"{SCRATCH}\ff6\6_Portfolios_2x3_Daily.csv", skiprows=18, nrows=26293 - 19)
sv.columns = ["date", "SMALL_LoBM", "ME1_BM2", "SMALL_HiBM", "BIG_LoBM", "ME2_BM2", "BIG_HiBM"]
sv["date"] = pd.to_datetime(sv["date"], format="%Y%m%d", errors="coerce")
sv = sv.dropna(subset=["date"])
sv["SV_Total"] = pd.to_numeric(sv["SMALL_HiBM"], errors="coerce") / 100.0  # Small-Cap Value, decimal
sv = sv.dropna(subset=["SV_Total"]).reset_index(drop=True)

df = pd.merge(mkt[["date", "Mkt_Total"]], sv[["date", "SV_Total"]], on="date", how="inner")
df = df.sort_values("date").reset_index(drop=True)
print(f"Merged daily data: {df['date'].min().date()} to {df['date'].max().date()}, n={len(df)} days")

# ---------------------------------------------------------------------------
# 2. Convert to monthly compounded returns
# ---------------------------------------------------------------------------
df = df.set_index("date")
monthly_mkt = (1 + df["Mkt_Total"]).resample("ME").prod() - 1
monthly_sv = (1 + df["SV_Total"]).resample("ME").prod() - 1
monthly = pd.DataFrame({"Mkt": monthly_mkt, "SV": monthly_sv}).dropna()
print(f"Monthly data: {monthly.index.min().date()} to {monthly.index.max().date()}, n={len(monthly)} months")

mkt_arr = monthly["Mkt"].to_numpy()
sv_arr = monthly["SV"].to_numpy()
n_months = len(monthly)
window = 120  # 10 years of months

# ---------------------------------------------------------------------------
# 3. Historical rolling 10-year windows
# ---------------------------------------------------------------------------
mkt_log = np.log1p(mkt_arr)
sv_log = np.log1p(sv_arr)
mkt_cum_log = np.concatenate([[0.0], np.cumsum(mkt_log)])
sv_cum_log = np.concatenate([[0.0], np.cumsum(sv_log)])

n_windows = n_months - window + 1
mkt_window_ret = np.exp(mkt_cum_log[window:] - mkt_cum_log[:-window] if window < len(mkt_cum_log) else []) - 1
# simpler explicit loop-free calc:
mkt_window_ret = np.exp(mkt_cum_log[window:n_months+1] - mkt_cum_log[0:n_windows]) - 1
sv_window_ret = np.exp(sv_cum_log[window:n_months+1] - sv_cum_log[0:n_windows]) - 1

diff_hist = sv_window_ret - mkt_window_ret
underperform_hist = diff_hist < 0
pct_underperform_hist = underperform_hist.mean() * 100

start_dates = monthly.index[0:n_windows]
end_dates = monthly.index[window-1:n_months]

print("\n=== HISTORICAL ROLLING 10-YEAR WINDOWS ===")
print(f"Number of overlapping 10-year (120-month) windows: {n_windows}")
print(f"Date range of window starts: {start_dates.min().date()} to {start_dates.max().date()}")
print(f"SV underperformed Market in {underperform_hist.sum()} / {n_windows} windows "
      f"({pct_underperform_hist:.1f}%)")
print(f"SV had negative absolute 10yr return in {(sv_window_ret < 0).sum()} / {n_windows} windows "
      f"({(sv_window_ret < 0).mean()*100:.1f}%)")

for thr in [0.10, 0.20, 0.30]:
    p = (diff_hist <= -thr).mean() * 100
    print(f"SV underperformed Market by >= {int(thr*100)}% (cumulative) in {p:.1f}% of windows")

print("\nDiff distribution (SV cumulative return - Mkt cumulative return), historical windows:")
for q in [5, 25, 50, 75, 95]:
    print(f"  p{q}: {np.percentile(diff_hist, q)*100:.1f}%")

worst_idx = np.argmin(diff_hist)
best_idx = np.argmax(diff_hist)
print(f"\nWorst relative underperformance window: {start_dates[worst_idx].date()} to {end_dates[worst_idx].date()}, "
      f"diff={diff_hist[worst_idx]*100:.1f}% (SV={sv_window_ret[worst_idx]*100:.1f}%, Mkt={mkt_window_ret[worst_idx]*100:.1f}%)")
print(f"Best relative outperformance window: {start_dates[best_idx].date()} to {end_dates[best_idx].date()}, "
      f"diff={diff_hist[best_idx]*100:.1f}% (SV={sv_window_ret[best_idx]*100:.1f}%, Mkt={mkt_window_ret[best_idx]*100:.1f}%)")

# ---------------------------------------------------------------------------
# 4. Monte Carlo simulation (moving-block bootstrap on monthly returns,
#    preserving cross-sectional correlation between SV and Mkt each month,
#    and preserving serial correlation / vol clustering within blocks)
# ---------------------------------------------------------------------------
rng = np.random.default_rng(42)
N_SIMS = 100_000
BLOCK = 12  # 1-year blocks to partially preserve autocorrelation/regime persistence
N_BLOCKS_NEEDED = int(np.ceil(window / BLOCK))
n_possible_starts = n_months - BLOCK + 1

starts = rng.integers(0, n_possible_starts, size=(N_SIMS, N_BLOCKS_NEEDED))
offsets = np.arange(BLOCK)
idx = (starts[:, :, None] + offsets[None, None, :]).reshape(N_SIMS, -1)[:, :window]

sim_mkt = mkt_arr[idx]   # (N_SIMS, window)
sim_sv = sv_arr[idx]

mkt_cum = np.prod(1 + sim_mkt, axis=1) - 1
sv_cum = np.prod(1 + sim_sv, axis=1) - 1
diff_mc = sv_cum - mkt_cum
underperform_mc = diff_mc < 0
pct_underperform_mc = underperform_mc.mean() * 100

print("\n=== MONTE CARLO (moving-block bootstrap, 12-month blocks, N=100,000) ===")
print(f"SV underperformed Market in {pct_underperform_mc:.1f}% of simulated 10-year paths")
print(f"SV had negative absolute 10yr return in {(sv_cum < 0).mean()*100:.1f}% of simulations")

for thr in [0.10, 0.20, 0.30]:
    p = (diff_mc <= -thr).mean() * 100
    print(f"SV underperformed Market by >= {int(thr*100)}% (cumulative) in {p:.1f}% of simulations")

print("\nDiff distribution (SV cumulative return - Mkt cumulative return), Monte Carlo:")
for q in [5, 25, 50, 75, 95]:
    print(f"  p{q}: {np.percentile(diff_mc, q)*100:.1f}%")

print(f"\nMedian SV 10yr cumulative return: {np.median(sv_cum)*100:.1f}%")
print(f"Median Mkt 10yr cumulative return: {np.median(mkt_cum)*100:.1f}%")

# ---------------------------------------------------------------------------
# 5. IID bootstrap for comparison (no autocorrelation preserved)
# ---------------------------------------------------------------------------
idx_iid = rng.integers(0, n_months, size=(N_SIMS, window))
sim_mkt_iid = mkt_arr[idx_iid]
sim_sv_iid = sv_arr[idx_iid]
mkt_cum_iid = np.prod(1 + sim_mkt_iid, axis=1) - 1
sv_cum_iid = np.prod(1 + sim_sv_iid, axis=1) - 1
diff_iid = sv_cum_iid - mkt_cum_iid
print(f"\n=== IID bootstrap (no autocorrelation) sanity check ===")
print(f"SV underperformed Market in {(diff_iid<0).mean()*100:.1f}% of simulations")

# ---------------------------------------------------------------------------
# 6. Summary stats on monthly series for methodology write-up
# ---------------------------------------------------------------------------
print("\n=== MONTHLY RETURN SUMMARY STATS ===")
for name, arr in [("Market", mkt_arr), ("Small Value", sv_arr)]:
    print(f"{name}: mean={arr.mean()*100:.3f}%/mo, std={arr.std()*100:.3f}%/mo, "
          f"skew={pd.Series(arr).skew():.2f}, kurt={pd.Series(arr).kurtosis():.2f}, "
          f"ann.return={( (1+arr.mean())**12-1)*100:.2f}%, ann.vol={arr.std()*np.sqrt(12)*100:.2f}%")
corr = np.corrcoef(mkt_arr, sv_arr)[0, 1]
print(f"Correlation(Mkt, SV) monthly: {corr:.3f}")
# lag-1 autocorrelation
print(f"Lag-1 autocorr Mkt: {pd.Series(mkt_arr).autocorr(1):.3f}, SV: {pd.Series(sv_arr).autocorr(1):.3f}")
