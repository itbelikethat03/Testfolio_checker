"""
Stage 1: SCV vs Bonds as diversifiers for a 2x-leveraged Market portfolio, 25yr horizon.

BOND DATA SOURCE (explicitly disclosed, since backtest.py / the Ken French dataset
contain no bond series at all): Robert Shiller's long-run stock market dataset
(http://www.econ.yale.edu/~shiller/data.htm, ie_data.xls), which includes a
monthly 10-year Treasury constant-maturity total-return factor (nominal), built
from GS10 yields using the standard yield+duration total-return approximation.
This is the only long-history (1871-present), publicly documented, non-fabricated
bond TOTAL RETURN series available without a live market-data subscription.
It runs through 2024-09 -- ~1.5 years short of the Apr-2026 end of the equity
data -- so every multi-asset comparison in this analysis is truncated to the
overlapping window (Jul 1926 - Sep 2024, monthly).

FREQUENCY CHANGE (clearly flagged, since backtest.py itself works in daily data):
Shiller's bond series is monthly-only, so this entire 5-strategy comparison runs
at MONTHLY frequency rather than backtest.py's native daily frequency. The
leverage-cost formula and daily-compounding logic are otherwise reused unchanged,
just applied at a monthly step: monthly_cost = (lev-1)*(RF_m+spread_m)+expense_m,
lev_ret_m = lev*Mkt_Total_m - monthly_cost, NAV = cumprod(1+lev_ret_m). This still
produces volatility drag via compounding, just computed monthly instead of daily
-- a documented, modest understatement of true daily-rebalanced drag (see report).
"""
import numpy as np
import pandas as pd
import json

ROOT = r"c:\Python Datoteke"
SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"
OUT = {}

# =============================================================================
# 1. LOAD EQUITY DATA (Market, SCV) -- daily, then compound to monthly
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

daily = pd.merge(mkt[["date", "Mkt_Total", "RF_d"]], sv[["date", "SV_Total"]], on="date", how="inner")
daily = daily.sort_values("date").reset_index(drop=True).set_index("date")

monthly = pd.DataFrame({
    "Mkt": (1 + daily["Mkt_Total"]).resample("ME").prod() - 1,
    "RF": (1 + daily["RF_d"]).resample("ME").prod() - 1,
    "SV": (1 + daily["SV_Total"]).resample("ME").prod() - 1,
}).dropna()
monthly.index = monthly.index.to_period("M")

# ---- SCV cost drag, calibrated to Dimensional's live DFSVX fund ----
# The raw Fama-French SMALL HiBM factor is a frictionless, annually-rebalanced
# academic construction with no transaction costs. Rather than assume a cost,
# this is now empirically calibrated: DFSVX (Dimensional US Small Cap Value I,
# inception Mar 2 1993) has an actual since-inception CAGR of 11.168%
# (totalrealreturns.com, dividends reinvested, 1993-02-26 to 2026-01-13),
# while the raw FF SMALL HiBM factor over the identical window compounds to
# 12.260%/yr -- a 1.092pp/yr gap. DFSVX's own stated net expense ratio is only
# 0.31%, so roughly 0.78pp/yr of the gap is real-world implementation drag
# (trading costs on a less liquid universe, weighting/screening methodology
# differences vs. the raw academic top-30%-BtM sort) beyond the stated fee.
SV_ANNUAL_COST = 0.01092
sv_cost_m = SV_ANNUAL_COST / 12.0
monthly["SV_gross"] = monthly["SV"]
monthly["SV"] = monthly["SV"] - sv_cost_m
print(f"Equity monthly: {monthly.index.min()} to {monthly.index.max()}, n={len(monthly)}")
print(f"SCV turnover-cost drag applied: {SV_ANNUAL_COST*100:.2f}%/yr ({sv_cost_m*100:.4f}%/mo)")

# =============================================================================
# 2. LOAD BOND DATA (Shiller)
# =============================================================================
shiller = pd.read_excel(rf"{SCRATCH}\ie_data.xls", sheet_name="Data", header=None)
bond = shiller.iloc[8:, [0, 6, 17]].copy()
bond.columns = ["date_frac", "GS10", "bond_factor"]
bond = bond.dropna(subset=["date_frac"])
bond["date_frac"] = pd.to_numeric(bond["date_frac"], errors="coerce")
bond = bond.dropna(subset=["date_frac"])
year = np.floor(bond["date_frac"]).astype(int)
month = np.round((bond["date_frac"] - year) * 100).astype(int)
month = month.replace(0, 1)  # guard
bond["period"] = pd.PeriodIndex(year=year, month=month, freq="M")
bond["Bond"] = pd.to_numeric(bond["bond_factor"], errors="coerce") - 1.0
bond = bond.dropna(subset=["Bond"]).set_index("period")[["Bond", "GS10"]]
print(f"Bond monthly (Shiller): {bond.index.min()} to {bond.index.max()}, n={len(bond)}")

