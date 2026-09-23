"""
ec_data.py -- data layer for the WisdomTree Global Efficient Core (90/60) study.

Every series here is downloaded from a PRIMARY source and cached to disk as CSV,
so the whole analysis is reproducible and the provenance of each number is
explicit.  Nothing in this project uses hand-typed return numbers.

SOURCES
-------
Equities (total return, dividends reinvested, USD)
    Ken French "Developed" 3-factor daily/monthly file
        -> Mkt-RF + RF = cap-weighted TOTAL return of developed-market equities
           in USD.  Proxy for the NTSG equity sleeve (top-1500 developed-market
           large caps, free-float cap weighted).  Available 1990-07-02 onwards.
    Ken French "Developed 6 Portfolios ME x BE/ME" daily
        -> SMALL HiBM = global developed small-cap value (total return, USD).
    Ken French US 3-factor daily (file already in the repo root)
        -> US market total return + RF (1-month T-bill), 1926 onwards.
    Ken French US 6 Portfolios (file already in SCV_leverage_analysis/ff6)
        -> US SMALL HiBM, the small-cap-value series the rest of this repo uses.
    yfinance -> URTH / ACWI / VT / IWDA.L for cross-checks and for the
       "All World" market reference.

Government bond curves (for synthetic constant-maturity bond futures)
    US  : FRED DGS2/DGS5/DGS10/DGS30 + DTB3        (daily, 1962+)
    EUR : ECB Data Portal, euro-area AAA spot curve (daily, 2004-09+)
    GBP : Bank of England IADB par yields + Bank Rate (daily, 1990+)
    JPY : Japan MoF published JGB yield curve       (daily, 1974+)
    Monthly fallback for EUR/GBP/JPY before the daily curves start:
          FRED OECD long-term (10y) and 3-month rates.

Live funds (to validate the reconstruction)
    NTSG.L  WisdomTree Global Efficient Core UCITS ETF, USD line, 2024-11-08+
    NTSX    WisdomTree U.S. Efficient Core Fund,             2018-08-02+
    NTSI    WisdomTree International Efficient Core Fund,    2021-05-21+

FX
    FRED DEXUSEU / DEXUSUK / DEXJPUS (daily).

Long-run US lab
    histretSP.xls (Damodaran) already in SCV_leverage_analysis/ -- annual
    S&P 500 / 10y T-bond / 3m T-bill total returns, 1928+.
"""
from __future__ import annotations

import io
import os
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # the suite root
from common import ff, manifest, paths                            # noqa: E402

PROJ = str(paths.EC)
SHARED = str(paths.SHARED)
CACHE = str(paths.EC_CACHE)
OUT = str(paths.EC_OUT)

FF_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

for _d in (CACHE, OUT, rf"{OUT}\charts"):
    os.makedirs(_d, exist_ok=True)

# The modelling choices every Efficient Core output depends on. Bump a value
# when a choice changes, so common/manifest.py can tell stale outputs apart.
EC_CONFIG = dict(us_3m_basis="bond-equivalent", coupons="usd/gbp/jpy semi-annual",
                 lev15_financing="fed funds + futures spread", engine="common.backtest",
                 equity_futures_financing="fed funds + spread")


def write_manifest(script: str, **extra) -> None:
    manifest.record(OUT, script, **EC_CONFIG, **extra)


# --------------------------------------------------------------------------
# low-level fetch helpers (all cached)
# --------------------------------------------------------------------------
def _fetch(url: str, timeout: int = 180, tries: int = 4, ua: bool = True) -> bytes:
    """`ua=False` sends the stock urllib agent -- FRED rejects browser agents,
    while the BoE / MoF / Dartmouth endpoints require one."""
    headers = UA if ua else {}
    last = None
    for k in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers=headers), timeout=timeout).read()
        except Exception as exc:            # transient DNS / TLS / read timeouts
            last = exc
            print(f"    [retry {k + 1}/{tries}] {type(exc).__name__} on {url[:70]}")
            time.sleep(3 * (k + 1))
    raise last


