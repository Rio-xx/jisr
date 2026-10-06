"""Shared helpers for the weekly Tadawul Kronos scripts."""
import os
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

HERE = Path(__file__).resolve().parent
TASI = "^TASI.SR"
# Tadawul trades Sunday–Thursday.
TADAWUL_BDAY = pd.offsets.CustomBusinessDay(weekmask="Sun Mon Tue Wed Thu")

# Candidate universe of large / actively traded TASI names. The 30 most liquid
# are picked at run time by average traded value, so this list only needs to
# be a superset; tickers Yahoo doesn't return are skipped.
UNIVERSE = {
    "2222.SR": "أرامكو السعودية", "1120.SR": "مصرف الراجحي", "1180.SR": "البنك الأهلي",
    "2010.SR": "سابك", "7010.SR": "إس تي سي", "1150.SR": "مصرف الإنماء",
    "1010.SR": "بنك الرياض", "1060.SR": "البنك السعودي الأول", "1140.SR": "بنك البلاد",
    "1080.SR": "البنك العربي الوطني", "1050.SR": "البنك السعودي الفرنسي", "2082.SR": "أكوا باور",
    "1211.SR": "معادن", "2280.SR": "المراعي", "4190.SR": "جرير",
    "2020.SR": "سابك للمغذيات", "2350.SR": "كيان السعودية", "2310.SR": "سبكيم",
    "2290.SR": "ينساب", "4002.SR": "المواساة", "4013.SR": "سليمان الحبيب",
    "4164.SR": "النهدي", "7020.SR": "موبايلي", "7030.SR": "زين السعودية",
    "7203.SR": "علم", "7202.SR": "حلول إس تي سي", "4280.SR": "المملكة القابضة",
    "4300.SR": "دار الأركان", "4030.SR": "البحري", "2380.SR": "بترو رابغ",
    "2060.SR": "التصنيع", "1111.SR": "مجموعة تداول", "2050.SR": "صافولا",
    "3030.SR": "أسمنت السعودية", "1303.SR": "الصناعات الكهربائية", "4263.SR": "سال",
    "2083.SR": "مرافق", "5110.SR": "الكهرباء السعودية", "4200.SR": "الدريس",
    "2223.SR": "لوبريف", "4003.SR": "إكسترا", "1212.SR": "أسترا الصناعية",
    "8210.SR": "بوبا العربية", "8010.SR": "التعاونية", "4007.SR": "الحمادي",
    "1830.SR": "لجام للرياضة", "6004.SR": "كاتريون", "4220.SR": "إعمار المدينة الاقتصادية",
    "4250.SR": "جبل عمر", "4322.SR": "رتال", "4142.SR": "كابلات الرياض",
    "4321.SR": "سينومي سنترز", "4150.SR": "التعمير", "2381.SR": "الحفر العربية",
}


def import_kronos():
    """Import Kronos from $KRONOS_DIR if set, else from the vendored ./model package."""
    sys.path.insert(0, os.environ.get("KRONOS_DIR", str(HERE)))
    from model import Kronos, KronosTokenizer, KronosPredictor
    return Kronos, KronosTokenizer, KronosPredictor


def load_predictor(max_context: int = 512):
    Kronos, KronosTokenizer, KronosPredictor = import_kronos()
    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    return KronosPredictor(model, tokenizer, device="cpu", max_context=max_context)


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=str.lower)
    df = df[[c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]].dropna(subset=["close"])
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df[~df.index.duplicated(keep="last")].sort_index()


def download(tickers, **kwargs) -> dict:
    """Download daily OHLCV for many tickers; returns {ticker: DataFrame}."""
    raw = yf.download(list(tickers), interval="1d", auto_adjust=False, group_by="ticker",
                      progress=False, threads=True, **kwargs)
    out = {}
    for t in tickers:
        if isinstance(raw.columns, pd.MultiIndex):
            if t not in raw.columns.get_level_values(0):
                continue
            df = raw[t]
        else:
            df = raw
        df = _clean(df)
        if not df.empty:
            out[t] = df
    return out


def pct(x: float) -> str:
    return f"{x * 100:+.2f}%"
