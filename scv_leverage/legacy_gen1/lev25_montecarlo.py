"""
Stage 2: Monte Carlo (block bootstrap, extended to Market+RF+SCV jointly) and
robustness tests for the 2x Market vs SCV vs Market, 25-year comparison.
"""
import numpy as np
import pandas as pd
import json
import time

ROOT = r"c:\Python Datoteke"
SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"
TRADING_DAYS = 252

with open(rf"{SCRATCH}\l25_summary_partial.json") as f:
    OUT = json.load(f)

# ---- reload daily series ----
mkt = pd.read_csv(rf"{ROOT}\F-F_Research_Data_Factors_daily.csv", skiprows=4, encoding="utf-8-sig")
mkt.columns = ["date", "Mkt-RF", "SMB", "HML", "RF"]
mkt["date"] = pd.to_datetime(mkt["date"], format="%Y%m%d", errors="coerce")
mkt = mkt.dropna(subset=["date"])
for c in ["Mkt-RF", "SMB", "HML", "RF"]:
    mkt[c] = pd.to_numeric(mkt[c], errors="coerce")
mkt = mkt.dropna(subset=["Mkt-RF", "RF"]).reset_index(drop=True)
mkt["Mkt_RF_d"] = mkt["Mkt-RF"] / 100.0
mkt["RF_d"] = mkt["RF"] / 100.0

sv = pd.read_csv(rf"{SCRATCH}\ff6\6_Portfolios_2x3_Daily.csv", skiprows=18, nrows=26293 - 19)
sv.columns = ["date", "SMALL_LoBM", "ME1_BM2", "SMALL_HiBM", "BIG_LoBM", "ME2_BM2", "BIG_HiBM"]
sv["date"] = pd.to_datetime(sv["date"], format="%Y%m%d", errors="coerce")
sv = sv.dropna(subset=["date"])
sv["SV_Total"] = pd.to_numeric(sv["SMALL_HiBM"], errors="coerce") / 100.0
sv = sv.dropna(subset=["SV_Total"]).reset_index(drop=True)

df = pd.merge(mkt[["date", "Mkt_RF_d", "RF_d"]], sv[["date", "SV_Total"]], on="date", how="inner")
df = df.sort_values("date").reset_index(drop=True)

mkt_rf_hist = df["Mkt_RF_d"].to_numpy(dtype=np.float64)
rf_hist = df["RF_d"].to_numpy(dtype=np.float64)
sv_hist = df["SV_Total"].to_numpy(dtype=np.float64)
n_obs = len(df)

LEVERAGE = 2.0
SPREAD_ANNUAL = 0.004
EXPENSE_ANNUAL = 0.0095
spread_daily = SPREAD_ANNUAL / TRADING_DAYS
expense_daily = EXPENSE_ANNUAL / TRADING_DAYS

def block_bootstrap_indices(n_observations, n_simulations, n_days, block_size, rng):
    """Reused verbatim from backtest.py."""
    n_possible_blocks = n_observations - block_size + 1
    n_blocks_needed = int(np.ceil(n_days / block_size))
    starts = rng.integers(0, n_possible_blocks, size=(n_simulations, n_blocks_needed))
    offsets = np.arange(block_size)
    idx = (starts[:, :, None] + offsets[None, None, :]).reshape(n_simulations, -1)[:, :n_days]
    return idx

def run_mc(n_sims, n_years, block_size, spread_annual, expense_annual, seed, chunk=5000):
    """
    Chunked moving-block bootstrap MC, jointly resampling (Mkt-RF, RF, SCV) with
    the SAME block indices per path (preserves historical correlation), then
    applies the backtest.py leverage-cost formula. Returns per-path annualized
    returns and max drawdowns for Market, 2x Market, SCV (no full paths kept).
    """
    n_days = n_years * TRADING_DAYS
    sd = spread_annual / TRADING_DAYS
    ed = expense_annual / TRADING_DAYS
    rng = np.random.default_rng(seed)

    mkt_ann = np.empty(n_sims); lev_ann = np.empty(n_sims); sv_ann = np.empty(n_sims)
    mkt_dd = np.empty(n_sims); lev_dd = np.empty(n_sims); sv_dd = np.empty(n_sims)

    n_chunks = int(np.ceil(n_sims / chunk))
    t0 = time.time()
    for c in range(n_chunks):
        lo = c * chunk
        hi = min(n_sims, lo + chunk)
        b = hi - lo
        idx = block_bootstrap_indices(n_obs, b, n_days, block_size, rng)  # (b, n_days)

        mkt_rf_b = mkt_rf_hist[idx].astype(np.float32)
        rf_b = rf_hist[idx].astype(np.float32)
        sv_b = sv_hist[idx].astype(np.float32)

        mkt_total_b = mkt_rf_b + rf_b
        daily_cost_b = (LEVERAGE - 1.0) * (rf_b + sd) + ed
        lev_ret_b = LEVERAGE * mkt_total_b - daily_cost_b

        mkt_fac = np.maximum(1.0 + mkt_total_b, 0.0)
        lev_fac = np.maximum(1.0 + lev_ret_b, 0.0)
        sv_fac = np.maximum(1.0 + sv_b, 0.0)
        del mkt_rf_b, rf_b, sv_b, mkt_total_b, daily_cost_b, lev_ret_b

        for fac, ann_out, dd_out in [(mkt_fac, mkt_ann, mkt_dd), (lev_fac, lev_ann, lev_dd), (sv_fac, sv_ann, sv_dd)]:
            nav = np.cumprod(fac, axis=1)
            final_nav = nav[:, -1]
            ann_out[lo:hi] = final_nav ** (1.0 / n_years) - 1.0
            peak = np.maximum.accumulate(nav, axis=1)
            dd = nav / peak - 1.0
            dd_out[lo:hi] = dd.min(axis=1)
            del nav, peak, dd
        del mkt_fac, lev_fac, sv_fac
    print(f"  MC ({n_sims} sims, {n_years}yr, block={block_size}td, spread={spread_annual*100:.2f}%, "
          f"expense={expense_annual*100:.2f}%) done in {time.time()-t0:.1f}s")
    return dict(mkt_ann=mkt_ann, lev_ann=lev_ann, sv_ann=sv_ann, mkt_dd=mkt_dd, lev_dd=lev_dd, sv_dd=sv_dd)