def _cached(name: str, builder, force: bool = False) -> pd.DataFrame:
    """Run `builder()` once and cache the resulting frame to data_cache/<name>."""
    path = rf"{CACHE}\{name}"
    if os.path.exists(path) and not force:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return df
    df = builder()
    df.to_csv(path)
    return df


# --------------------------------------------------------------------------
# FRED
# --------------------------------------------------------------------------
def fred(series_id: str, force: bool = False) -> pd.Series:
    """One FRED series.  FRED throttles bursts, so we pause between pulls and
    fall back to the plain-text endpoint if the CSV one resets the connection."""
    def build():
        time.sleep(1)
        raw = _fetch(
            f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
            ua=False)
        d = pd.read_csv(io.BytesIO(raw))
        d.columns = ["date", series_id]
        d["date"] = pd.to_datetime(d["date"])
        d[series_id] = pd.to_numeric(d[series_id], errors="coerce")
        return d.set_index("date")

    return _cached(f"fred_{series_id}.csv", build, force)[series_id]


# --------------------------------------------------------------------------
# Ken French
# --------------------------------------------------------------------------
def ff_text(zipname: str) -> str:
    """A Ken French zip from the data library, downloaded once and cached."""
    path = paths.EC_CACHE / zipname
    if not path.exists():
        path.write_bytes(_fetch(FF_BASE + zipname, timeout=300))
    return ff.read_text(path)


def _ff_daily(zipname: str, columns: list[str]) -> pd.DataFrame:
    d = ff.first_daily_block(ff_text(zipname))
    d.columns = columns
    return d


def load_ff_developed_daily(force: bool = False) -> pd.DataFrame:
    """Developed-market equities, daily, USD, decimal.
    Columns: dm_exc (excess), rf (USD 1m T-bill), dm_total (total return)."""
    def build():
        d = _ff_daily("Developed_3_Factors_Daily_CSV.zip", ["Mkt-RF", "SMB", "HML", "RF"])
        out = pd.DataFrame(index=d.index)
        out["dm_exc"] = d["Mkt-RF"]
        out["rf"] = d["RF"]
        out["dm_total"] = out["dm_exc"] + out["rf"]
        return out

    return _cached("ff_developed_daily.csv", build, force)


def load_ff_developed_ex_us_daily() -> pd.DataFrame:
    """Developed ex-US equities, daily, USD, decimal. Columns: exus_total, rf."""
    d = _ff_daily("Developed_ex_US_3_Factors_Daily_CSV.zip", ["Mkt-RF", "SMB", "HML", "RF"])
    return pd.DataFrame({"exus_total": d["Mkt-RF"] + d["RF"], "rf": d["RF"]})


def load_ff_developed_scv_daily(force: bool = False) -> pd.DataFrame:
    """Global developed SMALL-cap VALUE (SMALL HiBM), daily total return, USD."""
    def build():
        d = _ff_daily("Developed_6_Portfolios_ME_BE-ME_Daily_CSV.zip",
                      ["SMALL_LoBM", "SMALL_BM2", "SMALL_HiBM",
                       "BIG_LoBM", "BIG_BM2", "BIG_HiBM"])
        return d[["SMALL_HiBM"]].rename(columns={"SMALL_HiBM": "dm_scv_total"}).dropna()

    return _cached("ff_developed_scv_daily.csv", build, force)


def load_ff_us_daily() -> pd.DataFrame:
    """US market + RF, daily, decimal (common.ff, shared with kd_data.py)."""
    m = ff.us_market_daily()
    return pd.DataFrame({"us_exc": m["mkt_exc"], "rf": m["rf"], "us_total": m["mkt_total"]})


def load_ff_us_scv_daily() -> pd.DataFrame:
    """US SMALL HiBM daily total return (common.ff, shared with kd_data.py)."""
    return ff.us_small_value_daily().rename("us_scv_total").to_frame()


