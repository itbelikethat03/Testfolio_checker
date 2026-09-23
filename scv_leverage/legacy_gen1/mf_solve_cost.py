import numpy as np
import pandas as pd

SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"
ROOT = r"c:\Python Datoteke"

TARGET_CAGR = 0.06

def solve_cost(gross_returns: pd.Series, periods_per_year: float, target=TARGET_CAGR):
    """Bisection: find constant per-period cost c (annualized units) such that
    compounding (gross - c/periods_per_year) hits `target` CAGR."""
    def cagr_at(c_annual):
        net = gross_returns - c_annual / periods_per_year
        nav = (1 + net).prod()
        n = len(net)
        return nav ** (periods_per_year / n) - 1
    lo, hi = -0.20, 0.30
    for _ in range(60):
        mid = (lo + hi) / 2
        if cagr_at(mid) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

# ---- Annual series (for portfolios_1_5x.py) ----
mkt = pd.read_csv(rf"{ROOT}\F-F_Research_Data_Factors_daily.csv", skiprows=4, encoding="utf-8-sig")
mkt.columns = ["date", "Mkt-RF", "SMB", "HML", "RF"]
mkt["date"] = pd.to_datetime(mkt["date"], format="%Y%m%d", errors="coerce")
mkt = mkt.dropna(subset=["date"])
mkt["RF_d"] = pd.to_numeric(mkt["RF"], errors="coerce") / 100.0
mkt = mkt.dropna(subset=["RF_d"]).set_index("date")
rf_monthly = (1 + mkt["RF_d"]).resample("ME").prod() - 1
rf_monthly.index = rf_monthly.index.to_period("M").to_timestamp("M")

tsmom = pd.read_excel(rf"{SCRATCH}\tsmom.xlsx", sheet_name="TSMOM Factors", header=None, skiprows=17)
tsmom.columns = ["date", "TSMOM", "TSMOM_CM", "TSMOM_EQ", "TSMOM_FI", "TSMOM_FX"]
tsmom = tsmom.dropna(subset=["date"])
tsmom["date"] = pd.to_datetime(tsmom["date"])
tsmom = tsmom.set_index("date")
tsmom.index = tsmom.index.to_period("M").to_timestamp("M")
mf_m_gross = tsmom["TSMOM"] + rf_monthly.reindex(tsmom.index)

annual_mf_gross = (1 + mf_m_gross).resample("YE").prod() - 1
annual_mf_gross.index = annual_mf_gross.index.year
annual_mf_gross = annual_mf_gross.loc[1985:2024]

cost_annual = solve_cost(annual_mf_gross, 1.0)
print(f"[Annual series, 1985-2024] Required cost for {TARGET_CAGR*100:.1f}% CAGR: {cost_annual*100:.3f}%/yr")
check = ((1 + annual_mf_gross - cost_annual).prod()) ** (1/len(annual_mf_gross)) - 1
print(f"  Check: resulting CAGR = {check*100:.3f}%")

# ---- Monthly series (for mf_and_kelly.py / div report), Jan1985-Aug2024 ----
mf_m_gross_sub = mf_m_gross.loc[(mf_m_gross.index.year >= 1985) & (mf_m_gross.index <= pd.Timestamp("2024-08-31"))]
cost_monthly_annualized = solve_cost(mf_m_gross_sub, 12.0)
print(f"\n[Monthly series, Jan1985-Aug2024] Required cost for {TARGET_CAGR*100:.1f}% CAGR: {cost_monthly_annualized*100:.3f}%/yr")
check2 = ((1 + mf_m_gross_sub - cost_monthly_annualized/12).prod()) ** (12/len(mf_m_gross_sub)) - 1
print(f"  Check: resulting CAGR = {check2*100:.3f}%")

print(f"\nFor reference, gross (no cost) CAGR:")
print(f"  Annual: {((1+annual_mf_gross).prod()**(1/len(annual_mf_gross))-1)*100:.2f}%")
print(f"  Monthly: {((1+mf_m_gross_sub).prod()**(12/len(mf_m_gross_sub))-1)*100:.2f}%")
