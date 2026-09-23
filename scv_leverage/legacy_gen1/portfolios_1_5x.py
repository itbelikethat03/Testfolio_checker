"""
Two 1.5x-levered multi-asset portfolios, compared head-to-head:

  Portfolio A ("2x Market Core"): 80% 2x Market + 20% Gold + 25% Bonds + 25% Managed Futures
  Portfolio B ("SCV Core"):      100% SCV + 20% Managed Futures + 20% Bonds + 10% Gold

Both sum to 150% of capital -- read as a genuine 1.5x-levered multi-asset
portfolio (the extra 50% of notional is financed at RF+spread, same convention
as the 2x Market leverage cost elsewhere in this analysis), not a typo.
Rebalanced every 2 years ("bi-yearly") as requested.

FREQUENCY: switched to ANNUAL for this specific comparison. Gold has no
reliable monthly total-return series available without a paid data feed;
the only credible long-history gold series obtainable here is Aswath
Damodaran's (NYU Stern) annual gold price series, 1927-2025. Since the
Managed Futures data (AQR TSMOM) starts 1985 and Bond data (Shiller) ends
Aug 2024, the common window is 1985-2024 (40 annual observations) --
annual frequency is a natural fit for gold's data availability AND for a
"bi-yearly" rebalance cadence.
"""
import numpy as np
import pandas as pd
import json

ROOT = r"c:\Python Datoteke"
SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"
OUT = {}

# =============================================================================
# 1. LOAD everything at ANNUAL (calendar-year) frequency, 1985-2024
# =============================================================================
mkt = pd.read_csv(rf"{ROOT}\F-F_Research_Data_Factors_daily.csv", skiprows=4, encoding="utf-8-sig")
mkt.columns = ["date", "Mkt-RF", "SMB", "HML", "RF"]
mkt["date"] = pd.to_datetime(mkt["date"], format="%Y%m%d", errors="coerce")
mkt = mkt.dropna(subset=["date"])
for c in ["Mkt-RF", "RF"]:
    mkt[c] = pd.to_numeric(mkt[c], errors="coerce")
mkt = mkt.dropna(subset=["Mkt-RF", "RF"]).reset_index(drop=True)
mkt["Mkt_Total"] = (mkt["Mkt-RF"] + mkt["RF"]) / 100.0
mkt["RF_d"] = mkt["RF"] / 100.0
mkt = mkt.set_index("date")

sv = pd.read_csv(rf"{SCRATCH}\ff6\6_Portfolios_2x3_Daily.csv", skiprows=18, nrows=26293 - 19)
sv.columns = ["date", "SMALL_LoBM", "ME1_BM2", "SMALL_HiBM", "BIG_LoBM", "ME2_BM2", "BIG_HiBM"]
sv["date"] = pd.to_datetime(sv["date"], format="%Y%m%d", errors="coerce")
sv = sv.dropna(subset=["date"])
sv["SV_Total"] = pd.to_numeric(sv["SMALL_HiBM"], errors="coerce") / 100.0
sv = sv.dropna(subset=["SV_Total"]).reset_index(drop=True).set_index("date")

annual_mkt = (1 + mkt["Mkt_Total"]).resample("YE").prod() - 1
annual_rf = (1 + mkt["RF_d"]).resample("YE").prod() - 1
annual_sv_gross = (1 + sv["SV_Total"]).resample("YE").prod() - 1
for s in (annual_mkt, annual_rf, annual_sv_gross):
    s.index = s.index.year

SV_ANNUAL_COST = 0.01092  # DFSVX-calibrated
annual_sv = annual_sv_gross - SV_ANNUAL_COST

LEVERAGE = 2.0
SPREAD_ANNUAL = 0.004
EXPENSE_ANNUAL = 0.0095
annual_lev = LEVERAGE * annual_mkt - ((LEVERAGE - 1.0) * (annual_rf + SPREAD_ANNUAL) + EXPENSE_ANNUAL)

# ---- Bonds (Shiller), aggregated to annual ----
shiller = pd.read_excel(rf"{SCRATCH}\ie_data.xls", sheet_name="Data", header=None)
bond = shiller.iloc[8:, [0, 17]].copy()
bond.columns = ["date_frac", "bond_factor"]
bond = bond.dropna(subset=["date_frac"])
bond["date_frac"] = pd.to_numeric(bond["date_frac"], errors="coerce")
bond = bond.dropna(subset=["date_frac"])
year = np.floor(bond["date_frac"]).astype(int)
month = np.round((bond["date_frac"] - year) * 100).astype(int).replace(0, 1)
bond["period"] = pd.PeriodIndex.from_fields(year=year, month=month, freq="M")
bond["Bond"] = pd.to_numeric(bond["bond_factor"], errors="coerce") - 1.0
bond = bond.dropna(subset=["Bond"]).set_index("period")
bond_ts = bond["Bond"]
bond_ts.index = bond_ts.index.to_timestamp()
annual_bond = (1 + bond_ts).resample("YE").prod() - 1
annual_bond.index = annual_bond.index.year

