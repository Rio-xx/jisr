# Kronos × Aramco (2222.SR)

اختبار رجعي لنموذج Kronos-small على سهم أرامكو: آخر 30 يوم تداول كبيانات اختبار، والتنبؤ بها من كل ما قبلها.

## التثبيت
```bash
git clone https://github.com/shiyu-coder/Kronos ../Kronos   # أو أي مسار آخر
python3 -m venv ../Kronos/.venv
../Kronos/.venv/bin/pip install -r ../Kronos/requirements.txt yfinance
```

## التشغيل (CPU)
```bash
KRONOS_DIR=../Kronos ../Kronos/.venv/bin/python forecast_aramco.py
```
يطبع MAE ونسبة صحة الاتجاه، ويحفظ `aramco_kronos_forecast.png`.
يتطلب الوصول إلى `query*.finance.yahoo.com` و`huggingface.co`.

## توقعات الأسبوع لأعلى 30 سهمًا سيولة

```bash
# بعد إغلاق آخر جلسة: يتنبأ بأيام التداول الخمسة القادمة (الأحد–الخميس)
KRONOS_DIR=../Kronos ../Kronos/.venv/bin/python predict_week.py
# بعد مرور 5 أيام تداول: يقيّم ملف التوقعات مقابل الأسعار الفعلية وتاسي
../Kronos/.venv/bin/python evaluate_week.py predictions_YYYY-MM-DD.csv
```

- يُختار أعلى 30 سهمًا من قائمة مرشحة (`tadawul_common.UNIVERSE`) حسب متوسط قيمة التداول خلال آخر 60 جلسة.
- تواريخ التوقع تقويم الأحد–الخميس ولا تحتسب العطل الرسمية. أما التقييم فيعتمد على الجلسة الخامسة الفعلية في بيانات تاسي.
- عائد أعلى/أدنى 5 متوسط متساوي الأوزان. والاتجاه يُقارن بإشارة العائد المتوقع مع إشارة العائد الفعلي على 5 أيام.
