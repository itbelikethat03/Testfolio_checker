"""
paths.py -- every file location in the suite, relative to the suite folder, so
the folder can be moved or zipped as a unit.
"""
from pathlib import Path

SUITE = Path(__file__).resolve().parent.parent

SHARED = SUITE / "shared_data"
TESTFOLIO_DATA = SHARED / "testfolio_data"
FF_US_FACTORS_DAILY = SHARED / "F-F_Research_Data_Factors_daily.csv"
FF_US_PORT6_DAILY = SHARED / "ff6" / "6_Portfolios_2x3_Daily.csv"
DAMODARAN_XLS = SHARED / "histretSP.xls"

EC = SUITE / "efficient_core"
EC_CACHE = EC / "data_cache"
EC_OUT = EC / "output"

KD = SUITE / "scv_leverage"
KD_OUT = KD / "kelly_bestdays"

TF = SUITE / "testfolio_check"
DASHBOARD = SUITE / "dashboard"
RECON = SUITE / "reconstructions"
RECON_OUT = RECON / "output"
