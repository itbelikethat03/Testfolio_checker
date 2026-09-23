import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import json

ROOT = r"c:\Python Datoteke"
SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"
OUT = {}

# =============================================================================
# 1. LOAD DATA
# =============================================================================
mkt = pd.read_csv(rf"{ROOT}\F-F_Research_Data_Factors_daily.csv", skiprows=4, encoding="utf-8-sig")
mkt.columns = ["date", "Mkt-RF", "SMB", "HML", "RF"]
mkt["date"] = pd.to_datetime(mkt["date"], format="%Y%m%d", errors="coerce")
mkt = mkt.dropna(subset=["date"])
for c in ["Mkt-RF", "SMB", "HML", "RF"]:
    mkt[c] = pd.to_numeric(mkt[c], errors="coerce")
mkt = mkt.dropna(subset=["Mkt-RF", "RF"]).reset_index(drop=True)
mkt["Mkt_Total"] = (mkt["Mkt-RF"] + mkt["RF"]) / 100.0
mkt["RF_d"] = mkt["RF"] / 100.0

sv = pd.read_csv(rf"{SCRATCH}\ff6\6_Portfolios_2x3_Daily.csv", skiprows=18, nrows=26293 - 19)
sv.columns = ["date", "SMALL_LoBM", "ME1_BM2", "SMALL_HiBM", "BIG_LoBM", "ME2_BM2", "BIG_HiBM"]
sv["date"] = pd.to_datetime(sv["date"], format="%Y%m%d", errors="coerce")
sv = sv.dropna(subset=["date"])
sv["SV_Total"] = pd.to_numeric(sv["SMALL_HiBM"], errors="coerce") / 100.0
sv = sv.dropna(subset=["SV_Total"]).reset_index(drop=True)

df = pd.merge(mkt[["date", "Mkt_Total", "RF_d"]], sv[["date", "SV_Total"]], on="date", how="inner")
df = df.sort_values("date").reset_index(drop=True).set_index("date")
print(f"Daily merged: {df.index.min().date()} to {df.index.max().date()}, n={len(df)}")

# monthly compounding
monthly = pd.DataFrame({
    "Mkt": (1 + df["Mkt_Total"]).resample("ME").prod() - 1,
    "SV": (1 + df["SV_Total"]).resample("ME").prod() - 1,
    "RF": (1 + df["RF_d"]).resample("ME").prod() - 1,
}).dropna()
print(f"Monthly: {monthly.index.min().date()} to {monthly.index.max().date()}, n={len(monthly)}")

# annual compounding (calendar year) -- keep only FULL years
annual = pd.DataFrame({
    "Mkt": (1 + df["Mkt_Total"]).resample("YE").prod() - 1,
    "SV": (1 + df["SV_Total"]).resample("YE").prod() - 1,
    "RF": (1 + df["RF_d"]).resample("YE").prod() - 1,
})
annual.index = annual.index.year
days_per_year = df.groupby(df.index.year).size()
full_years = days_per_year[days_per_year >= 200].index  # exclude partial 1926 & 2026
# NOTE: 1968 legitimately has only ~226 trading days (NYSE closed most Wednesdays
# Jun-Dec 1968 during the back-office "paperwork crisis") -- a real, complete
# calendar year, not missing data, so the threshold is set below that count.
annual_full = annual.loc[annual.index.isin(full_years)].copy()
print(f"Full calendar years: {annual_full.index.min()}-{annual_full.index.max()}, n={len(annual_full)}")
print(f"Excluded partial years: {sorted(set(annual.index) - set(full_years))}")

# =============================================================================
# 2. FULL-SAMPLE LONG-TERM STATS
# =============================================================================
def cagr_from_daily(returns, index):
    nav = (1 + returns).cumprod()
    total_days = (index[-1] - index[0]).days
    years = total_days / 365.25
    return nav.iloc[-1] ** (1 / years) - 1, years, nav

mkt_cagr, n_years, mkt_nav = cagr_from_daily(df["Mkt_Total"], df.index)
sv_cagr, _, sv_nav = cagr_from_daily(df["SV_Total"], df.index)

