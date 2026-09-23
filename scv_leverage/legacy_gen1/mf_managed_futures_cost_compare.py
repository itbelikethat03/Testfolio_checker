import pandas as pd
import numpy as np

ROOT = r"c:\Python Datoteke"
SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"

mkt = pd.read_csv(rf"{ROOT}\F-F_Research_Data_Factors_daily.csv", skiprows=4, encoding="utf-8-sig")
mkt.columns = ["date", "Mkt-RF", "SMB", "HML", "RF"]
mkt["date"] = pd.to_datetime(mkt["date"], format="%Y%m%d", errors="coerce")
mkt = mkt.dropna(subset=["date"])
mkt["RF"] = pd.to_numeric(mkt["RF"], errors="coerce") / 100.0
mkt = mkt.dropna(subset=["RF"]).set_index("date")
rf_m = (1 + mkt["RF"]).resample("ME").prod() - 1
rf_m.index = rf_m.index.to_period("M")

tsmom = pd.read_excel(rf"{SCRATCH}\tsmom.xlsx", sheet_name="TSMOM Factors", header=None, skiprows=17)
tsmom.columns = ["date", "TSMOM", "TSMOM_CM", "TSMOM_EQ", "TSMOM_FI", "TSMOM_FX"]
tsmom = tsmom.dropna(subset=["date"])
tsmom["period"] = pd.PeriodIndex(pd.to_datetime(tsmom["date"]), freq="M")
tsmom = tsmom.set_index("period")

df = pd.DataFrame({"RF": rf_m, "TSMOM": tsmom["TSMOM"]}).dropna()
df["MF"] = df["TSMOM"] + df["RF"]

def cagr(series, start, end):
    sub = series.loc[start:end]
    n = len(sub)
    nav = (1 + sub).prod()
    return nav ** (12/n) - 1, n, sub.index[0], sub.index[-1]

# AQMIX: inception Jan 5 2010, since-inception return quoted as of Jul 31 2026 (4.13%)
c, n, s, e = cagr(df["MF"], "2010-01", "2026-04")  # our data ends Apr 2026
print(f"Raw TSMOM+RF factor, {s} to {e} ({n} months): CAGR = {c*100:.3f}%")
print(f"AQMIX (real fund, since-inception thru Jul 2026): 4.13%")
print(f"Implied annual drag: {(c-0.0413)*100:.3f} pp/yr")
print(f"AQMIX stated gross/net expense ratio: 3.09%")

# also check trailing 10yr and 5yr to see if the gap is stable or period-dependent
for yrs, aqmix_val in [(1,22.01),(3,12.05),(5,13.76),(10,4.36)]:
    end = pd.Period("2026-04", freq="M")
    start = end - yrs*12 + 1
    c2, n2, s2, e2 = cagr(df["MF"], start, end)
    print(f"Trailing {yrs}yr ({s2} to {e2}): Raw MF factor = {c2*100:.2f}%   AQMIX = {aqmix_val:.2f}%   gap = {(c2*100-aqmix_val):.2f}pp")
