"""Streamlit app: weekly Kronos-small forecasts for the 30 most liquid Tadawul stocks.

Run locally:  streamlit run app.py
"""
import html

import altair as alt
import pandas as pd
import streamlit as st

import evaluate_week as ev_mod
import predict_week as pw
from tadawul_common import load_predictor

st.set_page_config(page_title="توقعات تداول الأسبوعية", page_icon="📈", layout="centered")

UP, DOWN = "#1a9e4b", "#e03b3b"           # return colors (always paired with sign + arrow)
ACTUAL, FORECAST = "#2a78d6", "#eb6834"   # chart series: reference palette slots 1–2

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap');
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp button, .stApp h1, .stApp h2,
.stApp h3, .stApp td, .stApp th, [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {{
  font-family: 'Tajawal', sans-serif !important;
}}
[data-testid="stMain"], [data-testid="stHeader"], [data-testid="stFileUploader"] {{ direction: rtl; }}
[data-testid="stMain"] .stMarkdown, [data-testid="stMain"] h1, [data-testid="stMain"] h2,
[data-testid="stMain"] h3, [data-testid="stCaptionContainer"] {{ text-align: right; }}
[data-testid="stMainBlockContainer"] {{ padding-top: 3.5rem; padding-bottom: 5rem; }}
[data-testid="stMetricValue"] {{ font-size: 2.1rem; font-weight: 800; direction: ltr; text-align: right; }}
[data-testid="stMetricDelta"] {{ justify-content: flex-end; }}
[data-testid="stMetricDelta"], [data-testid="stMetricDelta"] * {{ direction: ltr !important; unicode-bidi: embed; }}
.num {{ direction: ltr; unicode-bidi: isolate; white-space: nowrap; }}
.rtable {{ width: 100%; border-collapse: collapse; direction: rtl; font-size: .95rem; margin-bottom: .5rem; }}
.rtable th {{ text-align: right; font-weight: 500; opacity: .7; padding: .45rem .4rem;
  border-bottom: 1px solid rgba(128,128,128,.35); }}
.rtable td {{ text-align: right; padding: .5rem .4rem; border-bottom: 1px solid rgba(128,128,128,.15); }}
.rtable td.co {{ font-weight: 700; }}
.rtable td.co small {{ display: block; font-weight: 400; opacity: .6; }}
.pos {{ color: {UP}; font-weight: 700; }}
.neg {{ color: {DOWN}; font-weight: 700; }}
.legend {{ display: flex; gap: 1.2rem; font-size: .85rem; margin: -.4rem 0 .6rem; }}
.legend i {{ display: inline-block; width: 22px; height: 2px; vertical-align: middle; margin-left: .4rem; }}
.legend i.dash {{ height: 0; border-top: 2px dashed; }}
.disclaimer {{ position: fixed; bottom: 0; left: 0; right: 0; z-index: 1000; direction: rtl;
  text-align: center; font-size: .78rem; padding: .35rem .75rem;
  background: rgba(250, 204, 21, .92); color: #3b2f00; font-family: 'Tajawal', sans-serif; }}
</style>
<div class="disclaimer">⚠️ تجربة شخصية — ليست توصية استثمارية</div>
""",
    unsafe_allow_html=True,
)


# ---------- cached resources ----------

@st.cache_resource(show_spinner="جارٍ تحميل نموذج Kronos-small…")
def get_predictor():
    return load_predictor(pw.MAX_CONTEXT)


@st.cache_resource
def forecast_store() -> dict:
    """Forecasts shared across sessions, keyed by the last trading date."""
    return {}


@st.cache_data(ttl=3600, show_spinner="جارٍ تحميل أسعار السوق…")
def get_market():
    return pw.fetch_market()


@st.cache_data(ttl=1800, show_spinner="جارٍ تحميل الأسعار الفعلية…")
def get_actuals(tickers: tuple, start: str):
    return ev_mod.fetch_actuals(list(tickers), pd.Timestamp(start))


# ---------- helpers ----------

def fmt_ret(x: float) -> str:
    if pd.isna(x):
        return '<span class="num">—</span>'
    cls, arrow = ("pos", "▲") if x > 0 else ("neg", "▼") if x < 0 else ("", "")
    return f'<span class="num {cls}">{arrow} {x * 100:+.2f}%</span>'


def fmt_px(x: float) -> str:
    return f'<span class="num">{x:,.2f}</span>'


def returns_table(df: pd.DataFrame, columns: list[tuple[str, callable]]) -> str:
    head = "".join(f"<th>{h}</th>" for h, _ in columns)
    body = "".join("<tr>" + "".join(f"<td{' class=co' if i == 0 else ''}>{fn(r)}</td>"
                                    for i, (_, fn) in enumerate(columns)) + "</tr>"
                   for _, r in df.iterrows())
    return f'<table class="rtable"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def company(r) -> str:
    return f"{html.escape(str(r['name']))}<small class='num'>{html.escape(str(r['ticker']).replace('.SR', ''))}</small>"


def stock_chart(hist: pd.Series, row: pd.Series) -> alt.Chart:
    actual_lbl, fc_lbl = "فعلي (آخر 60 يومًا)", "متوقع (5 أيام)"
    path = pw.predicted_path(row)
    fc = pd.concat([hist.iloc[-1:], path])  # join the forecast to the last real close
    data = pd.concat([
        pd.DataFrame({"date": hist.index, "close": hist.values, "series": actual_lbl}),
        pd.DataFrame({"date": fc.index, "close": fc.values, "series": fc_lbl}),
    ])
    color = alt.Color("series:N", title=None,
                      scale=alt.Scale(domain=[actual_lbl, fc_lbl], range=[ACTUAL, FORECAST]),
                      legend=None)  # an HTML legend above the charts renders Arabic correctly
    base = alt.Chart(data).encode(
        x=alt.X("date:T", title=None, axis=alt.Axis(format="%d/%m", grid=False, labelAngle=0, tickCount=5)),
        y=alt.Y("close:Q", title=None, scale=alt.Scale(zero=False), axis=alt.Axis(tickCount=4, gridOpacity=.25)),
        color=color,
        strokeDash=alt.StrokeDash("series:N", scale=alt.Scale(domain=[actual_lbl, fc_lbl], range=[[1, 0], [5, 3]]), legend=None),
    )
    hover = alt.selection_point(fields=["date"], nearest=True, on="pointerover", empty=False)
    lines = base.mark_line(strokeWidth=2)
    points = base.mark_circle(size=70).encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("date:T", title="التاريخ", format="%Y-%m-%d"),
                 alt.Tooltip("close:Q", title="الإغلاق", format=",.2f"),
                 alt.Tooltip("series:N", title="النوع")],
    ).add_params(hover)
    return (lines + points).properties(height=190)


# ---------- pages ----------

def predict_page():
    st.title("توقعات الأسبوع")
    st.caption("أعلى 30 سهمًا سيولةً في تداول — توقع أيام التداول الخمسة القادمة بنموذج Kronos-small (متوسط 5 مسارات).")

    if st.button("شغّل التوقع", type="primary", use_container_width=True):
        try:
            tasi, stocks, top, liquidity = pw.prepare(get_market())
        except Exception as e:  # network / data errors
            st.error(f"تعذّر تحميل البيانات: {e}")
            return
        key = str(tasi.index[-1].date())
        store = forecast_store()
        if key not in store:
            predictor = get_predictor()
            bar = st.progress(0.0, text="جارٍ التوقع…")
            store[key] = pw.forecast(
                predictor, tasi, stocks, top, liquidity,
                progress=lambda i, n, t: bar.progress(i / n, text=f"جارٍ التوقع… {i}/{n} ({t.replace('.SR', '')})"),
            )
            bar.empty()
        st.session_state["forecast"] = store[key]
        st.session_state["history"] = {t: stocks[t]["close"].iloc[-60:] for t in top}

    preds = st.session_state.get("forecast")
    if preds is None:
        st.info("اضغط «شغّل التوقع» لتحميل آخر الأسعار وتشغيل النموذج. قد يستغرق ذلك بضع دقائق على CPU.")
        return

    d1, d5 = preds["date_d1"].iloc[0], preds[f"date_d{pw.HORIZON}"].iloc[0]
    st.markdown(f"**آخر إغلاق:** <span class='num'>{preds['forecast_date'].iloc[0]}</span> &nbsp;·&nbsp; "
                f"**فترة التوقع:** <span class='num'>{d1}</span> ← <span class='num'>{d5}</span>",
                unsafe_allow_html=True)

    cols = [
        ("الشركة", company),
        ("آخر إغلاق", lambda r: fmt_px(r["last_close"])),
        ("الإغلاق المتوقع", lambda r: fmt_px(r[f"pred_close_d{pw.HORIZON}"])),
        ("العائد المتوقع %", lambda r: fmt_ret(r["pred_return_5d"])),
    ]
    st.subheader("▲ أعلى 5")
    st.markdown(returns_table(preds.head(5), cols), unsafe_allow_html=True)
    st.subheader("▼ أدنى 5")
    st.markdown(returns_table(preds.tail(5).iloc[::-1], cols), unsafe_allow_html=True)

    up = int((preds["pred_return_5d"] > 0).sum())
    st.markdown(f"<small>متوسط العائد المتوقع للأسهم الثلاثين: {fmt_ret(preds['pred_return_5d'].mean())} · "
                f"متوقع صعود {up} من {len(preds)}</small>", unsafe_allow_html=True)

    st.download_button(
        "⬇️ تنزيل ملف التوقعات (CSV)",
        preds.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"predictions_{preds['forecast_date'].iloc[0]}.csv",
        mime="text/csv", use_container_width=True, on_click="ignore",
    )

    st.subheader("الرسوم — أعلى 5")
    st.markdown(
        f'<div class="legend"><span><i style="background:{ACTUAL}"></i>فعلي (آخر 60 يومًا)</span>'
        f'<span><i class="dash" style="border-color:{FORECAST}"></i>متوقع (5 أيام)</span></div>',
        unsafe_allow_html=True,
    )
    history = st.session_state.get("history", {})
    for _, row in preds.head(5).iterrows():
        if row["ticker"] in history:
            st.markdown(f"**{html.escape(row['name'])}** · {fmt_ret(row['pred_return_5d'])}", unsafe_allow_html=True)
            st.altair_chart(stock_chart(history[row["ticker"]], row), use_container_width=True)


def evaluate_page():
    st.title("تقييم توقع سابق")
    st.caption("ارفع ملف predictions_YYYY-MM-DD.csv لمقارنة التوقع بما حدث فعلًا خلال 5 جلسات تداول.")

    up = st.file_uploader("ملف التوقعات (CSV)", type="csv")
    if up is None:
        return
    try:
        preds = pd.read_csv(up, encoding="utf-8-sig")
        missing = ev_mod.REQUIRED_COLS - set(preds.columns)
        if missing:
            st.error(f"الملف لا يبدو ملف توقعات: تنقصه الأعمدة {', '.join(sorted(missing))}")
            return
        start = str(pd.Timestamp(preds["forecast_date"].iloc[0]).date())
        ev = ev_mod.evaluate(preds, get_actuals(tuple(preds["ticker"]), start))
    except Exception as e:
        st.error(f"تعذّر التقييم: {e}")
        return

    if not ev.complete:
        st.warning(f"لم تكتمل فترة التوقع بعد: مضت **{ev.sessions_elapsed}** من **{ev_mod.HORIZON}** جلسات تداول بعد {start}.")
        st.progress(ev.sessions_elapsed / ev_mod.HORIZON, text=f"{ev.sessions_elapsed}/{ev_mod.HORIZON} جلسات")
        return

    st.markdown(f"**فترة التقييم:** إغلاق <span class='num'>{ev.start.date()}</span> ← إغلاق "
                f"<span class='num'>{ev.end.date()}</span>", unsafe_allow_html=True)

    def p(x):
        return f"{x * 100:+.2f}%"

    c1, c2 = st.columns(2)
    c1.metric("عائد أعلى 5 (فعلي)", p(ev.top_ret), f"{p(ev.top_ret - ev.tasi_ret)} مقابل تاسي", border=True)
    c2.metric("عائد أدنى 5 (فعلي)", p(ev.bottom_ret), f"{p(ev.bottom_ret - ev.tasi_ret)} مقابل تاسي", border=True)
    c3, c4 = st.columns(2)
    c3.metric("الفرق (أعلى − أدنى)", p(ev.top_ret - ev.bottom_ret), f"{p(ev.tasi_ret)} عائد تاسي", delta_color="off", border=True)
    c4.metric(f"صحة الاتجاه ({ev.hits} من {ev.n_valid} سهمًا)", f"{ev.hit_rate * 100:.0f}%",
              f"{(ev.hit_rate - .5) * 100:+.0f}% عن العشوائي", border=True)

    verdict = "✅ الترتيب صحيح: أعلى 5 تفوقت على أدنى 5." if ev.top_ret > ev.bottom_ret \
        else "❌ الترتيب معكوس: أدنى 5 تفوقت على أعلى 5."
    st.markdown(verdict)

    cols = [
        ("الشركة", company),
        ("المتوقع", lambda r: fmt_ret(r["pred_return_5d"])),
        ("الفعلي", lambda r: fmt_ret(r["actual_return_5d"])),
    ]
    with st.expander("التفاصيل لكل سهم"):
        st.markdown("**▲ أعلى 5**")
        st.markdown(returns_table(ev.top, cols), unsafe_allow_html=True)
        st.markdown("**▼ أدنى 5**")
        st.markdown(returns_table(ev.bottom, cols), unsafe_allow_html=True)
        st.markdown("**كل الأسهم**")
        st.markdown(returns_table(ev.preds, cols), unsafe_allow_html=True)


st.navigation(
    [st.Page(predict_page, title="توقعات الأسبوع", icon="📈", default=True),
     st.Page(evaluate_page, title="تقييم توقع سابق", icon="✅", url_path="evaluate")],
    position="top",
).run()