mkt_ann_vol = monthly["Mkt"].std() * np.sqrt(12)
sv_ann_vol = monthly["SV"].std() * np.sqrt(12)

avg_rf_ann = (1 + monthly["RF"]).prod() ** (12 / len(monthly)) - 1
mkt_sharpe = (mkt_cagr - avg_rf_ann) / mkt_ann_vol
sv_sharpe = (sv_cagr - avg_rf_ann) / sv_ann_vol

def max_drawdown(nav):
    peak = nav.cummax()
    dd = nav / peak - 1
    return dd.min()

mkt_mdd = max_drawdown(mkt_nav)
sv_mdd = max_drawdown(sv_nav)

mkt_avg_annual = annual_full["Mkt"].mean()
sv_avg_annual = annual_full["SV"].mean()
mkt_med_annual = annual_full["Mkt"].median()
sv_med_annual = annual_full["SV"].median()
mkt_pos_pct = (annual_full["Mkt"] > 0).mean() * 100
sv_pos_pct = (annual_full["SV"] > 0).mean() * 100
sv_underperf_annual_pct = (annual_full["SV"] < annual_full["Mkt"]).mean() * 100
n_years_underperf = (annual_full["SV"] < annual_full["Mkt"]).sum()

print("\n=== FULL-SAMPLE LONG-TERM STATS ===")
print(f"Span: {df.index.min().date()} to {df.index.max().date()} ({n_years:.1f} years)")
print(f"{'Metric':<32}{'Market':>14}{'Small Value':>14}")
print(f"{'Final value of $1':<32}{mkt_nav.iloc[-1]:>14,.2f}{sv_nav.iloc[-1]:>14,.2f}")
print(f"{'CAGR':<32}{mkt_cagr*100:>13.2f}%{sv_cagr*100:>13.2f}%")
print(f"{'Annual volatility':<32}{mkt_ann_vol*100:>13.2f}%{sv_ann_vol*100:>13.2f}%")
print(f"{'Sharpe ratio':<32}{mkt_sharpe:>14.2f}{sv_sharpe:>14.2f}")
print(f"{'Max drawdown':<32}{mkt_mdd*100:>13.2f}%{sv_mdd*100:>13.2f}%")
print(f"{'Avg annual return':<32}{mkt_avg_annual*100:>13.2f}%{sv_avg_annual*100:>13.2f}%")
print(f"{'Median annual return':<32}{mkt_med_annual*100:>13.2f}%{sv_med_annual*100:>13.2f}%")
print(f"{'% positive years':<32}{mkt_pos_pct:>13.1f}%{sv_pos_pct:>13.1f}%")
print(f"SCV underperformed Market in {n_years_underperf}/{len(annual_full)} years ({sv_underperf_annual_pct:.1f}%)")

OUT["full_sample"] = dict(
    start=str(df.index.min().date()), end=str(df.index.max().date()), years=round(n_years,1),
    mkt_final=round(mkt_nav.iloc[-1],1), sv_final=round(sv_nav.iloc[-1],1),
    mkt_cagr=round(mkt_cagr*100,2), sv_cagr=round(sv_cagr*100,2),
    mkt_vol=round(mkt_ann_vol*100,2), sv_vol=round(sv_ann_vol*100,2),
    mkt_sharpe=round(mkt_sharpe,2), sv_sharpe=round(sv_sharpe,2),
    mkt_mdd=round(mkt_mdd*100,1), sv_mdd=round(sv_mdd*100,1),
    mkt_avg=round(mkt_avg_annual*100,2), sv_avg=round(sv_avg_annual*100,2),
    mkt_med=round(mkt_med_annual*100,2), sv_med=round(sv_med_annual*100,2),
    mkt_pos=round(mkt_pos_pct,1), sv_pos=round(sv_pos_pct,1),
    n_years_annual=len(annual_full), n_underperf_years=int(n_years_underperf), pct_underperf_years=round(sv_underperf_annual_pct,1),
    rf_ann=round(avg_rf_ann*100,2),
)

