"""
tf_load.py -- content-addressed loader for the testfolio daily series.

The download folder contains a collision: three files share one MD5, because a
browser re-download reused a name. `FFSCV_daily.csv` and `VTSIM_L2_daily.csv`
are both stale copies of NTSDSIM; the `(1)` suffixed files are the real ones.

So this loader does NOT trust filenames. Every series is identified by its
content -- start date and ending value must match the expected row of the
testfolio summary table before the series is returned. A future re-download
collision fails loudly here instead of silently poisoning a comparison.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "shared_data" / "testfolio_data"

START_VALUE = 10_000.0

# The testfolio summary table, transcribed. This is the contract every loaded
# series is checked against -- it is reference data, not a computed result.
EXPECTED = {
    "NTSDSIM": dict(
        label="NTSDSIM", start="1969-12-31", end="2026-09-09", years=56.7,
        ending_value=6_189_175, cum_return=617.9175, cagr=0.1201,
        max_dd=-0.7441, avg_dd=-0.1583, longest_dd_y=6.62, vol=0.2456,
        sharpe=0.40, sortino=0.57, calmar=0.16, ulcer=21.49, upi=0.46, beta=1.34,
    ),
    "VTSIM_L2": dict(
        label="VTSIM?L=2", start="1969-12-31", end="2026-09-09", years=56.7,
        ending_value=3_107_211, cum_return=309.7211, cagr=0.1065,
        max_dd=-0.8681, avg_dd=-0.2627, longest_dd_y=9.54, vol=0.3281,
        sharpe=0.34, sortino=0.48, calmar=0.12, ulcer=32.65, upi=0.34, beta=1.65,
    ),
    "FFSCV": dict(
        label="FFSCV", start="1926-07-01", end="2025-10-31", years=99.3,
        ending_value=1_786_967_536, cum_return=178_695.7536, cagr=0.1295,
        max_dd=-0.8780, avg_dd=-0.1406, longest_dd_y=7.30, vol=0.1983,
        sharpe=0.55, sortino=0.78, calmar=0.15, ulcer=21.21, upi=0.51, beta=0.94,
    ),
    "DBMFSIM": dict(
        label="DBMFSIM", start="2000-01-03", end="2026-09-09", years=26.7,
        ending_value=57_376, cum_return=4.7376, cagr=0.0677,
        max_dd=-0.2044, avg_dd=-0.0532, longest_dd_y=3.32, vol=0.0958,
        sharpe=0.53, sortino=0.74, calmar=0.33, ulcer=6.37, upi=0.80, beta=0.01,
    ),
    "TLTSIM": dict(
        label="TLTSIM", start="1962-01-02", end="2026-09-09", years=64.7,
        ending_value=349_096, cum_return=33.9096, cagr=0.0565,
        max_dd=-0.4835, avg_dd=-0.0941, longest_dd_y=6.10, vol=0.1153,
        sharpe=0.15, sortino=0.21, calmar=0.12, ulcer=13.37, upi=0.13, beta=-0.04,
    ),
}

# Ending value must match to the dollar; the table is rounded to whole dollars.
ENDING_TOL = 1.0


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _read(p: Path) -> pd.Series:
    df = pd.read_csv(p, parse_dates=["date"])
    if list(df.columns) != ["date", "value"]:
        raise ValueError(f"{p.name}: unexpected columns {list(df.columns)}")
    s = df.set_index("date")["value"].sort_index()
    if s.isna().any():
        raise ValueError(f"{p.name}: contains NaN values")
    return s


def _matches(s: pd.Series, exp: dict) -> bool:
    return (str(s.index[0].date()) == exp["start"]
            and str(s.index[-1].date()) == exp["end"]
            and abs(s.iloc[-1] - exp["ending_value"]) <= ENDING_TOL)


def load_all(verbose: bool = True) -> dict[str, pd.Series]:
    """Map every expected ticker to its series, identified by content.

    Raises if a ticker cannot be found, or if two distinct files both claim it."""
    files = sorted(DATA.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"no CSVs in {DATA}")

    series = {p: _read(p) for p in files}
    hashes = {p: _md5(p) for p in files}

    out: dict[str, pd.Series] = {}
    claimed: dict[str, list[Path]] = {}

    for tic, exp in EXPECTED.items():
        hits = [p for p, s in series.items() if _matches(s, exp)]
        if not hits:
            raise ValueError(
                f"{tic}: no file matches start={exp['start']} end={exp['end']} "
                f"ending_value={exp['ending_value']:,}")
        # Several files may be byte-identical copies of the same series; that is
        # the known collision and is fine. Two DIFFERENT files claiming the same
        # ticker is not.
        distinct = {hashes[p] for p in hits}
        if len(distinct) > 1:
            raise ValueError(f"{tic}: {len(distinct)} different files claim it: "
                             + ", ".join(p.name for p in hits))
        # Among identical copies, prefer the one actually named for this ticker,
        # purely so the log reads sensibly.
        hits.sort(key=lambda p: (not p.name.upper().startswith(tic), p.name))
        out[tic] = series[hits[0]]
        claimed[tic] = hits

    if verbose:
        print(f"[tf_load] {DATA}")
        used, unused = set(), []
        for tic, hits in claimed.items():
            used.add(hashes[hits[0]])
            s = out[tic]
            print(f"  {EXPECTED[tic]['label']:<12} {hits[0].name:<26} "
                  f"n={len(s):>6,}  {s.index[0].date()} -> {s.index[-1].date()}  "
                  f"${s.iloc[-1]:,.2f}")
            for extra in hits[1:]:
                print(f"    (duplicate, ignored: {extra.name})")
        for p in files:
            if not any(p in h for h in claimed.values()):
                unused.append(p)
        for p in unused:
            dup_of = next((t for t, h in claimed.items()
                           if hashes[h[0]] == hashes[p]), None)
            stem = p.stem.replace("_daily", "")
            note = (f"stale duplicate of {EXPECTED[dup_of]['label']}" if dup_of
                    else "loaded separately (load_letf_sims)" if stem in LETF_SIMS
                    else "used by efficient_core/ec_ntsd.py" if stem == "VEASIM"
                    else "UNRECOGNISED")
            print(f"  [skipped] {p.name:<26} {note}")

    return out


# Leveraged-ETF simulations. Kept out of EXPECTED because no testfolio summary
# table was transcribed for them (tf_verify.py needs one for every ticker there);
# they are identified by content the same way.
LETF_SIMS = {
    "SSOSIM": dict(L=2.0, start="1885-03-20", end="2026-09-22",
                   ending_value=27_546_785_293.12),
    "UPROSIM": dict(L=3.0, start="1885-03-20", end="2026-09-22",
                    ending_value=3_645_537_953.15),
}


def load_letf_sims() -> dict[str, pd.Series]:
    """testfolio's SSOSIM / UPROSIM daily $ paths, verified by content."""
    out = {}
    for tic, exp in LETF_SIMS.items():
        p = DATA / f"{tic}_daily.csv"
        s = _read(p)
        if not _matches(s, exp):
            raise ValueError(f"{p.name} is not the expected {tic}: "
                             f"{s.index[0].date()}..{s.index[-1].date()} ${s.iloc[-1]:,.2f}")
        out[tic] = s
    return out


def returns(s: pd.Series) -> pd.Series:
    """Daily simple returns from the dollar path."""
    return s.pct_change().dropna()


if __name__ == "__main__":
    load_all()
