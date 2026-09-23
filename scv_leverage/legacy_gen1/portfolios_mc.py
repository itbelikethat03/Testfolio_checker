import numpy as np
import json
import time

SCRATCH = r"C:\Users\moravec\AppData\Local\Temp\claude\c--Python-Datoteke\259ef7eb-d0a5-43e7-8f4b-69ca3cde1378\scratchpad"
with open(rf"{SCRATCH}\portfolios_summary.json") as f:
    OUT = json.load(f)

series = {}
for k in ["Mkt","RF","Lev","SV","Bond","MF","Gold"]:
    series[k] = np.load(rf"{SCRATCH}\p15_{k}.npy")
n_obs = len(series["Mkt"])
print(f"Historical annual pool: {n_obs} observations")

LEVERAGE = 2.0
SPREAD_ANNUAL = 0.004
EXPENSE_ANNUAL = 0.0095

def block_bootstrap_indices(n_observations, n_simulations, n_periods, block_size, rng):
    n_possible_blocks = n_observations - block_size + 1
    n_blocks_needed = int(np.ceil(n_periods / block_size))
    starts = rng.integers(0, n_possible_blocks, size=(n_simulations, n_blocks_needed))
    offsets = np.arange(block_size)
    idx = (starts[:, :, None] + offsets[None, None, :]).reshape(n_simulations, -1)[:, :n_periods]
    return idx

def run_mc(n_sims, n_years, block_size, seed, chunk=20000):
    rng = np.random.default_rng(seed)
    idx = block_bootstrap_indices(n_obs, n_sims, n_years, block_size, rng)  # (n_sims, n_years)

    mkt_b = series["Mkt"][idx]; rf_b = series["RF"][idx]; sv_b = series["SV"][idx]
    bond_b = series["Bond"][idx]; mf_b = series["MF"][idx]; gold_b = series["Gold"][idx]
    lev_b = LEVERAGE * mkt_b - ((LEVERAGE - 1.0) * (rf_b + SPREAD_ANNUAL) + EXPENSE_ANNUAL)

    # Portfolio A: 80% Lev + 20% Gold + 25% Bond + 25% MF (150% total, biennial rebal)
    # Portfolio B: 100% SV + 20% MF + 20% Bond + 10% Gold (150% total, biennial rebal)
    def sim_portfolio(weights_and_series, rf_b, rebalance_years=2):
        """
        NAV/debt tracked explicitly, matching the corrected build_150pct_portfolio
        in portfolios_1_5x.py -- debt is fixed in dollar terms between rebalances
        (sized off NAV at the last rebalance) rather than scaled by drifted gross
        exposure, which had been overcharging financing cost by total_w (1.5x).
        """
        total_w = sum(w for w, _ in weights_and_series)
        excess = total_w - 1.0
        n_sims_, n_years_ = rf_b.shape
        nav = np.ones(n_sims_)
        asset_vals = None
        debt = np.zeros(n_sims_)
        port_ret = np.empty((n_sims_, n_years_))
        for t in range(n_years_):
            if t % rebalance_years == 0:
                asset_vals = [w * nav for w, _ in weights_and_series]
                debt = excess * nav
            nav_start = sum(asset_vals) - debt
            financing_cost = debt * (rf_b[:, t] + SPREAD_ANNUAL)
            pnl = sum(v * ser[:, t] for v, (w, ser) in zip(asset_vals, weights_and_series))
            nav_end = nav_start + pnl - financing_cost
            port_ret[:, t] = nav_end / nav_start - 1.0
            asset_vals = [v * (1 + ser[:, t]) for v, (w, ser) in zip(asset_vals, weights_and_series)]
            nav = nav_end
        return port_ret

    t0 = time.time()
    ret_A = sim_portfolio([(0.80, lev_b), (0.20, gold_b), (0.25, bond_b), (0.25, mf_b)], rf_b)
    ret_B = sim_portfolio([(1.00, sv_b), (0.20, mf_b), (0.20, bond_b), (0.10, gold_b)], rf_b)
    print(f"  MC sim done in {time.time()-t0:.1f}s")

    def path_stats(ret):
        nav = np.cumprod(1 + ret, axis=1)
        final = nav[:, -1]
        ann = final ** (1.0/n_years) - 1.0
        peak = np.maximum.accumulate(nav, axis=1)
        dd = nav/peak - 1.0
        maxdd = dd.min(axis=1)
        return ann, maxdd

    ann_A, dd_A = path_stats(ret_A)
    ann_B, dd_B = path_stats(ret_B)
    return ann_A, dd_A, ann_B, dd_B