# =============================================================================
# 3. ROLLING 10-YEAR WINDOWS (monthly basis, annualized)
# =============================================================================
mkt_arr = monthly["Mkt"].to_numpy()
sv_arr = monthly["SV"].to_numpy()
n_months = len(monthly)
window = 120

mkt_log = np.log1p(mkt_arr)
sv_log = np.log1p(sv_arr)
mkt_cum_log = np.concatenate([[0.0], np.cumsum(mkt_log)])
sv_cum_log = np.concatenate([[0.0], np.cumsum(sv_log)])

n_windows = n_months - window + 1
mkt_window_cum = np.exp(mkt_cum_log[window:n_months+1] - mkt_cum_log[0:n_windows]) - 1
sv_window_cum = np.exp(sv_cum_log[window:n_months+1] - sv_cum_log[0:n_windows]) - 1
mkt_window_ann = (1 + mkt_window_cum) ** (1/10) - 1
sv_window_ann = (1 + sv_window_cum) ** (1/10) - 1
diff_ann = sv_window_ann - mkt_window_ann

start_dates = monthly.index[0:n_windows]
end_dates = monthly.index[window-1:n_months]

n_underperf = (diff_ann < 0).sum()
n_outperf = (diff_ann >= 0).sum()
worst_idx = np.argmin(diff_ann)
best_idx = np.argmax(diff_ann)

print("\n=== ROLLING 10-YEAR WINDOWS (annualized) ===")
print(f"Total windows: {n_windows}")
print(f"SCV underperformed: {n_underperf} ({n_underperf/n_windows*100:.1f}%)")
print(f"SCV outperformed:   {n_outperf} ({n_outperf/n_windows*100:.1f}%)")
print(f"Worst relative window: {start_dates[worst_idx].date()} to {end_dates[worst_idx].date()}, "
      f"ann.diff={diff_ann[worst_idx]*100:.2f}pp (SCV={sv_window_ann[worst_idx]*100:.2f}%, Mkt={mkt_window_ann[worst_idx]*100:.2f}%)")
print(f"Best relative window: {start_dates[best_idx].date()} to {end_dates[best_idx].date()}, "
      f"ann.diff={diff_ann[best_idx]*100:.2f}pp (SCV={sv_window_ann[best_idx]*100:.2f}%, Mkt={mkt_window_ann[best_idx]*100:.2f}%)")
print(f"Median ann. diff: {np.median(diff_ann)*100:.2f}pp")
for q in [5,25,75,95]:
    print(f"  p{q}: {np.percentile(diff_ann,q)*100:.2f}pp")

OUT["rolling10"] = dict(
    n_windows=int(n_windows), n_underperf=int(n_underperf), pct_underperf=round(n_underperf/n_windows*100,1),
    n_outperf=int(n_outperf), pct_outperf=round(n_outperf/n_windows*100,1),
    worst_start=str(start_dates[worst_idx].date()), worst_end=str(end_dates[worst_idx].date()),
    worst_diff=round(diff_ann[worst_idx]*100,2), worst_scv=round(sv_window_ann[worst_idx]*100,2), worst_mkt=round(mkt_window_ann[worst_idx]*100,2),
    best_start=str(start_dates[best_idx].date()), best_end=str(end_dates[best_idx].date()),
    best_diff=round(diff_ann[best_idx]*100,2), best_scv=round(sv_window_ann[best_idx]*100,2), best_mkt=round(mkt_window_ann[best_idx]*100,2),
    median_diff=round(np.median(diff_ann)*100,2),
    p5=round(np.percentile(diff_ann,5)*100,2), p25=round(np.percentile(diff_ann,25)*100,2),
    p75=round(np.percentile(diff_ann,75)*100,2), p95=round(np.percentile(diff_ann,95)*100,2),
)

np.save(rf"{SCRATCH}\rolling_end_dates.npy", np.array([d.value for d in end_dates]))
np.save(rf"{SCRATCH}\rolling_mkt_ann.npy", mkt_window_ann)
np.save(rf"{SCRATCH}\rolling_sv_ann.npy", sv_window_ann)
np.save(rf"{SCRATCH}\rolling_diff_ann.npy", diff_ann)

