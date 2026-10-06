"""Evaluate a predictions_YYYY-MM-DD.csv file against what actually happened.

Usage:
    python evaluate_week.py predictions_2026-10-01.csv
Needs at least 5 TASI trading sessions after the forecast date.
"""
import argparse
from dataclasses import dataclass

import numpy as np
import pandas as pd

from tadawul_common import TASI, download, pct

HORIZON = 5
REQUIRED_COLS = {"ticker", "name", "forecast_date", "last_close", "pred_return_5d"}


@dataclass
class Evaluation:
    start: pd.Timestamp
    sessions_elapsed: int
    end: pd.Timestamp | None = None
    preds: pd.DataFrame | None = None  # with actual_return_5d, sorted by prediction
    top_ret: float = np.nan
    bottom_ret: float = np.nan
    all_ret: float = np.nan
    tasi_ret: float = np.nan
    hit_rate: float = np.nan
    hits: int = 0
    n_valid: int = 0

    @property
    def complete(self) -> bool:
        return self.end is not None

    @property
    def top(self):
        return self.preds.head(5)

    @property
    def bottom(self):
        return self.preds.tail(5).iloc[::-1]


def realised_return(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp):
    """Close-to-close return from `start` to the last close on or before `end`."""
    base = df["close"].loc[:start]
    after = df["close"].loc[:end]
    if base.empty or after.empty or base.index[-1] != start:
        return np.nan
    return after.iloc[-1] / base.iloc[-1] - 1


def fetch_actuals(tickers, start: pd.Timestamp) -> dict:
    return download([*tickers, TASI], start=(start - pd.Timedelta(days=10)).date())


def evaluate(preds: pd.DataFrame, data: dict) -> Evaluation:
    missing_cols = REQUIRED_COLS - set(preds.columns)
    if missing_cols:
        raise ValueError(f"ملف التوقعات ينقصه الأعمدة: {', '.join(sorted(missing_cols))}")
    start = pd.Timestamp(preds["forecast_date"].iloc[0])
    tasi = data.get(TASI)
    if tasi is None:
        raise RuntimeError("Could not download TASI (^TASI.SR)")
    sessions = tasi.index[tasi.index > start]
    if len(sessions) < HORIZON:
        return Evaluation(start=start, sessions_elapsed=len(sessions))
    end = sessions[HORIZON - 1]  # 5th actual trading session (accounts for holidays)

    preds = preds.copy()
    preds["actual_return_5d"] = [
        realised_return(data[t], start, end) if t in data else np.nan for t in preds["ticker"]
    ]
    preds = preds.sort_values("pred_return_5d", ascending=False).reset_index(drop=True)
    valid = preds.dropna(subset=["actual_return_5d"])
    hit = np.sign(valid["pred_return_5d"]) == np.sign(valid["actual_return_5d"])
    return Evaluation(
        start=start, sessions_elapsed=len(sessions), end=end, preds=preds,
        top_ret=preds.head(5)["actual_return_5d"].mean(),
        bottom_ret=preds.tail(5)["actual_return_5d"].mean(),
        all_ret=valid["actual_return_5d"].mean(),
        tasi_ret=realised_return(tasi, start, end),
        hit_rate=hit.mean(), hits=int(hit.sum()), n_valid=len(valid),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions", help="path to predictions_YYYY-MM-DD.csv")
    args = ap.parse_args()

    preds = pd.read_csv(args.predictions, encoding="utf-8-sig")
    start = pd.Timestamp(preds["forecast_date"].iloc[0])
    ev = evaluate(preds, fetch_actuals(preds["ticker"], start))
    if not ev.complete:
        raise SystemExit(f"لم تكتمل الفترة بعد: مضى {ev.sessions_elapsed} من {HORIZON} أيام تداول بعد {start.date()}.")

    def table(df):
        return pd.DataFrame({
            "الرمز": df["ticker"].str.replace(".SR", "", regex=False),
            "الشركة": df["name"],
            "المتوقع": df["pred_return_5d"].map(pct),
            "الفعلي": df["actual_return_5d"].map(lambda x: "—" if pd.isna(x) else pct(x)),
            "الاتجاه": [
                "—" if pd.isna(a) else ("✔" if np.sign(p) == np.sign(a) else "✘")
                for p, a in zip(df["pred_return_5d"], df["actual_return_5d"])
            ],
        }).to_string(index=False)

    missing = len(ev.preds) - ev.n_valid
    print(f"فترة التقييم: إغلاق {ev.start.date()} ← إغلاق {ev.end.date()} ({HORIZON} أيام تداول)\n")
    print("▲ أعلى 5 توقعات:")
    print(table(ev.top))
    print("\n▼ أدنى 5 توقعات:")
    print(table(ev.bottom))
    print("\n— مقارنة العوائد (متوسط متساوي الأوزان) —")
    print(f"  أعلى 5 (فعلي):         {pct(ev.top_ret)}   مقابل متوقع {pct(ev.top['pred_return_5d'].mean())}")
    print(f"  أدنى 5 (فعلي):         {pct(ev.bottom_ret)}   مقابل متوقع {pct(ev.bottom['pred_return_5d'].mean())}")
    print(f"  الفرق (أعلى − أدنى):   {pct(ev.top_ret - ev.bottom_ret)}")
    print(f"  كل الأسهم الثلاثين:    {pct(ev.all_ret)}")
    print(f"  مؤشر تاسي:             {pct(ev.tasi_ret)}")
    print(f"\nنسبة صحة الاتجاه (كل الأسهم): {ev.hit_rate * 100:.1f}% ({ev.hits}/{ev.n_valid})"
          + (f"  — {missing} سهم بلا بيانات فعلية" if missing else ""))

    print("\n— الملخص —")
    print(f"• أعلى 5 {'تفوقت' if ev.top_ret > ev.tasi_ret else 'لم تتفوق'} على تاسي بفارق {pct(ev.top_ret - ev.tasi_ret)}.")
    print(f"• أدنى 5 {'كانت أضعف' if ev.bottom_ret < ev.tasi_ret else 'لم تكن أضعف'} من تاسي بفارق {pct(ev.bottom_ret - ev.tasi_ret)}.")
    print(f"• الترتيب {'صحيح' if ev.top_ret > ev.bottom_ret else 'معكوس'}: أعلى 5 {'تفوقت على' if ev.top_ret > ev.bottom_ret else 'تأخرت عن'} أدنى 5 بفارق {pct(ev.top_ret - ev.bottom_ret)}.")
    print(f"• صحة الاتجاه {ev.hit_rate * 100:.0f}% مقابل 50% للتخمين العشوائي.")
    out = args.predictions.replace(".csv", "_evaluated.csv")
    ev.preds.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\nتم حفظ التفاصيل في: {out}")


if __name__ == "__main__":
    main()