print("Running Monte Carlo (100,000 x 25yr, annual block bootstrap, block=2yr)...")
ann_A, dd_A, ann_B, dd_B = run_mc(n_sims=100_000, n_years=25, block_size=2, seed=42)

p_A_beats_B = (ann_A > ann_B).mean() * 100
print(f"\nP(Portfolio A > Portfolio B, 25yr annualized): {p_A_beats_B:.1f}%")

def summary(arr):
    return dict(median=round(float(np.median(arr))*100,2), p5=round(float(np.percentile(arr,5))*100,2),
                p25=round(float(np.percentile(arr,25))*100,2), p75=round(float(np.percentile(arr,75))*100,2),
                p95=round(float(np.percentile(arr,95))*100,2), worst=round(float(arr.min())*100,2),
                best=round(float(arr.max())*100,2))

print(f"Portfolio A: median={np.median(ann_A)*100:.2f}%  p5={np.percentile(ann_A,5)*100:.2f}%  p95={np.percentile(ann_A,95)*100:.2f}%")
print(f"Portfolio B: median={np.median(ann_B)*100:.2f}%  p5={np.percentile(ann_B,5)*100:.2f}%  p95={np.percentile(ann_B,95)*100:.2f}%")
print(f"Portfolio A max DD: median={np.median(dd_A)*100:.1f}%  p5={np.percentile(dd_A,5)*100:.1f}%")
print(f"Portfolio B max DD: median={np.median(dd_B)*100:.1f}%  p5={np.percentile(dd_B,5)*100:.1f}%")

for thr in [0.3,0.4,0.5]:
    print(f"P(DD < -{int(thr*100)}%): A={np.mean(dd_A<-thr)*100:.1f}%  B={np.mean(dd_B<-thr)*100:.1f}%")

OUT["mc"] = dict(
    n_sims=100_000, n_years=25, block_size=2, n_hist_obs=n_obs,
    p_A_beats_B=round(p_A_beats_B,1),
    port_A=summary(ann_A), port_B=summary(ann_B),
    port_A_dd=dict(median=round(float(np.median(dd_A))*100,1), p5=round(float(np.percentile(dd_A,5))*100,1),
                    p_gt30=round(float((dd_A<-0.3).mean())*100,1), p_gt40=round(float((dd_A<-0.4).mean())*100,1), p_gt50=round(float((dd_A<-0.5).mean())*100,1)),
    port_B_dd=dict(median=round(float(np.median(dd_B))*100,1), p5=round(float(np.percentile(dd_B,5))*100,1),
                    p_gt30=round(float((dd_B<-0.3).mean())*100,1), p_gt40=round(float((dd_B<-0.4).mean())*100,1), p_gt50=round(float((dd_B<-0.5).mean())*100,1)),
)

np.save(rf"{SCRATCH}\p15_mc_ann_A.npy", ann_A)
np.save(rf"{SCRATCH}\p15_mc_ann_B.npy", ann_B)
np.save(rf"{SCRATCH}\p15_mc_dd_A.npy", dd_A)
np.save(rf"{SCRATCH}\p15_mc_dd_B.npy", dd_B)

with open(rf"{SCRATCH}\portfolios_summary.json", "w") as f:
    json.dump(OUT, f, indent=2, default=str)
print("\nDone.")