# =============================================================================
# 4. ROBUSTNESS TESTS
# =============================================================================
print("\n" + "="*70)
print("ROBUSTNESS TESTS")
print("="*70)

# ---- A. Exclude the strongest SCV 10-year window ----
strong_start_month_idx = worst_idx * 0 + best_idx  # index into monthly series windows
excl_start = best_idx
excl_end = best_idx + window  # exclusive, months [excl_start, excl_end)

remaining_mkt_log = np.concatenate([mkt_log[:excl_start], mkt_log[excl_end:]])
remaining_sv_log = np.concatenate([sv_log[:excl_start], sv_log[excl_end:]])
n_remaining_months = len(remaining_mkt_log)
mkt_cagr_ex = np.exp(remaining_mkt_log.sum() * 12 / n_remaining_months) - 1
sv_cagr_ex = np.exp(remaining_sv_log.sum() * 12 / n_remaining_months) - 1

print(f"\n--- A. Exclude strongest SCV decade ({start_dates[best_idx].date()} to {end_dates[best_idx].date()}) ---")
print(f"Full-sample CAGR:        Market {mkt_cagr*100:.2f}%  SCV {sv_cagr*100:.2f}%  premium {(sv_cagr-mkt_cagr)*100:+.2f}pp")
print(f"Ex-best-decade CAGR:     Market {mkt_cagr_ex*100:.2f}%  SCV {sv_cagr_ex*100:.2f}%  premium {(sv_cagr_ex-mkt_cagr_ex)*100:+.2f}pp")

# also: exclude top-5 individual calendar years by SCV-Mkt log-return contribution
annual_diff_log = np.log1p(annual_full["SV"]) - np.log1p(annual_full["Mkt"])
top5_years = annual_diff_log.sort_values(ascending=False).head(5)
print(f"\nTop 5 single years by SCV-over-Market log-return contribution:")
for yr, val in top5_years.items():
    print(f"  {yr}: SCV {annual_full.loc[yr,'SV']*100:+.1f}%  Mkt {annual_full.loc[yr,'Mkt']*100:+.1f}%  contribution {val*100:+.1f}pp(log)")

mask_ex5 = ~annual_full.index.isin(top5_years.index)
mkt_cagr_ex5 = np.exp(np.log1p(annual_full.loc[mask_ex5,"Mkt"]).sum() / mask_ex5.sum()) - 1
sv_cagr_ex5 = np.exp(np.log1p(annual_full.loc[mask_ex5,"SV"]).sum() / mask_ex5.sum()) - 1
print(f"Ex-top-5-years CAGR:     Market {mkt_cagr_ex5*100:.2f}%  SCV {sv_cagr_ex5*100:.2f}%  premium {(sv_cagr_ex5-mkt_cagr_ex5)*100:+.2f}pp")
print(f"(computed over remaining {mask_ex5.sum()} of {len(annual_full)} years)")

OUT["robust_A"] = dict(
    best_start=str(start_dates[best_idx].date()), best_end=str(end_dates[best_idx].date()),
    full_premium=round((sv_cagr-mkt_cagr)*100,2),
    ex_decade_mkt=round(mkt_cagr_ex*100,2), ex_decade_sv=round(sv_cagr_ex*100,2), ex_decade_premium=round((sv_cagr_ex-mkt_cagr_ex)*100,2),
    top5_years=[int(y) for y in top5_years.index],
    ex5_mkt=round(mkt_cagr_ex5*100,2), ex5_sv=round(sv_cagr_ex5*100,2), ex5_premium=round((sv_cagr_ex5-mkt_cagr_ex5)*100,2),
)