# ---- Managed Futures (AQR TSMOM), aggregated to annual, AQMIX-calibrated cost ----
tsmom = pd.read_excel(rf"{SCRATCH}\tsmom.xlsx", sheet_name="TSMOM Factors", header=None, skiprows=17)
tsmom.columns = ["date", "TSMOM", "TSMOM_CM", "TSMOM_EQ", "TSMOM_FI", "TSMOM_FX"]
tsmom = tsmom.dropna(subset=["date"])
tsmom["date"] = pd.to_datetime(tsmom["date"])
tsmom = tsmom.set_index("date")
rf_monthly = (1 + mkt["RF_d"]).resample("ME").prod() - 1
rf_monthly.index = rf_monthly.index.to_period("M").to_timestamp("M")
tsmom.index = tsmom.index.to_period("M").to_timestamp("M")
mf_m = tsmom["TSMOM"] + rf_monthly.reindex(tsmom.index)
# Third calibration pass (see mf_and_kelly.py for full history): empirical
# checks against AQMIX (1.87pp/yr) and the SG Trend Index (5.02pp/yr) both
# still left standalone Managed Futures compounding near or above 10%/yr --
# implausible for a near-zero-equity-correlation strategy per reader input.
# This cost is instead solved (by bisection) so standalone Managed Futures
# compounds to a deliberately conservative 6.0%/yr over 1985-2024, a stated
# ceiling rather than a pure empirical calibration.
MF_ANNUAL_COST = 0.09492
annual_mf_gross = (1 + mf_m).resample("YE").prod() - 1
annual_mf_gross.index = annual_mf_gross.index.year
annual_mf = annual_mf_gross - MF_ANNUAL_COST

# ---- Gold (Damodaran, NYU Stern), annual price -> annual return ----
gold_raw = pd.read_excel(rf"{SCRATCH}\histretSP.xls", sheet_name="Gold Prices", header=None, skiprows=1)
gold_raw.columns = ["Year", "Price", "c", "d", "Source"]
gold_raw = gold_raw.dropna(subset=["Year", "Price"])
gold_raw["Year"] = gold_raw["Year"].astype(int)
gold_price = gold_raw.set_index("Year")["Price"]
annual_gold = gold_price.pct_change().dropna()

# =============================================================================
# 2. MERGE on common annual window
# =============================================================================
df = pd.DataFrame({
    "Mkt": annual_mkt, "RF": annual_rf, "SV": annual_sv, "Lev": annual_lev,
    "Bond": annual_bond, "MF": annual_mf, "Gold": annual_gold,
}).dropna()
print(f"Common annual sample: {df.index.min()} to {df.index.max()}, n={len(df)} years")
df.to_csv(rf"{SCRATCH}\portfolios_annual.csv")

# =============================================================================
# 3. BUILD THE TWO 1.5x PORTFOLIOS, biennial (every-2-year) rebalance
# =============================================================================
EXTRA_LEVERAGE_SPREAD = SPREAD_ANNUAL  # same financing spread convention as the 2x Market sleeve

