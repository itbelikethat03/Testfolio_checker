import numpy as np
import pandas as pd
import json

SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"
with open(rf"{SCRATCH}\div_summary.json") as f:
    OUT = json.load(f)

mkt = np.load(rf"{SCRATCH}\div_mkt.npy"); lev = np.load(rf"{SCRATCH}\div_lev.npy")
sv = np.load(rf"{SCRATCH}\div_sv.npy"); bond = np.load(rf"{SCRATCH}\div_bond.npy")
port_scv_m = np.load(rf"{SCRATCH}\div_port_scv_m.npy"); port_bond_m = np.load(rf"{SCRATCH}\div_port_bond_m.npy")
periods = np.load(rf"{SCRATCH}\div_periods.npy", allow_pickle=True)
n = len(mkt)
WINDOW = 25 * 12  # 300 months

series = dict(mkt=mkt, lev=lev, sv=sv, bond=bond, port_scv=port_scv_m, port_bond=port_bond_m)
log_cum = {k: np.concatenate([[0.0], np.cumsum(np.log1p(v))]) for k, v in series.items()}

n_windows = n - WINDOW + 1
ann = {}
cum = {}
for k in series:
    c = np.exp(log_cum[k][WINDOW:] - log_cum[k][:n_windows]) - 1
    cum[k] = c
    ann[k] = (1 + c) ** (1/25) - 1

win_start = periods[0:n_windows]
win_end = periods[WINDOW-1:n]

print(f"Rolling 25yr (300mo) windows: {n_windows}")

n_scv_beats_mkt = (ann["port_scv"] > ann["mkt"]).sum()
n_bond_beats_mkt = (ann["port_bond"] > ann["mkt"]).sum()
n_scv_beats_lev = (ann["port_scv"] > ann["lev"]).sum()
n_bond_beats_lev = (ann["port_bond"] > ann["lev"]).sum()
n_scv_beats_bond = (ann["port_scv"] > ann["port_bond"]).sum()

print(f"50/50 SCV port beats Market:  {n_scv_beats_mkt}/{n_windows} ({n_scv_beats_mkt/n_windows*100:.1f}%)")
print(f"50/50 Bond port beats Market: {n_bond_beats_mkt}/{n_windows} ({n_bond_beats_mkt/n_windows*100:.1f}%)")
print(f"50/50 SCV port beats 2xMkt:   {n_scv_beats_lev}/{n_windows} ({n_scv_beats_lev/n_windows*100:.1f}%)")
print(f"50/50 Bond port beats 2xMkt:  {n_bond_beats_lev}/{n_windows} ({n_bond_beats_lev/n_windows*100:.1f}%)")
print(f"50/50 SCV port beats 50/50 Bond port: {n_scv_beats_bond}/{n_windows} ({n_scv_beats_bond/n_windows*100:.1f}%)")

OUT["rolling25"] = dict(n_windows=int(n_windows), window_months=WINDOW,
    n_scv_beats_mkt=int(n_scv_beats_mkt), pct_scv_beats_mkt=round(n_scv_beats_mkt/n_windows*100,1),
    n_bond_beats_mkt=int(n_bond_beats_mkt), pct_bond_beats_mkt=round(n_bond_beats_mkt/n_windows*100,1),
    n_scv_beats_lev=int(n_scv_beats_lev), pct_scv_beats_lev=round(n_scv_beats_lev/n_windows*100,1),
    n_bond_beats_lev=int(n_bond_beats_lev), pct_bond_beats_lev=round(n_bond_beats_lev/n_windows*100,1),
    n_scv_beats_bond=int(n_scv_beats_bond), pct_scv_beats_bond=round(n_scv_beats_bond/n_windows*100,1),
    stats={})

def summarize(arr):
    return dict(worst=round(float(arr.min())*100,2), best=round(float(arr.max())*100,2),
                p5=round(float(np.percentile(arr,5))*100,2), p25=round(float(np.percentile(arr,25))*100,2),
                p50=round(float(np.percentile(arr,50))*100,2), p75=round(float(np.percentile(arr,75))*100,2),
                p95=round(float(np.percentile(arr,95))*100,2))

for k in series:
    OUT["rolling25"]["stats"][k] = summarize(ann[k])
    print(f"{k}: p5={summarize(ann[k])['p5']}% p50={summarize(ann[k])['p50']}% p95={summarize(ann[k])['p95']}%  "
          f"worst={summarize(ann[k])['worst']}% best={summarize(ann[k])['best']}%")

# ---- risk-adjusted: how often does bond portfolio have better Sharpe than SCV portfolio despite lower CAGR? ----
# compute rolling-window vol and Sharpe using monthly returns within each window
def rolling_vol_sharpe(ret, window, rf_ret):
    vol = np.empty(n_windows)
    sharpe = np.empty(n_windows)
    for i in range(n_windows):
        r = ret[i:i+window]
        v = r.std() * np.sqrt(12)
        vol[i] = v
        rf_c = (1+rf_ret[i:i+window]).prod()**(12/window)-1
        c = (1+r).prod()**(12/window)-1
        sharpe[i] = (c - rf_c) / v if v > 0 else np.nan
    return vol, sharpe

rf_arr = np.load(rf"{SCRATCH}\div_rf.npy")
print("\nComputing rolling Sharpe (this scans each window; may take a moment)...")
vol_scv, sharpe_scv = rolling_vol_sharpe(port_scv_m, WINDOW, rf_arr)
vol_bond, sharpe_bond = rolling_vol_sharpe(port_bond_m, WINDOW, rf_arr)

n_bond_better_sharpe = (sharpe_bond > sharpe_scv).sum()
n_bond_better_sharpe_despite_lower_cagr = ((sharpe_bond > sharpe_scv) & (ann["port_bond"] < ann["port_scv"])).sum()
print(f"Bond portfolio has higher Sharpe than SCV portfolio: {n_bond_better_sharpe}/{n_windows} ({n_bond_better_sharpe/n_windows*100:.1f}%)")
print(f"...of which, despite LOWER CAGR: {n_bond_better_sharpe_despite_lower_cagr}/{n_windows} ({n_bond_better_sharpe_despite_lower_cagr/n_windows*100:.1f}%)")

OUT["rolling25"]["pct_bond_better_sharpe"] = round(n_bond_better_sharpe/n_windows*100,1)
OUT["rolling25"]["pct_bond_better_sharpe_despite_lower_cagr"] = round(n_bond_better_sharpe_despite_lower_cagr/n_windows*100,1)

# strongest SCV period (by ann return) -- objective definition
best_idx_sv_port = int(np.argmax(ann["sv"]))  # strongest for the standalone SCV factor itself
print(f"\nStrongest 25yr SCV window (standalone factor): {win_start[best_idx_sv_port]} to {win_end[best_idx_sv_port]}, "
      f"SCV ann={ann['sv'][best_idx_sv_port]*100:.2f}%")
OUT["rolling25"]["best_sv_window"] = dict(start=str(win_start[best_idx_sv_port]), end=str(win_end[best_idx_sv_port]),
                                            sv_ann=round(float(ann['sv'][best_idx_sv_port])*100,2), start_month_idx=best_idx_sv_port)

with open(rf"{SCRATCH}\div_summary.json", "w") as f:
    json.dump(OUT, f, indent=2, default=str)

np.save(rf"{SCRATCH}\div_roll_win_end.npy", win_end)
for k in series:
    np.save(rf"{SCRATCH}\div_roll_ann_{k}.npy", ann[k])

print("\nStage 2 (rolling 25yr) complete.")