# ---- B. Pre/post era analysis ----
eras = [
    ("1927-1945", 1927, 1945),
    ("1946-1964", 1946, 1964),
    ("1965-1983", 1965, 1983),
    ("1984-2002", 1984, 2002),
    ("2003-2025", 2003, 2025),
]
print("\n--- B. Era-by-era analysis ---")
era_stats = []
for name, y0, y1 in eras:
    sub = annual_full.loc[(annual_full.index >= y0) & (annual_full.index <= y1)]
    n = len(sub)
    mkt_c = (1+sub["Mkt"]).prod() ** (1/n) - 1
    sv_c = (1+sub["SV"]).prod() ** (1/n) - 1
    win_pct = (sub["SV"] >= sub["Mkt"]).mean() * 100
    print(f"{name} (n={n}): Market {mkt_c*100:6.2f}%  SCV {sv_c*100:6.2f}%  premium {(sv_c-mkt_c)*100:+6.2f}pp  SCV won {win_pct:.0f}% of years")
    era_stats.append(dict(name=name, n=n, mkt=round(mkt_c*100,2), sv=round(sv_c*100,2), premium=round((sv_c-mkt_c)*100,2), win_pct=round(win_pct,0)))
OUT["robust_B"] = era_stats

# ---- C. Random subsampling (year-level bootstrap without replacement, 50% of years) ----
rng = np.random.default_rng(7)
n_sub = 10000
frac = 0.5
n_yr = len(annual_full)
n_pick = int(n_yr * frac)
mkt_log_yr = np.log1p(annual_full["Mkt"].to_numpy())
sv_log_yr = np.log1p(annual_full["SV"].to_numpy())

sub_premium = np.empty(n_sub)
for i in range(n_sub):
    pick = rng.choice(n_yr, size=n_pick, replace=False)
    mkt_c = np.exp(mkt_log_yr[pick].mean()) - 1
    sv_c = np.exp(sv_log_yr[pick].mean()) - 1
    sub_premium[i] = sv_c - mkt_c

pct_scv_ahead = (sub_premium > 0).mean() * 100
print(f"\n--- C. Random subsampling (10,000 draws of {n_pick}/{n_yr} years, without replacement) ---")
print(f"SCV premium positive in {pct_scv_ahead:.1f}% of subsamples")
print(f"Median premium: {np.median(sub_premium)*100:+.2f}pp")
print(f"p5: {np.percentile(sub_premium,5)*100:+.2f}pp   p95: {np.percentile(sub_premium,95)*100:+.2f}pp")

OUT["robust_C"] = dict(
    n_sub=n_sub, n_pick=n_pick, n_total=n_yr,
    pct_scv_ahead=round(pct_scv_ahead,1),
    median=round(np.median(sub_premium)*100,2),
    p5=round(np.percentile(sub_premium,5)*100,2), p95=round(np.percentile(sub_premium,95)*100,2),
)

# ---- D. Leave-one-era-out ----
print("\n--- D. Leave-one-era-out (recompute full-sample premium excluding each era) ---")
lopo = []
for name, y0, y1 in eras:
    mask = ~((annual_full.index >= y0) & (annual_full.index <= y1))
    sub = annual_full.loc[mask]
    n = len(sub)
    mkt_c = (1+sub["Mkt"]).prod() ** (1/n) - 1
    sv_c = (1+sub["SV"]).prod() ** (1/n) - 1
    print(f"Excl. {name}: Market {mkt_c*100:6.2f}%  SCV {sv_c*100:6.2f}%  premium {(sv_c-mkt_c)*100:+6.2f}pp   (n={n})")
    lopo.append(dict(excluded=name, n=n, mkt=round(mkt_c*100,2), sv=round(sv_c*100,2), premium=round((sv_c-mkt_c)*100,2)))
full_premium_annual = (np.exp(mkt_log_yr.sum()/n_yr) - 1, np.exp(sv_log_yr.sum()/n_yr) - 1)
print(f"(Full sample, for reference: Market {full_premium_annual[0]*100:.2f}%  SCV {full_premium_annual[1]*100:.2f}%  "
      f"premium {(full_premium_annual[1]-full_premium_annual[0])*100:+.2f}pp)")
OUT["robust_D"] = dict(lopo=lopo, full_mkt=round(full_premium_annual[0]*100,2), full_sv=round(full_premium_annual[1]*100,2),
                        full_premium=round((full_premium_annual[1]-full_premium_annual[0])*100,2))