# =============================================================================
# MAIN MONTE CARLO: 100,000 sims, 25yr, block=20 trading days (backtest.py default)
# =============================================================================
print("Running main Monte Carlo (100,000 x 25yr, block bootstrap, block=20td)...")
mc = run_mc(n_sims=100_000, n_years=25, block_size=20, spread_annual=SPREAD_ANNUAL,
            expense_annual=EXPENSE_ANNUAL, seed=42, chunk=4000)

mkt_ann, lev_ann, sv_ann = mc["mkt_ann"], mc["lev_ann"], mc["sv_ann"]

p_lev_beats_mkt = (lev_ann > mkt_ann).mean() * 100
p_sv_beats_mkt = (sv_ann > mkt_ann).mean() * 100
p_lev_beats_sv = (lev_ann > sv_ann).mean() * 100
p_sv_beats_lev = (sv_ann > lev_ann).mean() * 100

print(f"\nP(2x Market > Market): {p_lev_beats_mkt:.1f}%")
print(f"P(SCV > Market): {p_sv_beats_mkt:.1f}%")
print(f"P(2x Market > SCV): {p_lev_beats_sv:.1f}%")
print(f"P(SCV > 2x Market): {p_sv_beats_lev:.1f}%")

thresholds = [0.05, 0.10, 0.20]
under_lev = {}
under_sv = {}
for thr in thresholds:
    under_lev[thr] = ((lev_ann - mkt_ann) <= -thr).mean() * 100
    under_sv[thr] = ((sv_ann - mkt_ann) <= -thr).mean() * 100
    print(f"P(2x Market underperforms Mkt by >= {int(thr*100)}pp ann.): {under_lev[thr]:.2f}%   "
          f"P(SCV underperforms Mkt by >= {int(thr*100)}pp ann.): {under_sv[thr]:.2f}%")

def pct_summary(arr):
    return dict(
        median=round(float(np.median(arr))*100,2),
        p5=round(float(np.percentile(arr,5))*100,2), p25=round(float(np.percentile(arr,25))*100,2),
        p75=round(float(np.percentile(arr,75))*100,2), p95=round(float(np.percentile(arr,95))*100,2),
        worst=round(float(arr.min())*100,2), best=round(float(arr.max())*100,2),
        mean_dd=None,
    )

OUT["mc"] = dict(
    n_sims=100_000, n_years=25, block_size=20,
    p_lev_beats_mkt=round(p_lev_beats_mkt,1), p_sv_beats_mkt=round(p_sv_beats_mkt,1),
    p_lev_beats_sv=round(p_lev_beats_sv,1), p_sv_beats_lev=round(p_sv_beats_lev,1),
    under_lev={str(int(k*100)): round(v,2) for k,v in under_lev.items()},
    under_sv={str(int(k*100)): round(v,2) for k,v in under_sv.items()},
    mkt=pct_summary(mkt_ann), lev=pct_summary(lev_ann), sv=pct_summary(sv_ann),
    lev_median_dd=round(float(np.median(mc["lev_dd"]))*100,1),
    lev_p5_dd=round(float(np.percentile(mc["lev_dd"],5))*100,1),
    mkt_median_dd=round(float(np.median(mc["mkt_dd"]))*100,1),
    sv_median_dd=round(float(np.median(mc["sv_dd"]))*100,1),
    lev_prob_ruin=round(float((mc["lev_dd"] < -0.90).mean())*100,2),
)
print(f"Median max DD over 25yr sims: Mkt {OUT['mc']['mkt_median_dd']}%  2x {OUT['mc']['lev_median_dd']}%  SCV {OUT['mc']['sv_median_dd']}%")
print(f"P(2x Market DD < -90% at some point in 25yr): {OUT['mc']['lev_prob_ruin']:.2f}%")

np.save(rf"{SCRATCH}\l25_mc_mkt_ann.npy", mkt_ann)
np.save(rf"{SCRATCH}\l25_mc_lev_ann.npy", lev_ann)
np.save(rf"{SCRATCH}\l25_mc_sv_ann.npy", sv_ann)
np.save(rf"{SCRATCH}\l25_mc_lev_dd.npy", mc["lev_dd"])
np.save(rf"{SCRATCH}\l25_mc_mkt_dd.npy", mc["mkt_dd"])
np.save(rf"{SCRATCH}\l25_mc_sv_dd.npy", mc["sv_dd"])

with open(rf"{SCRATCH}\l25_summary_partial.json", "w") as f:
    json.dump(OUT, f, indent=2, default=str)
print("\nStage 2 (Monte Carlo) complete.")
