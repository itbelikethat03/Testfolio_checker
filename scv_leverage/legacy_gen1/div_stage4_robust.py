import numpy as np
import pandas as pd
import json

SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"
with open(rf"{SCRATCH}\div_summary.json") as f:
    OUT = json.load(f)

mkt = np.load(rf"{SCRATCH}\div_mkt.npy"); lev = np.load(rf"{SCRATCH}\div_lev.npy")
sv = np.load(rf"{SCRATCH}\div_sv.npy"); bond = np.load(rf"{SCRATCH}\div_bond.npy")
port_scv = np.load(rf"{SCRATCH}\div_port_scv_m.npy"); port_bond = np.load(rf"{SCRATCH}\div_port_bond_m.npy")
periods = np.load(rf"{SCRATCH}\div_periods.npy", allow_pickle=True)
years_arr = np.load(rf"{SCRATCH}\div_years.npy")
n = len(mkt)
WINDOW = 300

def cagr_of(ret, mask=None):
    if mask is not None:
        ret = ret[mask]
    fac = np.maximum(1.0+ret, 0.0)
    n_ = len(fac)
    return float(np.prod(fac)) ** (12.0/n_) - 1.0

# =============================================================================
# A. Exclude strongest SCV 25yr period (objectively: highest standalone SCV ann. return)
# =============================================================================
best = OUT["rolling25"]["best_sv_window"]
start_idx = best["start_month_idx"]
end_idx = start_idx + WINDOW
print(f"Excluding strongest SCV period: {best['start']} to {best['end']} (months {start_idx}:{end_idx})")

mask = np.ones(n, dtype=bool)
mask[start_idx:end_idx] = False

names = ["mkt","lev","sv","bond","port_scv","port_bond"]
arrs = {"mkt":mkt,"lev":lev,"sv":sv,"bond":bond,"port_scv":port_scv,"port_bond":port_bond}
excl_results = {}
print("\n=== A. Full-sample CAGR, strongest SCV period excluded ===")
for name in names:
    full_c = cagr_of(arrs[name])
    excl_c = cagr_of(arrs[name], mask)
    excl_results[name] = dict(full=round(full_c*100,2), excl=round(excl_c*100,2))
    print(f"{name:<12} full={full_c*100:6.2f}%   ex-best-SCV-period={excl_c*100:6.2f}%")

OUT["robust_exclude_best"] = dict(window=best, results=excl_results)

# =============================================================================
# B. Era split
# =============================================================================
eras = [("1926-1951",1926,1951), ("1951-1976",1951,1976), ("1976-2001",1976,2001), ("2001-2024",2001,2025)]
era_results = []
print("\n=== B. Era split ===")
for name_e, y0, y1 in eras:
    emask = (years_arr >= y0) & (years_arr < y1)
    if emask.sum() < 24:
        continue
    row = {"era": name_e, "n_months": int(emask.sum())}
    for name in names:
        row[name] = round(cagr_of(arrs[name], emask)*100, 2)
    era_results.append(row)
    print(f"{name_e} (n={emask.sum()}mo): " + "  ".join(f"{k}={row[k]:.2f}%" for k in names))
OUT["robust_eras"] = era_results

with open(rf"{SCRATCH}\div_summary.json", "w") as f:
    json.dump(OUT, f, indent=2, default=str)
print("\nStage 4 (robustness) complete.")