# =============================================================================
# 5. MONTE CARLO (moving-block bootstrap, monthly, 12-month blocks, 10yr paths)
# =============================================================================
print("\n" + "="*70)
print("MONTE CARLO SIMULATION")
print("="*70)
rng2 = np.random.default_rng(42)
N_SIMS = 100_000
BLOCK = 12
N_BLOCKS_NEEDED = int(np.ceil(window / BLOCK))
n_possible_starts = n_months - BLOCK + 1

starts = rng2.integers(0, n_possible_starts, size=(N_SIMS, N_BLOCKS_NEEDED))
offsets = np.arange(BLOCK)
idx = (starts[:, :, None] + offsets[None, None, :]).reshape(N_SIMS, -1)[:, :window]

sim_mkt = mkt_arr[idx]
sim_sv = sv_arr[idx]
mc_mkt_cum = np.prod(1 + sim_mkt, axis=1) - 1
mc_sv_cum = np.prod(1 + sim_sv, axis=1) - 1
mc_mkt_ann = (1 + mc_mkt_cum) ** (1/10) - 1
mc_sv_ann = (1 + mc_sv_cum) ** (1/10) - 1
mc_diff_ann = mc_sv_ann - mc_mkt_ann

pct_underperf_mc = (mc_diff_ann < 0).mean() * 100
pct_neg_abs_mc = (mc_sv_cum < 0).mean() * 100

print(f"N simulations: {N_SIMS:,}  (12-month moving-block bootstrap, 10-year paths)")
print(f"P(SCV underperforms Market, annualized): {pct_underperf_mc:.1f}%")
for thr in [0.05, 0.10, 0.20, 0.30]:
    p = (mc_diff_ann <= -thr).mean() * 100
    print(f"P(SCV underperforms by >= {int(thr*100)}pp annualized): {p:.1f}%")
print(f"P(SCV 10yr cumulative return negative): {pct_neg_abs_mc:.1f}%")
print(f"Median ann. diff: {np.median(mc_diff_ann)*100:+.2f}pp")
for q in [5,25,75,95]:
    print(f"  p{q}: {np.percentile(mc_diff_ann,q)*100:+.2f}pp")
print(f"Median SCV ann. return: {np.median(mc_sv_ann)*100:.2f}%   Median Mkt ann. return: {np.median(mc_mkt_ann)*100:.2f}%")

OUT["mc"] = dict(
    n_sims=N_SIMS, pct_underperf=round(pct_underperf_mc,1),
    p_gt5=round((mc_diff_ann<=-0.05).mean()*100,1), p_gt10=round((mc_diff_ann<=-0.10).mean()*100,1),
    p_gt20=round((mc_diff_ann<=-0.20).mean()*100,1), p_gt30=round((mc_diff_ann<=-0.30).mean()*100,1),
    pct_neg_abs=round(pct_neg_abs_mc,1),
    median_diff=round(np.median(mc_diff_ann)*100,2),
    p5=round(np.percentile(mc_diff_ann,5)*100,2), p25=round(np.percentile(mc_diff_ann,25)*100,2),
    p75=round(np.percentile(mc_diff_ann,75)*100,2), p95=round(np.percentile(mc_diff_ann,95)*100,2),
    median_sv_ann=round(np.median(mc_sv_ann)*100,2), median_mkt_ann=round(np.median(mc_mkt_ann)*100,2),
)

np.save(rf"{SCRATCH}\mc_diff_ann.npy", mc_diff_ann)
np.save(rf"{SCRATCH}\mc_mkt_ann.npy", mc_mkt_ann)
np.save(rf"{SCRATCH}\mc_sv_ann.npy", mc_sv_ann)

# =============================================================================
# save annual table + json summary
# =============================================================================
annual_full.to_csv(rf"{SCRATCH}\annual_full.csv")
with open(rf"{SCRATCH}\summary_stats.json", "w") as f:
    json.dump(OUT, f, indent=2, default=str)

print("\nDone. JSON summary + npy arrays + annual csv saved to scratch.")