def build_150pct_portfolio(weights: dict, df: pd.DataFrame, rf: pd.Series, rebalance_years=2):
    """
    weights: dict of {column: weight}, weights sum to > 1.0 (the excess over
    1.0 is financed at RF + spread, i.e. margin borrowing, same convention as
    the 2x Market leverage-cost formula used throughout this analysis).
    Rebalances back to target weights every `rebalance_years`; drifts between.

    NAV/debt are tracked explicitly and separately (this replaces an earlier,
    buggy version that multiplied the financing charge by GROSS exposure
    -- e.g. 1.5 at a rebalance point -- instead of by NAV, i.e. by the actual
    borrowed dollar amount. That overcharged financing cost by 50% relative
    to what was intended and was enough to make positive-expected-return
    diversifiers, financed on margin, subtract from total return instead of
    adding to it -- the opposite of what leverage on profitable assets should
    do. Fixed here: debt is fixed in dollar terms between rebalances (a margin
    loan sized at the last rebalance, not re-levered every year), and each
    year's financing charge is levied on that fixed debt amount, consistent
    with how the 2x Market leverage-cost formula treats its own "1 unit
    borrowed" as fixed within a compounding period.
    """
    total_w = sum(weights.values())
    excess = total_w - 1.0  # fraction of NAV borrowed at each rebalance
    n = len(df.index)
    port_ret = np.empty(n)
    nav = 1.0
    asset_vals = None
    debt = 0.0
    for i in range(n):
        if i % rebalance_years == 0:
            asset_vals = {k: w * nav for k, w in weights.items()}
            debt = excess * nav
        nav_start = sum(asset_vals.values()) - debt  # == nav, kept explicit for clarity
        financing_cost = debt * (rf.iloc[i] + EXTRA_LEVERAGE_SPREAD)
        pnl = sum(v * df[k].iloc[i] for k, v in asset_vals.items())
        nav_end = nav_start + pnl - financing_cost
        port_ret[i] = nav_end / nav_start - 1.0
        asset_vals = {k: v * (1 + df[k].iloc[i]) for k, v in asset_vals.items()}
        nav = nav_end
    return pd.Series(port_ret, index=df.index)

weights_A = {"Lev": 0.80, "Gold": 0.20, "Bond": 0.25, "MF": 0.25}
weights_B = {"SV": 1.00, "MF": 0.20, "Bond": 0.20, "Gold": 0.10}

port_A = build_150pct_portfolio(weights_A, df, df["RF"], rebalance_years=2)
port_B = build_150pct_portfolio(weights_B, df, df["RF"], rebalance_years=2)
df["Port_A"] = port_A
df["Port_B"] = port_B
df.to_csv(rf"{SCRATCH}\portfolios_annual.csv")

# =============================================================================
# 4. FULL-SAMPLE STATS
# =============================================================================
avg_rf_ann = (1 + df["RF"]).prod() ** (1/len(df)) - 1

def stats_from_annual(ret, name):
    nav = (1 + ret).cumprod()
    n_ = len(ret)
    cagr = nav.iloc[-1] ** (1/n_) - 1
    ann_vol = ret.std()
    peak = nav.cummax()
    dd = nav/peak - 1
    mdd = dd.min()
    sharpe = (cagr - avg_rf_ann) / ann_vol
    return dict(name=name, cagr=float(cagr), ann_vol=float(ann_vol), mdd=float(mdd),
                sharpe=float(sharpe), final=float(nav.iloc[-1]))

print(f"\n=== FULL-SAMPLE STATS, {df.index.min()}-{df.index.max()} (annual) ===")
components = {"mkt": df["Mkt"], "lev": df["Lev"], "sv": df["SV"], "bond": df["Bond"],
              "mf": df["MF"], "gold": df["Gold"], "port_A": df["Port_A"], "port_B": df["Port_B"]}
full_stats = {}
for k, ret in components.items():
    s = stats_from_annual(ret, k)
    full_stats[k] = s
    print(f"{k:<10} CAGR={s['cagr']*100:6.2f}%  vol={s['ann_vol']*100:6.2f}%  Sharpe={s['sharpe']:5.2f}  "
          f"MDD={s['mdd']*100:7.2f}%  final=${s['final']:,.2f}")
OUT["full_sample"] = full_stats
OUT["sample_range"] = dict(start=int(df.index.min()), end=int(df.index.max()), n_years=len(df))
OUT["rf_ann"] = float(avg_rf_ann)

# correlations
corr = df[["Mkt","Lev","SV","Bond","MF","Gold"]].corr()
print("\nCorrelation matrix (annual):")
print(corr.round(3))
OUT["correlations"] = corr.round(4).to_dict()

# Port A vs Port B head to head
diff = port_A - port_B
print(f"\nPort A beat Port B in {(diff>0).sum()}/{len(diff)} years")
OUT["A_beats_B_years"] = dict(count=int((diff>0).sum()), total=len(diff))

with open(rf"{SCRATCH}\portfolios_summary.json", "w") as f:
    json.dump(OUT, f, indent=2, default=str)

np.save(rf"{SCRATCH}\p15_years.npy", df.index.to_numpy())
for k in ["Mkt","RF","Lev","SV","Bond","MF","Gold","Port_A","Port_B"]:
    np.save(rf"{SCRATCH}\p15_{k}.npy", df[k].to_numpy(dtype=np.float64))

print("\nStage 1 (data + portfolios + full-sample stats) complete.")
