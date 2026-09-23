"""
ff.py -- the one Ken French CSV parser in the suite.

Ken French files are several numeric blocks stacked in one CSV, each preceded
by a column-header line and usually a title line ("Average Value Weighted
Returns -- Daily"). Blocks are found by their titles, never by hard-coded row
numbers, so a re-download that adds rows cannot shift a block boundary.

All returns come back in DECIMAL (the files store percent). Ken French codes
missing data as -99.99 or -999; those become NaN.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

from common import paths

MISSING_AT_OR_BELOW = -0.99          # decimal, i.e. -99% or worse is a missing code


def sections(text: str) -> list[tuple[str, list[str], pd.DataFrame]]:
    """Every numeric block in a Ken French CSV, as (title, columns, frame).

    A block is a run of rows whose first field is all digits. Its columns come
    from the header line right above it; its title is the nearest non-blank
    line above that header that is not itself comma-separated data."""
    lines = text.splitlines()
    out, i = [], 0
    while i < len(lines):
        head = lines[i].split(",")[0].strip()
        if not head.isdigit():
            i += 1
            continue
        start = i
        width = len(lines[i].split(","))
        while i < len(lines):
            p = lines[i].split(",")
            if len(p) != width or not p[0].strip().isdigit() \
                    or len(p[0].strip()) != len(head):
                break
            i += 1
        header = lines[start - 1].split(",") if start > 0 else []
        cols = [c.strip() for c in header[1:]] if len(header) == width \
            else [f"c{k}" for k in range(1, width)]
        title = ""
        for j in range(start - 2, -1, -1):
            s = lines[j].strip()
            if s:
                title = s if "," not in s else ""
                break
        rows = [l.split(",") for l in lines[start:i]]
        df = pd.DataFrame([[float(x) for x in r[1:]] for r in rows], columns=cols,
                          index=[r[0].strip() for r in rows])
        out.append((title, cols, df))
    return out


def _to_decimal(block: pd.DataFrame, datefmt: str) -> pd.DataFrame:
    df = block / 100.0
    df.index = pd.to_datetime(df.index, format=datefmt)
    df.index.name = "date"
    return df.mask(df <= MISSING_AT_OR_BELOW)


def first_daily_block(text: str) -> pd.DataFrame:
    """The first block with 8-digit (YYYYMMDD) dates, in decimal."""
    for _, _, df in sections(text):
        if len(df.index[0]) == 8:
            return _to_decimal(df, "%Y%m%d")
    raise ValueError("no daily block found")


def block_titled(text: str, title_contains: str, datefmt: str = "%Y%m%d") -> pd.DataFrame:
    """The block whose title contains `title_contains` (case-insensitive)."""
    for title, _, df in sections(text):
        if title_contains.lower() in title.lower():
            return _to_decimal(df, datefmt)
    raise KeyError(f"no block titled like {title_contains!r}")


def read_text(path: Path) -> str:
    """A Ken French CSV, plain or zipped."""
    raw = Path(path).read_bytes()
    if raw[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(raw))
        raw = z.read(z.namelist()[0])
    return raw.decode("latin-1")


# --------------------------------------------------------------------------
# the US files the suite ships with
# --------------------------------------------------------------------------
def us_factors_daily() -> pd.DataFrame:
    """US 3-factor daily file. Columns Mkt-RF, SMB, HML, RF (decimal)."""
    return first_daily_block(read_text(paths.FF_US_FACTORS_DAILY))


def us_port6_daily(weighting: str = "value") -> pd.DataFrame:
    """US 6 portfolios (2 ME x 3 BE/ME), daily, decimal.

    `weighting` is "value" or "equal". Column names are the file's own:
    SMALL LoBM, ME1 BM2, SMALL HiBM, BIG LoBM, ME2 BM2, BIG HiBM."""
    title = {"value": "Value Weighted Returns -- Daily",
             "equal": "Equal Weighted Returns -- Daily"}[weighting]
    return block_titled(read_text(paths.FF_US_PORT6_DAILY), title)


def us_small_value_daily() -> pd.Series:
    """US SMALL HiBM (value-weighted), daily total return, missing days dropped."""
    return us_port6_daily("value")["SMALL HiBM"].dropna().rename("scv_total")


def us_market_daily() -> pd.DataFrame:
    """US market: columns mkt_exc, rf, mkt_total (decimal)."""
    f = us_factors_daily().dropna(subset=["Mkt-RF", "RF"])
    out = pd.DataFrame(index=f.index)
    out["mkt_exc"] = f["Mkt-RF"]
    out["rf"] = f["RF"]
    out["mkt_total"] = out["mkt_exc"] + out["rf"]
    return out
