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
