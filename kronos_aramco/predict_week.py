"""Forecast the next 5 Tadawul trading days for the 30 most liquid stocks with Kronos-small.

Usage:
    python predict_week.py [--out-dir DIR]
Writes predictions_YYYY-MM-DD.csv (date = last available trading day).
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from tadawul_common import TADAWUL_BDAY, TASI, UNIVERSE, download, load_predictor, pct

N_STOCKS = 30
HORIZON = 5
SAMPLE_COUNT = 5
MAX_CONTEXT = 512
LIQUIDITY_WINDOW = 60  # trading days used to rank by average traded value
MIN_HISTORY = 120
COLS = ["open", "high", "low", "close", "volume", "amount"]


def fetch_market() -> dict:
    return download([*UNIVERSE, TASI], period="3y")


def prepare(data: dict):
    """Split TASI out, keep tradable stocks, and rank them by liquidity.

    Returns (tasi, stocks, top_tickers, liquidity).
    """
    data = dict(data)
    tasi = data.pop(TASI, None)
    if tasi is None:
        raise RuntimeError("Could not download TASI (^TASI.SR)")
    last_date = tasi.index[-1]
    stocks = {}
    for t, df in data.items():
        df = df[df["volume"] > 0]
        if len(df) >= MIN_HISTORY and df.index[-1] == last_date:
            stocks[t] = df.assign(amount=df["volume"] * df[["open", "high", "low", "close"]].mean(axis=1))
    liquidity = pd.Series({t: df["amount"].iloc[-LIQUIDITY_WINDOW:].mean() for t, df in stocks.items()}, dtype=float)
    top = list(liquidity.sort_values(ascending=False).index[:N_STOCKS])
    return tasi, stocks, top, liquidity


def forecast(predictor, tasi, stocks, tickers, liquidity, progress=None) -> pd.DataFrame:
    """Forecast HORIZON sessions for each ticker; returns predictions sorted by expected return.

    `progress(i, n, ticker)` is called after each stock if given.
    """
    torch.manual_seed(42)
    np.random.seed(42)
    last_date = tasi.index[-1]
    future_dates = pd.date_range(last_date + TADAWUL_BDAY, periods=HORIZON, freq=TADAWUL_BDAY)
    rows = []
    for i, t in enumerate(tickers, 1):
        ctx = stocks[t].iloc[-MAX_CONTEXT:]
        pred = predictor.predict(
            df=ctx[COLS].reset_index(drop=True),
            x_timestamp=pd.Series(ctx.index),
            y_timestamp=pd.Series(future_dates),
            pred_len=HORIZON, T=1.0, top_p=0.9, sample_count=SAMPLE_COUNT, verbose=False,
        )
        last_close = ctx["close"].iloc[-1]
        row = {
            "ticker": t, "name": UNIVERSE.get(t, t), "forecast_date": last_date.date(),
            "last_close": round(last_close, 4), "avg_traded_value": round(liquidity[t]),
        }
        for d, (dt, c) in enumerate(zip(future_dates, pred["close"]), 1):
            row[f"date_d{d}"] = dt.date()
            row[f"pred_close_d{d}"] = round(float(c), 4)
        row["pred_return_5d"] = row[f"pred_close_d{HORIZON}"] / last_close - 1
        rows.append(row)
        if progress:
            progress(i, len(tickers), t)

    out = pd.DataFrame(rows).sort_values("pred_return_5d", ascending=False).reset_index(drop=True)
    out["rank"] = np.arange(1, len(out) + 1)
    out.insert(0, "tasi_last_close", round(tasi["close"].iloc[-1], 2))
    return out


def predicted_path(row: pd.Series) -> pd.Series:
    """The 5 forecast closes of one predictions row, indexed by date."""
    return pd.Series(
        [row[f"pred_close_d{d}"] for d in range(1, HORIZON + 1)],
        index=pd.to_datetime([row[f"date_d{d}"] for d in range(1, HORIZON + 1)]),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=Path(__file__).resolve().parent, type=Path)
    args = ap.parse_args()

    tasi, stocks, top, liquidity = prepare(fetch_market())
    last_date = tasi.index[-1]
    print(f"آخر يوم تداول متاح (تاسي): {last_date.date()}  |  إغلاق تاسي: {tasi['close'].iloc[-1]:,.2f}")
    print(f"تم اختيار {len(top)} سهمًا الأعلى سيولة من أصل {len(stocks)} سهمًا متاحًا.")

    predictor = load_predictor(MAX_CONTEXT)
    out = forecast(
        predictor, tasi, stocks, top, liquidity,
        progress=lambda i, n, t: print(f"  [{i:2d}/{n}] {t}"),
    )
    path = args.out_dir / f"predictions_{last_date.date()}.csv"
    out.to_csv(path, index=False, encoding="utf-8-sig")

    end_date = out[f"date_d{HORIZON}"].iloc[0]

    def table(df):
        return pd.DataFrame({
            "الرمز": df["ticker"].str.replace(".SR", "", regex=False),
            "الشركة": df["name"],
            "آخر إغلاق": df["last_close"].map("{:,.2f}".format),
            f"الإغلاق المتوقع ({end_date})": df[f"pred_close_d{HORIZON}"].map("{:,.2f}".format),
            "العائد المتوقع": df["pred_return_5d"].map(pct),
        }).to_string(index=False)

    print(f"\nفترة التوقع: {out['date_d1'].iloc[0]} ← {end_date} (5 أيام تداول)")
    print("\n▲ أعلى 5 أسهم في العائد المتوقع:")
    print(table(out.head(5)))
    print("\n▼ أدنى 5 أسهم في العائد المتوقع:")
    print(table(out.tail(5).iloc[::-1]))
    print(f"\nمتوسط العائد المتوقع للأسهم الثلاثين: {pct(out['pred_return_5d'].mean())}  |  "
          f"عدد الأسهم المتوقع صعودها: {(out['pred_return_5d'] > 0).sum()}/{len(out)}")
    print(f"تم الحفظ في: {path}")


if __name__ == "__main__":
    main()
