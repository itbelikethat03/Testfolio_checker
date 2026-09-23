import numpy as np
import pandas as pd
import json

ROOT = r"c:\Python Datoteke"
SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"
TRADING_DAYS = 252

with open(rf"{SCRATCH}\l25_summary_partial.json") as f:
    OUT = json.load(f)

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

df = pd.merge(mkt[["date", "Mkt_Total", "RF_d"]], sv[["date", "SV_Total"]], on="date", how="inner")
df = df.sort_values("date").reset_index(drop=True)
mkt_total = df["Mkt_Total"].to_numpy()
rf = df["RF_d"].to_numpy()
sv_total = df["SV_Total"].to_numpy()
dates = df["date"].to_numpy()
n = len(df)

def lev_returns(mkt_total, rf, leverage=2.0, spread_annual=0.004, expense_annual=0.0095):
    sd = spread_annual / TRADING_DAYS
    ed = expense_annual / TRADING_DAYS
    daily_cost = (leverage - 1.0) * (rf + sd) + ed
    return leverage * mkt_total - daily_cost

def cagr_of(ret, mask=None):
    if mask is not None:
        ret = ret[mask]
    factors = np.maximum(1.0 + ret, 0.0)
    n_ = len(factors)
    nav_final = np.prod(factors)
    return nav_final ** (TRADING_DAYS / n_) - 1.0

lev_total = lev_returns(mkt_total, rf)

WINDOW_DAYS = 25 * TRADING_DAYS
starts = np.load(rf"{SCRATCH}\l25_starts.npy")
sv_ann = np.load(rf"{SCRATCH}\l25_sv_ann.npy")
mkt_ann = np.load(rf"{SCRATCH}\l25_mkt_ann.npy")
best_idx_sv = int(np.argmax(sv_ann))
best_idx_mkt = int(np.argmax(mkt_ann))
sv_excl_range = (starts[best_idx_sv], starts[best_idx_sv] + WINDOW_DAYS)
mkt_excl_range = (starts[best_idx_mkt], starts[best_idx_mkt] + WINDOW_DAYS)

print("=== A. Exclude strongest SCV 25yr period ===")
mask = np.ones(n, dtype=bool)
mask[sv_excl_range[0]:sv_excl_range[1]] = False
mkt_c = cagr_of(mkt_total, mask); lev_c = cagr_of(lev_total, mask); sv_c = cagr_of(sv_total, mask)
print(f"Excl. {pd.Timestamp(dates[sv_excl_range[0]]).date()}-{pd.Timestamp(dates[sv_excl_range[1]-1]).date()}: "
      f"Market {mkt_c*100:.2f}%  2xMarket {lev_c*100:.2f}%  SCV {sv_c*100:.2f}%")
OUT["robust_A"] = dict(excl_start=str(pd.Timestamp(dates[sv_excl_range[0]]).date()), excl_end=str(pd.Timestamp(dates[sv_excl_range[1]-1]).date()),
                        mkt=round(mkt_c*100,2), lev=round(lev_c*100,2), sv=round(sv_c*100,2))

print("\n=== B. Exclude strongest Market 25yr period ===")
mask2 = np.ones(n, dtype=bool)
mask2[mkt_excl_range[0]:mkt_excl_range[1]] = False
mkt_c2 = cagr_of(mkt_total, mask2); lev_c2 = cagr_of(lev_total, mask2); sv_c2 = cagr_of(sv_total, mask2)
print(f"Excl. {pd.Timestamp(dates[mkt_excl_range[0]]).date()}-{pd.Timestamp(dates[mkt_excl_range[1]-1]).date()}: "
      f"Market {mkt_c2*100:.2f}%  2xMarket {lev_c2*100:.2f}%  SCV {sv_c2*100:.2f}%")
OUT["robust_B"] = dict(excl_start=str(pd.Timestamp(dates[mkt_excl_range[0]]).date()), excl_end=str(pd.Timestamp(dates[mkt_excl_range[1]-1]).date()),
                        mkt=round(mkt_c2*100,2), lev=round(lev_c2*100,2), sv=round(sv_c2*100,2))

print("\n=== C. Era split (four 25yr eras) ===")
era_bounds = [0, 25, 50, 75, 100]  # in years from start
start_date = pd.Timestamp(dates[0])
eras = []
for i in range(4):
    y0 = start_date.year + era_bounds[i]
    y1 = start_date.year + era_bounds[i+1]
    era_mask = (pd.DatetimeIndex(dates).year >= y0) & (pd.DatetimeIndex(dates).year < y1)
    if era_mask.sum() < 100:
        continue
    mkt_e = cagr_of(mkt_total, era_mask); lev_e = cagr_of(lev_total, era_mask); sv_e = cagr_of(sv_total, era_mask)
    n_days_era = era_mask.sum()
    print(f"{y0}-{y1} (n={n_days_era}d): Market {mkt_e*100:6.2f}%  2xMarket {lev_e*100:6.2f}%  SCV {sv_e*100:6.2f}%   "
          f"(2x>Mkt: {lev_e>mkt_e}, SCV>Mkt: {sv_e>mkt_e}, SCV>2x: {sv_e>lev_e})")
    eras.append(dict(range=f"{y0}-{y1}", n_days=int(n_days_era), mkt=round(mkt_e*100,2), lev=round(lev_e*100,2), sv=round(sv_e*100,2)))
OUT["robust_C"] = eras

print("\n=== D. Leverage cost sensitivity ===")
scenarios = [
    ("Zero cost", 0.0, 0.0),
    ("Base case (backtest.py default)", 0.004, 0.0095),
    ("High cost", 0.010, 0.015),
]
cost_rows = []
for name, sp, ex in scenarios:
    lev_s = lev_returns(mkt_total, rf, leverage=2.0, spread_annual=sp, expense_annual=ex)
    lev_cagr_full = cagr_of(lev_s)
    lev_cum = np.cumprod(np.maximum(1+lev_s,0.0))
    lev_win = lev_cum[starts + WINDOW_DAYS] / lev_cum[starts]
    lev_win_ann = lev_win ** (1/25) - 1
    pct_lev_beats_mkt = (lev_win_ann > mkt_ann).mean() * 100
    pct_lev_beats_sv = (lev_win_ann > sv_ann).mean() * 100
    print(f"{name} (spread={sp*100:.2f}%, expense={ex*100:.2f}%): full-sample 2x CAGR={lev_cagr_full*100:.2f}%  "
          f"2x beats Mkt {pct_lev_beats_mkt:.1f}% of 25yr windows, 2x beats SCV {pct_lev_beats_sv:.1f}% of windows")
    cost_rows.append(dict(name=name, spread=sp*100, expense=ex*100, lev_cagr=round(lev_cagr_full*100,2),
                           pct_beats_mkt=round(pct_lev_beats_mkt,1), pct_beats_sv=round(pct_lev_beats_sv,1)))
OUT["robust_D"] = cost_rows

with open(rf"{SCRATCH}\l25_summary_partial.json", "w") as f:
    json.dump(OUT, f, indent=2, default=str)
print("\nStage 3 (robustness) complete.")
