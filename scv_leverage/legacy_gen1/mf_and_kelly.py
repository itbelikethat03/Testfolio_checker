import numpy as np
import pandas as pd
import json

ROOT = r"c:\Python Datoteke"
SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"
OUT = {}

# =============================================================================
# LOAD everything (Market, SCV w/ DFSVX-calibrated cost, Bond, and now Managed Futures)
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
mkt["Mkt_RF_d"] = mkt["Mkt-RF"] / 100.0

sv = pd.read_csv(rf"{SCRATCH}\ff6\6_Portfolios_2x3_Daily.csv", skiprows=18, nrows=26293 - 19)
sv.columns = ["date", "SMALL_LoBM", "ME1_BM2", "SMALL_HiBM", "BIG_LoBM", "ME2_BM2", "BIG_HiBM"]
sv["date"] = pd.to_datetime(sv["date"], format="%Y%m%d", errors="coerce")
sv = sv.dropna(subset=["date"])
sv["SV_Total"] = pd.to_numeric(sv["SMALL_HiBM"], errors="coerce") / 100.0
sv = sv.dropna(subset=["SV_Total"]).reset_index(drop=True).set_index("date")

daily = pd.merge(mkt[["date", "Mkt_Total", "RF_d", "Mkt_RF_d"]], sv[["SV_Total"]], left_on="date", right_index=True, how="inner")
daily = daily.sort_values("date").reset_index(drop=True).set_index("date")

monthly = pd.DataFrame({
    "Mkt": (1 + daily["Mkt_Total"]).resample("ME").prod() - 1,
    "Mkt_RF": (1 + daily["Mkt_RF_d"]).resample("ME").prod() - 1,  # approx; used only for reference
    "RF": (1 + daily["RF_d"]).resample("ME").prod() - 1,
    "SV_gross": (1 + daily["SV_Total"]).resample("ME").prod() - 1,
}).dropna()
monthly.index = monthly.index.to_period("M")

SV_ANNUAL_COST = 0.01092  # DFSVX-calibrated, from prior turn
monthly["SV"] = monthly["SV_gross"] - SV_ANNUAL_COST / 12.0

LEVERAGE = 2.0
SPREAD_ANNUAL = 0.004
EXPENSE_ANNUAL = 0.0095
sd_m = SPREAD_ANNUAL / 12.0
ed_m = EXPENSE_ANNUAL / 12.0
monthly["Lev"] = LEVERAGE * monthly["Mkt"] - ((LEVERAGE - 1.0) * (monthly["RF"] + sd_m) + ed_m)

# ---- Bonds (Shiller) ----
shiller = pd.read_excel(rf"{SCRATCH}\ie_data.xls", sheet_name="Data", header=None)
bond = shiller.iloc[8:, [0, 6, 17]].copy()
bond.columns = ["date_frac", "GS10", "bond_factor"]
bond = bond.dropna(subset=["date_frac"])
bond["date_frac"] = pd.to_numeric(bond["date_frac"], errors="coerce")
bond = bond.dropna(subset=["date_frac"])
year = np.floor(bond["date_frac"]).astype(int)
month = np.round((bond["date_frac"] - year) * 100).astype(int).replace(0, 1)
bond["period"] = pd.PeriodIndex.from_fields(year=year, month=month, freq="M")
bond["Bond"] = pd.to_numeric(bond["bond_factor"], errors="coerce") - 1.0
bond = bond.dropna(subset=["Bond"]).set_index("period")[["Bond"]]

# ---- Managed Futures (AQR TSMOM, diversified across EQ/FI/FX/CM, + RF as collateral yield) ----
tsmom = pd.read_excel(rf"{SCRATCH}\tsmom.xlsx", sheet_name="TSMOM Factors", header=None, skiprows=17)
tsmom.columns = ["date", "TSMOM", "TSMOM_CM", "TSMOM_EQ", "TSMOM_FI", "TSMOM_FX"]
tsmom = tsmom.dropna(subset=["date"])
tsmom["period"] = pd.PeriodIndex(pd.to_datetime(tsmom["date"]), freq="M")
tsmom = tsmom.set_index("period")