# --------------------------------------------------------------------------
# Yield curves
# --------------------------------------------------------------------------
def bill_discount_to_bey(d: pd.Series, days: int = 91) -> pd.Series:
    """T-bill DISCOUNT yield (how FRED's DTB3 is quoted) -> bond-equivalent
    yield, the basis the DGS par yields and money-market rates use.
    BEY = 365 d / (360 - d t). At a 5% discount rate the BEY is ~5.13%."""
    return 365.0 * d / (360.0 - d * days)


def load_us_curve(force: bool = False) -> pd.DataFrame:
    """US Treasury constant-maturity par yields + 3m bill, daily, decimal.
    `us_3m` is converted from DTB3's discount basis to bond-equivalent, so the
    whole curve (and every financing leg that uses it) is on one basis."""
    def build():
        cols = {"DTB3": "us_3m", "DGS2": "us_2y", "DGS5": "us_5y",
                "DGS10": "us_10y", "DGS30": "us_30y"}
        d = pd.DataFrame({v: fred(k) for k, v in cols.items()})
        return d / 100.0

    c = _cached("curve_us.csv", build, force)       # cache holds the raw quotes
    c["us_3m"] = bill_discount_to_bey(c["us_3m"])
    return c


def load_eur_curve(force: bool = False) -> pd.DataFrame:
    """Euro-area AAA government spot curve from the ECB Data Portal, daily."""
    def build():
        out = {}
        for tenor, col in [("SR_3M", "eur_3m"), ("SR_2Y", "eur_2y"),
                           ("SR_5Y", "eur_5y"), ("SR_10Y", "eur_10y"),
                           ("SR_30Y", "eur_30y")]:
            url = ("https://data-api.ecb.europa.eu/service/data/YC/"
                   f"B.U2.EUR.4F.G_N_A.SV_C_YM.{tenor}?format=csvdata&detail=dataonly")
            d = pd.read_csv(io.BytesIO(_fetch(url, 300)))
            s = pd.Series(d["OBS_VALUE"].values,
                          index=pd.to_datetime(d["TIME_PERIOD"]))
            out[col] = s[~s.index.duplicated()]
        return pd.DataFrame(out) / 100.0

    return _cached("curve_eur.csv", build, force)


def load_gbp_curve(force: bool = False) -> pd.DataFrame:
    """UK gilt nominal par yields (5y/10y/20y) + Bank Rate, daily, from the
    Bank of England Interactive Database."""
    def build():
        url = ("https://www.bankofengland.co.uk/boeapps/iadb/fromshowcolumns.asp?"
               "csv.x=yes&Datefrom=01/Jan/1970&Dateto=31/Dec/2026"
               "&SeriesCodes=IUDSNPY,IUDMNPY,IUDLNPY,IUDBEDR"
               "&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N")
        d = pd.read_csv(io.BytesIO(_fetch(url, 300)))
        d.columns = ["date", "gbp_5y", "gbp_10y", "gbp_20y", "gbp_on"]
        d["date"] = pd.to_datetime(d["date"], format="%d %b %Y")
        return d.set_index("date").apply(pd.to_numeric, errors="coerce") / 100.0

    return _cached("curve_gbp.csv", build, force)


def load_jpy_curve(force: bool = False) -> pd.DataFrame:
    """JGB yield curve published daily by the Japanese Ministry of Finance."""
    def build():
        url = ("https://www.mof.go.jp/english/policy/jgbs/reference/"
               "interest_rate/historical/jgbcme_all.csv")
        txt = _fetch(url, 300).decode("latin-1")
        d = pd.read_csv(io.StringIO(txt), skiprows=1)
        d = d.rename(columns={d.columns[0]: "date"})
        d["date"] = pd.to_datetime(d["date"], format="%Y/%m/%d", errors="coerce")
        d = d.dropna(subset=["date"]).set_index("date")
        keep = {"1Y": "jpy_1y", "2Y": "jpy_2y", "5Y": "jpy_5y",
                "10Y": "jpy_10y", "30Y": "jpy_30y"}
        d = d[[c for c in keep if c in d.columns]].rename(columns=keep)
        return d.apply(pd.to_numeric, errors="coerce") / 100.0

    return _cached("curve_jpy.csv", build, force)


