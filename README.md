# الذاكرة AlDhakira

الذاكرة عقل ثان محلي خاص: يبتلع ملفات نصية وJSON/JSONL/CSV، يعقم الأسرار قبل التخزين، يقسم النص إلى مقاطع، يبني فهرس BM25/TF-IDF بلا تبعيات، ثم يسترجع إجابات مع إحالات إلى المصادر.

## آلية العمل

1. `build` يقرأ المصدر أو المجلد ويدعم `txt/md/json/jsonl/csv`.
2. `redact` داخل خط الابتلاع يحذف البريد والمفاتيح والأسرار قبل كتابة المقاطع.
3. `chunk_text` يقسم النصوص إلى مقاطع صغيرة قابلة للاسترجاع.
4. `build_index` يكتب `chunks.jsonl`, `postings.json`, و`meta.json`.
5. `search` يستخدم BM25 لاسترجاع أفضل المقاطع.
6. `ask` يعيد إجابة مختصرة مع citations محلية، ولا يستدعي الإنترنت أو LLM.

## تشغيل سريع

```powershell
python -m aldhakira.cli build --source C:\Users\FARHAN\AI_PROJECTS_REFERENCE --index indexes\reference
python -m aldhakira.cli ask --index indexes\reference --query "ما هي فكرة السرب؟"
```

## اختبار كبير

```powershell
python -m aldhakira.cli benchmark --source C:\Projects\almeezan\data\external\databricks-dolly-15k\databricks-dolly-15k.jsonl --limit 12000
python -m aldhakira.cli stress --index indexes\dolly15k --repeat 3
```

مصدر البيانات الكبير: Databricks Dolly 15k المحفوظ من الإنترنت داخل مشروع الميزان.

## آخر نتائج

- الاختبارات الذاتية: 3/3 ناجحة.
- الفهرس الكبير: 12,000 سجل Dolly تحولت إلى 14,862 مقطعاً، مع 66,335 مصطلحاً و26 تعقيماً للأسرار/البريد قبل التخزين.
- Benchmark: 12,000 سؤال، 0 أخطاء، Recall@5=98.56%، p99=89.89ms، peak memory=3.48MB أثناء القياس.
- Stress تفاعلي: 12 سؤالاً، 0 أخطاء، 0 نتائج فارغة، p99=20.12ms.

## تحسينات إنتاجية 2026-07-04

- البحث في benchmark/stress يحمّل الفهرس مرة واحدة داخل `MemoryIndex` بدلاً من إعادة تحميل `chunks/postings` لكل سؤال.
- تمت إضافة stopwords عربية/إنجليزية واختيار أندر 10 مصطلحات في الاستعلام لتقليل الغرق في الكلمات العامة.
- لا تخزن المقاطع الأسرار الخام؛ يتم استبدال البريد والمفاتيح بعلامات آمنة مع عدّ redactions في `meta.json`.

## التشغيل المؤسسي (Enterprise) — v1.0.0

- **خدمة استرجاع HTTP**: `python -m aldhakira.cli serve` → `POST /api/ask` و`POST /api/search` بـ `{"query","top_k"}`.
- **الفهرس يحمل مرة واحدة** في الذاكرة عند الإقلاع (`ALDHAKIRA_INDEX`، افتراضي `indexes\default`).
- **ضمانة**: الأسرار معقمة عند الابتلاع فلا تظهر في نتائج البحث.
- **نقاط فحص**: `/api/health` (مفتوح) · `/api/version` · `/api/metrics`.
- **تهيئة عبر البيئة**: متغيرات `ALDHAKIRA_*` — انظر `docs/OPERATIONS.md`.
- **مصادقة**: `ALDHAKIRA_API_KEY` → ترويسة `X-API-Key`. **سجلات JSON**: `logs\aldhakira.service.jsonl`.