df = monthly.join(bond, how="inner").join(tsmom[["TSMOM"]], how="inner")
# Managed futures total return = trend excess return + collateral (T-bill) yield,
# minus a cost drag. History of this calibration:
#   1) AQMIX (single fund, inception 2010) -> 1.87pp/yr gap -- too low.
#   2) SG Trend Index (broad CTA benchmark, live since 2000) -> 5.02pp/yr gap,
#      still left standalone MF compounding at ~10.5%/yr, 1985-2024.
#   3) User judgment call (this version): a strategy with near-zero equity
#      correlation persistently compounding at 10%+/yr would be an unlikely-
#      to-persist market anomaly -- essentially risk-free-plus-alpha at scale.
#      Capped so standalone Managed Futures compounds to a deliberately
#      conservative 6.0%/yr over this sample (Jan 1985-Aug 2024), which
#      requires an implied cost of 8.839pp/yr (solved by bisection). This is
#      now a stated ceiling, not a pure empirical calibration -- it trades
#      away some of the SG-Trend-Index grounding for a more conservative,
#      user-specified long-run assumption.
MF_ANNUAL_COST = 0.08839
df["MF_gross"] = df["TSMOM"] + df["RF"]
df["MF"] = df["MF_gross"] - MF_ANNUAL_COST / 12.0
print(f"4-way overlap sample (Mkt/SCV/Bond/ManagedFutures): {df.index.min()} to {df.index.max()}, n={len(df)} months")

df["Port_MF_m"] = 0.5 * df["Lev"] + 0.5 * df["MF"]
df["Port_SCV_m"] = 0.5 * df["Lev"] + 0.5 * df["SV"]
df["Port_Bond_m"] = 0.5 * df["Lev"] + 0.5 * df["Bond"]

df.to_csv(rf"{SCRATCH}\mf_monthly.csv")

# =============================================================================
# CORRELATIONS -- including conditional-on-equity-drawdown
# =============================================================================
corr = df[["Mkt", "Lev", "SV", "Bond", "MF"]].corr()
print("\n=== CORRELATION MATRIX (Jan 1985 - Aug 2024 overlap) ===")
print(corr.round(3))
OUT["correlations_mf_period"] = corr.round(4).to_dict()

q25 = df["Mkt"].quantile(0.25)
q75 = df["Mkt"].quantile(0.75)
bad = df[df["Mkt"] <= q25]
good = df[df["Mkt"] >= q75]
print(f"\nCorr(Mkt, X) in worst-quartile Mkt months (n={len(bad)}):")
for col in ["SV", "Bond", "MF"]:
    print(f"  {col}: {bad[['Mkt', col]].corr().iloc[0,1]:.3f}")
print(f"Corr(Mkt, X) in best-quartile Mkt months (n={len(good)}):")
for col in ["SV", "Bond", "MF"]:
    print(f"  {col}: {good[['Mkt', col]].corr().iloc[0,1]:.3f}")

OUT["conditional_corr_mf"] = dict(
    n_bad=int(len(bad)), n_good=int(len(good)),
    bad={c: round(float(bad[["Mkt", c]].corr().iloc[0,1]), 3) for c in ["SV","Bond","MF"]},
    good={c: round(float(good[["Mkt", c]].corr().iloc[0,1]), 3) for c in ["SV","Bond","MF"]},
)

# also: correlation during the worst 10 individual Market months (true crisis months)
worst10 = df.nsmallest(10, "Mkt")
print(f"\nDuring the 10 single worst Market months in this sample:")
print(worst10[["Mkt","SV","Bond","MF"]].round(3))
OUT["worst10_months"] = worst10[["Mkt","SV","Bond","MF"]].round(4).reset_index().astype(str).to_dict(orient="records")

