"""Evaluate a predictions_YYYY-MM-DD.csv file against what actually happened.

Usage:
    python evaluate_week.py predictions_2026-10-01.csv
Needs at least 5 TASI trading sessions after the forecast date.
"""
import argparse

import numpy as np
import pandas as pd

from tadawul_common import TASI, download, pct

HORIZON = 5


def realised_return(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp):
    """Close-to-close return from `start` to the last close on or before `end`."""
    base = df["close"].loc[:start]
    after = df["close"].loc[:end]
    if base.empty or after.empty or base.index[-1] != start:
        return np.nan
    return after.iloc[-1] / base.iloc[-1] - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions", help="path to predictions_YYYY-MM-DD.csv")
    args = ap.parse_args()

    preds = pd.read_csv(args.predictions, encoding="utf-8-sig")
    start = pd.Timestamp(preds["forecast_date"].iloc[0])

    data = download([*preds["ticker"], TASI], start=(start - pd.Timedelta(days=10)).date())
    tasi = data.get(TASI)
    if tasi is None:
        raise RuntimeError("Could not download TASI (^TASI.SR)")
    sessions = tasi.index[tasi.index > start]
    if len(sessions) < HORIZON:
        raise SystemExit(f"لم تكتمل الفترة بعد: مضى {len(sessions)} من {HORIZON} أيام تداول بعد {start.date()}.")
    end = sessions[HORIZON - 1]  # 5th actual trading session (accounts for holidays)

    preds["actual_return_5d"] = [
        realised_return(data[t], start, end) if t in data else np.nan for t in preds["ticker"]
    ]
    tasi_ret = realised_return(tasi, start, end)
    missing = preds["actual_return_5d"].isna().sum()

    preds = preds.sort_values("pred_return_5d", ascending=False).reset_index(drop=True)
    top, bottom = preds.head(5), preds.tail(5).iloc[::-1]
    valid = preds.dropna(subset=["actual_return_5d"])
    hit = np.sign(valid["pred_return_5d"]) == np.sign(valid["actual_return_5d"])

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

    top_ret, bot_ret, all_ret = top["actual_return_5d"].mean(), bottom["actual_return_5d"].mean(), valid["actual_return_5d"].mean()
    print(f"فترة التقييم: إغلاق {start.date()} ← إغلاق {end.date()} ({HORIZON} أيام تداول)\n")
    print("▲ أعلى 5 توقعات:")
    print(table(top))
    print("\n▼ أدنى 5 توقعات:")
    print(table(bottom))
    print("\n— مقارنة العوائد (متوسط متساوي الأوزان) —")
    print(f"  أعلى 5 (فعلي):         {pct(top_ret)}   مقابل متوقع {pct(top['pred_return_5d'].mean())}")
    print(f"  أدنى 5 (فعلي):         {pct(bot_ret)}   مقابل متوقع {pct(bottom['pred_return_5d'].mean())}")
    print(f"  الفرق (أعلى − أدنى):   {pct(top_ret - bot_ret)}")
    print(f"  كل الأسهم الثلاثين:    {pct(all_ret)}")
    print(f"  مؤشر تاسي:             {pct(tasi_ret)}")
    print(f"\nنسبة صحة الاتجاه (كل الأسهم): {hit.mean() * 100:.1f}% ({int(hit.sum())}/{len(valid)})"
          + (f"  — {missing} سهم بلا بيانات فعلية" if missing else ""))

    print("\n— الملخص —")
    print(f"• أعلى 5 {'تفوقت' if top_ret > tasi_ret else 'لم تتفوق'} على تاسي بفارق {pct(top_ret - tasi_ret)}.")
    print(f"• أدنى 5 {'كانت أضعف' if bot_ret < tasi_ret else 'لم تكن أضعف'} من تاسي بفارق {pct(bot_ret - tasi_ret)}.")
    print(f"• الترتيب {'صحيح' if top_ret > bot_ret else 'معكوس'}: أعلى 5 {'تفوقت على' if top_ret > bot_ret else 'تأخرت عن'} أدنى 5 بفارق {pct(top_ret - bot_ret)}.")
    print(f"• صحة الاتجاه {hit.mean() * 100:.0f}% مقابل 50% للتخمين العشوائي.")
    out = args.predictions.replace(".csv", "_evaluated.csv")
    preds.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\nتم حفظ التفاصيل في: {out}")


if __name__ == "__main__":
    main()
