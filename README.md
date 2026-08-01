# LabStats Shatrah

نظام إدارة وإحصائيات مختبر مستشفى الشطرة العام.

## النشر على Render
1. ارفع جميع ملفات هذا المجلد إلى مستودع GitHub.
2. في Render اختر New > Blueprint.
3. اختر المستودع `labstats-shatrah`.
4. سيقرأ Render ملف `render.yaml` وينشئ الموقع وقاعدة البيانات تلقائيًا.
5. رمز المدير الافتراضي: `A99999`.

## التشغيل المحلي
```bash
pip install -r requirements.txt
python app.py
```
ثم افتح:
`http://127.0.0.1:5000`