# =============================================================================
# FULL-SAMPLE STATS over the common 1985-2024 window, all strategies
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

strategies = {"mkt": df["Mkt"], "lev": df["Lev"], "sv": df["SV"], "bond": df["Bond"], "mf": df["MF"],
              "port_scv": df["Port_SCV_m"], "port_bond": df["Port_Bond_m"], "port_mf": df["Port_MF_m"]}
print(f"\n=== FULL-SAMPLE STATS, common window {df.index.min()}-{df.index.max()} ===")
full_stats = {}
for k, ret in strategies.items():
    s = stats_from_monthly(ret, k)
    full_stats[k] = s
    print(f"{k:<10} CAGR={s['cagr']*100:6.2f}%  vol={s['ann_vol']*100:6.2f}%  Sharpe={s['sharpe']:5.2f}  "
          f"MDD={s['mdd']*100:7.2f}%  final=${s['final']:,.2f}")
OUT["full_sample_mf_period"] = full_stats
OUT["mf_sample_range"] = dict(start=str(df.index.min()), end=str(df.index.max()), n_months=len(df))

# =============================================================================
# ERA SPLIT for Managed Futures -- the well-known "CTA winter" pattern
# =============================================================================
print("\n=== Managed Futures era split ===")
eras_mf = [("1985-2009 (\"golden era\")", "1985-01", "2009-12"), ("2010-2024 (post-2010, \"CTA winter\")", "2010-01", "2024-08")]
era_mf_results = []
for name, s, e in eras_mf:
    sub_mf = df["MF"].loc[s:e]
    sub_mkt = df["Mkt"].loc[s:e]
    sub_scv = df["SV"].loc[s:e]
    sub_bond = df["Bond"].loc[s:e]
    n_ = len(sub_mf)
    c_mf = (1+sub_mf).prod()**(12/n_)-1
    c_mkt = (1+sub_mkt).prod()**(12/n_)-1
    c_scv = (1+sub_scv).prod()**(12/n_)-1
    c_bond = (1+sub_bond).prod()**(12/n_)-1
    print(f"{name} (n={n_}mo): MF={c_mf*100:.2f}%  Mkt={c_mkt*100:.2f}%  SCV={c_scv*100:.2f}%  Bond={c_bond*100:.2f}%")
    era_mf_results.append(dict(era=name, n=n_, mf=round(c_mf*100,2), mkt=round(c_mkt*100,2), scv=round(c_scv*100,2), bond=round(c_bond*100,2)))
OUT["mf_era_split"] = era_mf_results

np.save(rf"{SCRATCH}\mf_mkt.npy", df["Mkt"].to_numpy())
np.save(rf"{SCRATCH}\mf_lev.npy", df["Lev"].to_numpy())
np.save(rf"{SCRATCH}\mf_sv.npy", df["SV"].to_numpy())
np.save(rf"{SCRATCH}\mf_bond.npy", df["Bond"].to_numpy())
np.save(rf"{SCRATCH}\mf_mf.npy", df["MF"].to_numpy())
np.save(rf"{SCRATCH}\mf_rf.npy", df["RF"].to_numpy())
periods_str = np.array([str(p) for p in df.index])
np.save(rf"{SCRATCH}\mf_periods.npy", periods_str)