# =============================================================================
# 3. MERGE on overlapping monthly period
# =============================================================================
df = monthly.join(bond[["Bond"]], how="inner")
print(f"Merged 4-asset monthly sample: {df.index.min()} to {df.index.max()}, n={len(df)}")
df.to_csv(rf"{SCRATCH}\div_monthly.csv")

# =============================================================================
# 4. LEVERAGE COST (monthly-adapted, backtest.py formula/defaults)
# =============================================================================
LEVERAGE = 2.0
SPREAD_ANNUAL = 0.004
EXPENSE_ANNUAL = 0.0095
sd_m = SPREAD_ANNUAL / 12.0
ed_m = EXPENSE_ANNUAL / 12.0
monthly_cost = (LEVERAGE - 1.0) * (df["RF"] + sd_m) + ed_m
df["Lev"] = LEVERAGE * df["Mkt"] - monthly_cost

# =============================================================================
# 5. 50/50 PORTFOLIOS -- monthly rebalanced AND annual (buy-and-hold-within-year) rebalanced
# =============================================================================
def monthly_rebal(ret_a, ret_b, w=0.5):
    return w * ret_a + w * ret_b

def annual_rebal_nav(ret_a, ret_b, index, w=0.5):
    """Drift weights within each calendar year, reset to w at each Jan (or first obs)."""
    nav = np.empty(len(ret_a))
    years = index.year if hasattr(index, "year") else pd.PeriodIndex(index).year
    val_a, val_b = w, w
    for i in range(len(ret_a)):
        if i == 0 or years[i] != years[i-1]:
            val_a, val_b = w, w
        val_a *= (1 + ret_a[i]); val_b *= (1 + ret_b[i])
        nav[i] = val_a + val_b
    port_ret = nav / np.concatenate([[1.0], nav[:-1]]) - 1.0
    # fix: at rebalance points nav[:-1] should be total port value before that step, recompute properly
    return None  # placeholder, real implementation below

def annual_rebal_returns(ret_a, ret_b, years, w=0.5):
    n = len(ret_a)
    port_ret = np.empty(n)
    val_a = val_b = w
    prev_total = 1.0
    for i in range(n):
        if i == 0 or years[i] != years[i-1]:
            total_before = val_a + val_b if i > 0 else 1.0
            val_a, val_b = w * total_before, w * total_before
        total_start = val_a + val_b
        val_a *= (1 + ret_a[i]); val_b *= (1 + ret_b[i])
        total_end = val_a + val_b
        port_ret[i] = total_end / total_start - 1.0
    return port_ret

years_arr = df.index.year.to_numpy()
lev_arr = df["Lev"].to_numpy(); sv_arr = df["SV"].to_numpy(); bond_arr = df["Bond"].to_numpy(); mkt_arr = df["Mkt"].to_numpy()

df["Port_SCV_m"] = monthly_rebal(lev_arr, sv_arr)
df["Port_Bond_m"] = monthly_rebal(lev_arr, bond_arr)
df["Port_SCV_a"] = annual_rebal_returns(lev_arr, sv_arr, years_arr)
df["Port_Bond_a"] = annual_rebal_returns(lev_arr, bond_arr, years_arr)

df.to_csv(rf"{SCRATCH}\div_monthly.csv")

# =============================================================================
# 6. CORRELATIONS
# =============================================================================
corr = df[["Mkt", "Lev", "SV", "Bond"]].corr()
print("\n=== CORRELATION MATRIX (full monthly sample) ===")
print(corr.round(3))
OUT["correlations"] = corr.round(4).to_dict()

