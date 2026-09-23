import numpy as np
import json
import time

SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"
with open(rf"{SCRATCH}\div_summary.json") as f:
    OUT = json.load(f)

mkt_hist = np.load(rf"{SCRATCH}\div_mkt.npy"); rf_hist = np.load(rf"{SCRATCH}\div_rf.npy")
sv_hist = np.load(rf"{SCRATCH}\div_sv.npy"); bond_hist = np.load(rf"{SCRATCH}\div_bond.npy")
n_obs = len(mkt_hist)

LEVERAGE = 2.0
SPREAD_ANNUAL = 0.004
EXPENSE_ANNUAL = 0.0095
sd_m = SPREAD_ANNUAL / 12.0
ed_m = EXPENSE_ANNUAL / 12.0

def block_bootstrap_indices(n_observations, n_simulations, n_periods, block_size, rng):
    """Reused from backtest.py (block_bootstrap_indices), monthly granularity here."""
    n_possible_blocks = n_observations - block_size + 1
    n_blocks_needed = int(np.ceil(n_periods / block_size))
    starts = rng.integers(0, n_possible_blocks, size=(n_simulations, n_blocks_needed))
    offsets = np.arange(block_size)
    idx = (starts[:, :, None] + offsets[None, None, :]).reshape(n_simulations, -1)[:, :n_periods]
    return idx

def run_mc(n_sims, n_years, block_size, seed, chunk=10000):
    n_periods = n_years * 12
    rng = np.random.default_rng(seed)
    names = ["mkt", "lev", "sv", "bond", "port_scv", "port_bond"]
    ann = {k: np.empty(n_sims) for k in names}
    dd = {k: np.empty(n_sims) for k in names}

    n_chunks = int(np.ceil(n_sims / chunk))
    t0 = time.time()
    for c in range(n_chunks):
        lo = c*chunk; hi = min(n_sims, lo+chunk); b = hi-lo
        idx = block_bootstrap_indices(n_obs, b, n_periods, block_size, rng)

        mkt_b = mkt_hist[idx]; rf_b = rf_hist[idx]; sv_b = sv_hist[idx]; bond_b = bond_hist[idx]
        monthly_cost = (LEVERAGE-1.0)*(rf_b + sd_m) + ed_m
        lev_b = LEVERAGE*mkt_b - monthly_cost
        port_scv_b = 0.5*lev_b + 0.5*sv_b
        port_bond_b = 0.5*lev_b + 0.5*bond_b

        for name, ret_b in [("mkt",mkt_b),("lev",lev_b),("sv",sv_b),("bond",bond_b),
                              ("port_scv",port_scv_b),("port_bond",port_bond_b)]:
            fac = np.maximum(1.0+ret_b, 0.0)
            nav = np.cumprod(fac, axis=1)
            final = nav[:,-1]
            ann[name][lo:hi] = final ** (1.0/n_years) - 1.0
            peak = np.maximum.accumulate(nav, axis=1)
            ddv = nav/peak - 1.0
            dd[name][lo:hi] = ddv.min(axis=1)
    print(f"  MC ({n_sims} sims, {n_years}yr, block={block_size}mo) done in {time.time()-t0:.1f}s")
    return ann, dd

print("Running main Monte Carlo (100,000 x 25yr, monthly block bootstrap, block=12mo)...")
ann, dd = run_mc(n_sims=100_000, n_years=25, block_size=12, seed=42, chunk=10000)

mkt_a, lev_a, sv_a, bond_a = ann["mkt"], ann["lev"], ann["sv"], ann["bond"]
pscv_a, pbond_a = ann["port_scv"], ann["port_bond"]

print("\n=== MC head-to-head ===")
res = {}
for name, arr in ann.items():
    p_beat_mkt = (arr > mkt_a).mean()*100
    p_beat_lev = (arr > lev_a).mean()*100
    print(f"{name}: P(>Mkt)={p_beat_mkt:.1f}%  P(>2xMkt)={p_beat_lev:.1f}%  median={np.median(arr)*100:.2f}%  "
          f"p5={np.percentile(arr,5)*100:.2f}%  p95={np.percentile(arr,95)*100:.2f}%")
    res[name] = dict(
        p_beat_mkt=round(p_beat_mkt,1), p_beat_lev=round(p_beat_lev,1),
        median=round(float(np.median(arr))*100,2), p5=round(float(np.percentile(arr,5))*100,2),
        p25=round(float(np.percentile(arr,25))*100,2), p75=round(float(np.percentile(arr,75))*100,2),
        p95=round(float(np.percentile(arr,95))*100,2),
        worst=round(float(arr.min())*100,2), best=round(float(arr.max())*100,2),
        median_dd=round(float(np.median(dd[name]))*100,1), p5_dd=round(float(np.percentile(dd[name],5))*100,1),
    )
    for thr in [0.30,0.40,0.50,0.60]:
        res[name][f"p_dd_gt_{int(thr*100)}"] = round(float((dd[name] < -thr).mean())*100,2)

p_scv_beats_bond = (pscv_a > pbond_a).mean()*100
print(f"\nP(50/50 SCV port > 50/50 Bond port) = {p_scv_beats_bond:.1f}%")
res["p_scv_port_beats_bond_port"] = round(p_scv_beats_bond,1)

for k, arr in dd.items():
    print(f"{k} maxDD: median={np.median(arr)*100:.1f}%  p5={np.percentile(arr,5)*100:.1f}%  "
          f"P(DD<-30%)={(arr<-0.30).mean()*100:.1f}%  P(DD<-50%)={(arr<-0.50).mean()*100:.1f}%  P(DD<-60%)={(arr<-0.60).mean()*100:.1f}%")

OUT["mc"] = res
OUT["mc"]["n_sims"] = 100_000; OUT["mc"]["n_years"] = 25; OUT["mc"]["block_months"] = 12

for name, arr in ann.items():
    np.save(rf"{SCRATCH}\div_mc_ann_{name}.npy", arr)
for name, arr in dd.items():
    np.save(rf"{SCRATCH}\div_mc_dd_{name}.npy", arr)

with open(rf"{SCRATCH}\div_summary.json", "w") as f:
    json.dump(OUT, f, indent=2, default=str)
print("\nStage 3 (Monte Carlo) complete.")