def load_fx(force: bool = False) -> pd.DataFrame:
    """USD per unit of foreign currency, daily."""
    def build():
        eur = fred("DEXUSEU")           # USD per EUR
        gbp = fred("DEXUSUK")           # USD per GBP
        jpy = 1.0 / fred("DEXJPUS")     # DEXJPUS is JPY per USD
        return pd.DataFrame({"usd_per_eur": eur, "usd_per_gbp": gbp,
                             "usd_per_jpy": jpy})

    return _cached("fx.csv", build, force)


# --------------------------------------------------------------------------
# ETFs / live funds
# --------------------------------------------------------------------------
def load_prices(tickers, start="1990-01-01", force: bool = False) -> pd.DataFrame:
    """Split- and dividend-adjusted closes (total-return basis) from Yahoo."""
    key = "prices_" + "_".join(t.replace(".", "").replace("^", "") for t in tickers)

    def build():
        import yfinance as yf
        px = yf.download(list(tickers), start=start, progress=False,
                         auto_adjust=True, threads=False)["Close"]
        if isinstance(px, pd.Series):
            px = px.to_frame(tickers[0])
        return px[list(tickers)]

    return _cached(f"{key}.csv", build, force)


# --------------------------------------------------------------------------
# Long-run US annual lab (Damodaran)
# --------------------------------------------------------------------------
def load_damodaran_annual() -> pd.DataFrame:
    """Annual US total returns 1928+: S&P 500, 10y T-bond, 3m T-bill."""
    raw = pd.read_excel(paths.DAMODARAN_XLS, sheet_name="Returns by year",
                        skiprows=19, engine="xlrd")
    raw = raw.rename(columns={raw.columns[0]: "year"})
    cols = {c: str(c).strip() for c in raw.columns}
    raw = raw.rename(columns=cols)

    def pick(*keys):
        for c in raw.columns:
            lc = str(c).lower()
            if all(k in lc for k in keys):
                return c
        raise KeyError(keys)

    out = pd.DataFrame()
    out["year"] = pd.to_numeric(raw["year"], errors="coerce")
    out["stocks"] = pd.to_numeric(raw[pick("s&p 500")], errors="coerce")
    out["bills"] = pd.to_numeric(raw[pick("3-month t.bill")], errors="coerce")
    out["bonds"] = pd.to_numeric(raw[pick("us t. bond")], errors="coerce")
    out = out.dropna(subset=["year", "stocks", "bonds", "bills"])
    out["year"] = out["year"].astype(int)
    return out.set_index("year")


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    print("Downloading / loading every series ...\n")
    checks = [
        ("FF developed daily", load_ff_developed_daily()),
        ("FF developed SCV daily", load_ff_developed_scv_daily()),
        ("FF US daily", load_ff_us_daily()),
        ("FF US SCV daily", load_ff_us_scv_daily()),
        ("US curve", load_us_curve()),
        ("EUR curve", load_eur_curve()),
        ("GBP curve", load_gbp_curve()),
        ("JPY curve", load_jpy_curve()),
        ("FX", load_fx()),
    ]
    for name, d in checks:
        print(f"{name:26s} n={len(d):7,d}  {d.index.min().date()} -> "
              f"{d.index.max().date()}  cols={list(d.columns)}")

    px = load_prices(["NTSG.L", "NTSX", "NTSI", "URTH", "ACWI", "VT",
                      "IEF", "SHY", "TLT", "IEI"])
    print("\nPrices:")
    for c in px.columns:
        s = px[c].dropna()
        print(f"  {c:8s} n={len(s):6,d}  {s.index.min().date()} -> {s.index.max().date()}")

    dam = load_damodaran_annual()
    print(f"\nDamodaran annual: {dam.index.min()} -> {dam.index.max()}, n={len(dam)}")
    print(dam.tail(3))