# conditional correlations: equity drawdown months (bottom quartile Mkt) vs top quartile
q25 = df["Mkt"].quantile(0.25)
q75 = df["Mkt"].quantile(0.75)
bad_months = df[df["Mkt"] <= q25]
good_months = df[df["Mkt"] >= q75]
corr_bad = bad_months[["Mkt","SV","Bond"]].corr()
corr_good = good_months[["Mkt","SV","Bond"]].corr()
print(f"\nCorr(Mkt,SV) in worst-quartile Mkt months: {corr_bad.loc['Mkt','SV']:.3f}   Corr(Mkt,Bond): {corr_bad.loc['Mkt','Bond']:.3f}")
print(f"Corr(Mkt,SV) in best-quartile Mkt months:  {corr_good.loc['Mkt','SV']:.3f}   Corr(Mkt,Bond): {corr_good.loc['Mkt','Bond']:.3f}")
OUT["conditional_corr"] = dict(
    bad_mkt_sv=round(float(corr_bad.loc['Mkt','SV']),3), bad_mkt_bond=round(float(corr_bad.loc['Mkt','Bond']),3),
    good_mkt_sv=round(float(corr_good.loc['Mkt','SV']),3), good_mkt_bond=round(float(corr_good.loc['Mkt','Bond']),3),
    n_bad=int(len(bad_months)), n_good=int(len(good_months)),
)

# =============================================================================
# 7. FULL-SAMPLE STATS for all 5 base strategies + monthly-rebal portfolios
# =============================================================================
avg_rf_ann = (1 + df["RF"]).prod() ** (12/len(df)) - 1

def stats_from_monthly(ret, name):
    nav = (1 + ret).cumprod()
    n_m = len(ret)
    cagr = nav.iloc[-1] ** (12/n_m) - 1
    ann_vol = ret.std() * np.sqrt(12)
    peak = nav.cummax()
    dd = nav/peak - 1
    mdd = dd.min()
    sharpe = (cagr - avg_rf_ann) / ann_vol
    downside = ret[ret < 0]
    downside_dev = downside.std() * np.sqrt(12) if len(downside) > 1 else np.nan
    return dict(name=name, cagr=float(cagr), ann_vol=float(ann_vol), mdd=float(mdd),
                sharpe=float(sharpe), final=float(nav.iloc[-1]), downside_dev=float(downside_dev))

strategies_m = {
    "mkt": df["Mkt"], "lev": df["Lev"], "sv": df["SV"], "bond": df["Bond"],
    "port_scv_m": df["Port_SCV_m"], "port_bond_m": df["Port_Bond_m"],
    "port_scv_a": df["Port_SCV_a"], "port_bond_a": df["Port_Bond_a"],
}
print("\n=== FULL-SAMPLE STATS (monthly-compounded) ===")
full_stats = {}
for k, ret in strategies_m.items():
    s = stats_from_monthly(ret, k)
    full_stats[k] = s
    print(f"{k:<14} CAGR={s['cagr']*100:6.2f}%  vol={s['ann_vol']*100:6.2f}%  Sharpe={s['sharpe']:5.2f}  "
          f"MDD={s['mdd']*100:7.2f}%  final=${s['final']:,.0f}  downDev={s['downside_dev']*100:5.2f}%")
OUT["full_sample"] = full_stats
OUT["full_sample"]["rf_ann"] = float(avg_rf_ann)
OUT["sample_range"] = dict(start=str(df.index.min()), end=str(df.index.max()), n_months=len(df))

with open(rf"{SCRATCH}\div_summary.json", "w") as f:
    json.dump(OUT, f, indent=2, default=str)

# save arrays for later stages
np.save(rf"{SCRATCH}\div_mkt.npy", mkt_arr); np.save(rf"{SCRATCH}\div_lev.npy", lev_arr)
np.save(rf"{SCRATCH}\div_sv.npy", sv_arr); np.save(rf"{SCRATCH}\div_bond.npy", bond_arr)
np.save(rf"{SCRATCH}\div_rf.npy", df["RF"].to_numpy())
np.save(rf"{SCRATCH}\div_port_scv_m.npy", df["Port_SCV_m"].to_numpy())
np.save(rf"{SCRATCH}\div_port_bond_m.npy", df["Port_Bond_m"].to_numpy())
np.save(rf"{SCRATCH}\div_port_scv_a.npy", df["Port_SCV_a"].to_numpy())
np.save(rf"{SCRATCH}\div_port_bond_a.npy", df["Port_Bond_a"].to_numpy())
np.save(rf"{SCRATCH}\div_years.npy", years_arr)
periods_str = np.array([str(p) for p in df.index])
np.save(rf"{SCRATCH}\div_periods.npy", periods_str)

print("\nStage 1 complete.")
