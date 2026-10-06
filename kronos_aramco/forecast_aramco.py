"""Backtest Kronos-small on Saudi Aramco (2222.SR) daily OHLCV.

Holds out the last 30 trading days, forecasts them from all prior data,
plots predicted vs. actual close, and prints MAE and directional accuracy.

Usage:
    KRONOS_DIR=/path/to/Kronos python forecast_aramco.py
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yfinance as yf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

KRONOS_DIR = Path(os.environ.get("KRONOS_DIR", Path(__file__).resolve().parents[2] / "Kronos"))
sys.path.insert(0, str(KRONOS_DIR))
from model import Kronos, KronosTokenizer, KronosPredictor  # noqa: E402

TICKER = "2222.SR"
TEST_DAYS = 30
MAX_CONTEXT = 512  # Kronos-small context limit
SAMPLE_COUNT = 5   # average several sampled paths for a steadier forecast
OUT_PNG = Path(__file__).resolve().parent / "aramco_kronos_forecast.png"


def load_data() -> pd.DataFrame:
    raw = yf.download(TICKER, period="2y", interval="1d", auto_adjust=False, progress=False)
    if raw.empty:
        raise RuntimeError(f"No data returned for {TICKER}")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    df = raw.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].copy()
    df = df.dropna()
    df = df[df["volume"] > 0]  # drop non-trading / holiday rows
    df["amount"] = df["volume"] * df[["open", "high", "low", "close"]].mean(axis=1)
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df.reset_index().rename(columns={df.index.name or "index": "timestamps"})
    df = df.rename(columns={"Date": "timestamps"})
    return df


def main():
    torch.manual_seed(42)
    np.random.seed(42)

    df = load_data()
    print(f"Loaded {len(df)} trading days: {df['timestamps'].iloc[0].date()} -> {df['timestamps'].iloc[-1].date()}")

    train, test = df.iloc[:-TEST_DAYS], df.iloc[-TEST_DAYS:]
    context = train.iloc[-MAX_CONTEXT:]
    cols = ["open", "high", "low", "close", "volume", "amount"]

    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    predictor = KronosPredictor(model, tokenizer, device="cpu", max_context=MAX_CONTEXT)

    pred = predictor.predict(
        df=context[cols].reset_index(drop=True),
        x_timestamp=context["timestamps"].reset_index(drop=True),
        y_timestamp=test["timestamps"].reset_index(drop=True),
        pred_len=TEST_DAYS,
        T=1.0,
        top_p=0.9,
        sample_count=SAMPLE_COUNT,
        verbose=False,
    )

    actual = test["close"].to_numpy()
    predicted = pred["close"].to_numpy()
    last_known = train["close"].iloc[-1]

    mae = np.mean(np.abs(predicted - actual))
    mape = np.mean(np.abs(predicted - actual) / actual) * 100
    # Day-over-day direction; first day is compared to the last known close.
    actual_dir = np.sign(np.diff(np.concatenate([[last_known], actual])))
    pred_dir = np.sign(np.diff(np.concatenate([[last_known], predicted])))
    mask = actual_dir != 0  # skip flat days where there is no direction to call
    dir_acc = (actual_dir[mask] == pred_dir[mask]).mean() * 100

    print(f"Context: {len(context)} days, test: {TEST_DAYS} days ({test['timestamps'].iloc[0].date()} -> {test['timestamps'].iloc[-1].date()})")
    print(f"MAE (close): {mae:.4f} SAR  |  MAPE: {mape:.2f}%")
    print(f"Directional accuracy: {dir_acc:.1f}% ({int((actual_dir[mask] == pred_dir[mask]).sum())}/{int(mask.sum())} non-flat days)")
    print(f"Net 30-day move — actual: {actual[-1] - last_known:+.2f} SAR, predicted: {predicted[-1] - last_known:+.2f} SAR")

    hist = train.iloc[-60:]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(hist["timestamps"], hist["close"], color="#888888", lw=1.5, label="History (context)")
    ax.plot(test["timestamps"], actual, color="#1f77b4", lw=2, label="Actual close")
    ax.plot(test["timestamps"], predicted, color="#d62728", lw=2, ls="--", label="Kronos-small forecast")
    ax.axvline(test["timestamps"].iloc[0], color="#bbbbbb", ls=":", lw=1)
    ax.set_title(f"Aramco ({TICKER}) — 30-day close forecast vs actual\nMAE {mae:.3f} SAR · direction accuracy {dir_acc:.0f}%")
    ax.set_ylabel("Close (SAR)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=130)
    print(f"Saved plot: {OUT_PNG}")


if __name__ == "__main__":
    main()
