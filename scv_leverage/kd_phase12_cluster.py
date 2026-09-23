import numpy as np, pandas as pd, json
from kd_data import load_daily, series_frame, SERIES, OUTDIR, write_manifest
df = load_daily(verbose=False)
OUT={}
for key,col in [("mkt","mkt_total"),("scv","scv_total")]:
    # own calendar per series -- scv is absent on the pre-1952 Saturdays
    frame, _apy, _yrs = series_frame(df, key)
    t = frame[col].to_numpy(float)
    nav = np.cumprod(1+t); dd = nav/np.maximum.accumulate(nav)-1
    ob = np.argsort(-t)[:100]; ow = np.argsort(t)[:100]
    rows=[]
    for X in [10,20,50,100]:
        b, w = set(ob[:X].tolist()), set(ow[:X].tolist())
        # best days sitting inside a >20% drawdown
        in_dd = float(np.mean(dd[list(b)] < -0.20))
        # best days within 10 trading days of one of the X worst days
        wa = np.array(sorted(w))
        near = float(np.mean([np.min(np.abs(wa-i))<=10 for i in sorted(b)]))
        # realized vol (21d trailing) on best days vs all days
        vol = pd.Series(t).rolling(21).std().to_numpy()
        vr = float(np.nanmean(vol[list(b)])/np.nanmean(vol))
        rows.append(dict(X=X, pct_in_20pct_drawdown=in_dd, pct_within_10d_of_worst=near, vol_ratio=vr))
        print(f"{key} X={X:<4} best days inside a >20% drawdown: {in_dd*100:5.1f}%   "
              f"within 10 trading days of a worst-{X} day: {near*100:5.1f}%   "
              f"trailing-21d vol vs average: {vr:.2f}x")
    OUT[key]=rows
    yrs = pd.Series(frame.index[ob[:20]].year).value_counts().sort_index()
    print(f"  {key}: years of the 20 best days -> {dict(yrs)}\n")
json.dump(OUT, open(rf"{OUTDIR}\phase12_clustering.json","w"), indent=2)
write_manifest("kd_phase12_cluster.py")