# =============================================================================
# KELLY CRITERION -- reusing backtest.py's compute_kelly_metrics methodology
# =============================================================================
def compute_kelly_metrics(R, periods_per_year=12):
    R = np.asarray(R)
    mu = np.mean(R)
    sigma2 = np.var(R)
    f_kelly = 0.0 if sigma2 < 1e-12 else mu / sigma2
    f_kelly = np.clip(f_kelly, -1.0, 10.0)
    f_half = 0.5 * f_kelly
    f_quarter = 0.25 * f_kelly

    sorted_R = np.sort(R)
    var_5 = np.percentile(sorted_R, 5)
    cvar_5 = sorted_R[sorted_R <= var_5].mean() if np.any(sorted_R <= var_5) else var_5
    cvar_5_annualized = cvar_5 * np.sqrt(periods_per_year)
    f_dd = f_kelly * (1.0 - min(1.0, abs(cvar_5_annualized)))
    f_dd = np.clip(f_dd, -1.0, 10.0)

    f_grid = np.linspace(-1.0, 3.0, 400)
    log_growth = np.zeros_like(f_grid)
    for i, f in enumerate(f_grid):
        growth = 1.0 + f * R
        log_growth[i] = np.mean(np.log(np.maximum(growth, 1e-15)))
    f_log_opt = f_grid[np.argmax(log_growth)]

    ann_mu = mu * periods_per_year
    ann_sigma2 = sigma2 * periods_per_year
    return dict(
        full_kelly=float(f_kelly), half_kelly=float(f_half), quarter_kelly=float(f_quarter),
        dd_adjusted_kelly=float(f_dd), log_optimal_kelly=float(f_log_opt),
        ann_mean_excess=float(ann_mu), ann_variance=float(ann_sigma2), ann_vol=float(np.sqrt(ann_sigma2)),
        monthly_mean_excess=float(mu), monthly_vol=float(np.sqrt(sigma2)),
    )

print("\n" + "="*70)
print("KELLY CRITERION (reusing backtest.py's compute_kelly_metrics)")
print("="*70)

# Use the FULL long-history sample (1926-2024) for SCV and Market, matching the
# main report's primary dataset -- not the shorter 1985-2024 MF-overlap window.
full_mkt = pd.read_csv(rf"{SCRATCH}\div_monthly.csv", index_col=0)
sv_excess_full = full_mkt["SV"] - full_mkt["RF"]
mkt_excess_full = full_mkt["Mkt"] - full_mkt["RF"]
lev_excess_full = full_mkt["Lev"] - full_mkt["RF"]

kelly_sv = compute_kelly_metrics(sv_excess_full.to_numpy())
kelly_mkt = compute_kelly_metrics(mkt_excess_full.to_numpy())

# Managed futures Kelly uses its own (shorter, 1985-2024) excess-return sample --
# MF is already reported net of RF collateral yield here, so its "excess return"
# for Kelly purposes is MF - RF (MF as constructed = TSMOM + RF - cost, so MF-RF
# = TSMOM - cost, the actual tradeable excess return of the strategy).
mf_excess = (df["MF"] - df["RF"]).to_numpy(dtype=np.float64)
kelly_mf = compute_kelly_metrics(mf_excess)
OUT["kelly_mf"] = kelly_mf

for name, k in [("Market", kelly_mkt), ("Small-Cap Value (DFSVX-cost-adjusted)", kelly_sv), ("Managed Futures (AQMIX-cost-adjusted)", kelly_mf)]:
    print(f"\n{name}:")
    print(f"  Annualized mean excess return: {k['ann_mean_excess']*100:.2f}%   Annualized vol: {k['ann_vol']*100:.2f}%")
    print(f"  Full Kelly f*:        {k['full_kelly']:.2f}x")
    print(f"  Half Kelly:           {k['half_kelly']:.2f}x")
    print(f"  Quarter Kelly:        {k['quarter_kelly']:.2f}x")
    print(f"  Drawdown-adjusted:    {k['dd_adjusted_kelly']:.2f}x")
    print(f"  Log-optimal (grid):   {k['log_optimal_kelly']:.2f}x")

OUT["kelly"] = dict(market=kelly_mkt, scv=kelly_sv)

with open(rf"{SCRATCH}\mf_kelly_summary.json", "w") as f:
    json.dump(OUT, f, indent=2, default=str)
print("\nDone.")
