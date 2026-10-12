# Egyptian Labor Law Chatbot

A RAG assistant for Egyptian Labor Law No. 14 of 2025 and its executive decisions. Ask in formal or colloquial Arabic and get an answer grounded in the official text, with the article number and page.

- **Hybrid retrieval:** exact article-number lookup, BM25 over normalized Arabic with a legal-synonym layer, and optional embeddings, fused with Reciprocal Rank Fusion
- **Measured:** 94% Recall@8 and 83% top-1 on an 18-question evaluation set using lexical search alone (`scripts/eval_retrieval.py`)
- **Cheap to run:** retrieval works with no API key; the key is only needed to phrase the final answer
- **Corpus:** 796 chunks and 297 indexed articles extracted from 8 official PDFs

**Stack:** Python · FastAPI · BM25 · OpenAI · vanilla web UI

```bash
pip install -r requirements.txt
cp .env.example .env      # add OPENAI_API_KEY (optional)
./run.sh                  # http://127.0.0.1:8000
```

See also [smart-legal-advisor](https://github.com/MahmoudElnahal/smart-legal-advisor), the React voice-and-chat front end for the same domain.

The full documentation below is in Arabic.

---

# شات بوت قانون العمل المصري

بروتوتايب شغّال: موقع ويب تسأله عن قانون العمل رقم 14 لسنة 2025 وقراراته التنفيذية،
فيرد بإجابة مبنية على النص الرسمي مع ذكر رقم المادة والصفحة.

مبني على مجموعة البيانات المفرّغة من 8 ملفات PDF (796 مقطع، 297 مادة مفهرسة).

---

## التشغيل في دقيقتين

```bash
pip install -r requirements.txt

cp .env.example .env          # وحط مفتاح OpenAI جواه
./run.sh                      # أو: python -m uvicorn app.server:app --port 8000
```

افتح <http://127.0.0.1:8000>

**بيشتغل من غير مفتاح كمان** — البحث اللفظي مجاني بالكامل، وهتشوف المصادر
من غير صياغة إجابة. مفيد إنك تجرّب جودة البحث قبل ما تصرف مليم.

### بناء فهرس الـ embeddings (اختياري بس مُوصى به)

```bash
python scripts/build_index.py
```

مرة واحدة، تكلفتها أقل من 3 سنت، وبتخزّن `data/embeddings.npz`.
السيرفر بيلقطه تلقائيًا أول ما يشتغل.

---

## إزاي بيشتغل

```
سؤال المستخدم
     │
     ├─► استخراج رقم المادة      "المادة 120" → مطابقة حرفية مضمونة
     ├─► BM25 على النص العربي     تطبيع + تجريد + توسيع بالمرادفات القانونية
     └─► embeddings (اختياري)     للأسئلة اللي مفيهاش كلمة مشتركة مع النص
                  │
          دمج بـ Reciprocal Rank Fusion
                  │
          أفضل 8 مقاطع → GPT مع تعليمات صارمة
                  │
          إجابة مبثوثة + قائمة المصادر
```

### ليه البحث الهجين مش embeddings وبس

أغلب أسئلة قانون العمل بتذكر رقم مادة أو مصطلح محدد. المطابقة الحرفية في
الحالات دي أدق من البحث الدلالي، وأسرع، ومجانية. الـ embeddings بتشتغل
على الأسئلة اللي بالعامية والمعنى فيها بعيد عن لفظ القانون
("فصلوني من الشغل" ↔ "إنهاء عقد العمل بغير مبرر").

### طبقة المرادفات

`app/synonyms.py` فيه جدول بيترجم لغة الناس للغة القانون:
"مرتب" → "أجر"، "فصل تعسفي" → "إنهاء بغير مبرر"، "عقوبة" → "يعاقب / غرامة".
الجدول ده لوحده رفّع الـ Recall من 83% لـ 94% من غير أي تكلفة —
أرخص وأدق من إنك تعتمد على الـ embedding وحده.

---

## قياس الجودة

```bash
python scripts/eval_retrieval.py          # لفظي بس
python scripts/eval_retrieval.py --dense  # بالـ embeddings
```

18 سؤال بالعامية والفصحى، ولكل واحد المواد الصح (متأكد منها من نص القانون).

| المقياس | بحث لفظي بس |
|---|---|
| Recall@8 | **94%** (17/18) |
| أول نتيجة صح | **83%** (15/18) |

شغّله بعد أي تعديل في المرادفات أو الأوزان — لو الرقم نزل، التعديل ضرّ.
وزوّد أسئلة للمجموعة كل ما تلاقي سؤال البوت غلط فيه.

---

## الملفات

```
app/
  arabic.py      تطبيع عربي، تجريد خفيف، استخراج أرقام المواد
  synonyms.py    جدول المرادفات القانونية
  retrieval.py   BM25 + مطابقة المواد + embeddings + الدمج
  llm.py         الـ prompt والبثّ
  server.py      FastAPI
  config.py      الإعدادات (كلها من متغيرات البيئة)
web/index.html   واجهة الشات (RTL، وضع ليلي، بثّ مباشر)
scripts/
  build_index.py     بناء فهرس embeddings
  build_corpus.py    إعادة توليد الـ chunks من ملفات Markdown
  eval_retrieval.py  قياس جودة البحث
data/
  corpus-chunks.jsonl  796 مقطع
```

## الـ API

| الطريق | الوظيفة |
|---|---|
| `GET /api/health` | حالة الفهرس والمفتاح |
| `POST /api/search` | بحث خام بدون موديل — `{"question": "...", "k": 5}` |
| `POST /api/chat` | إجابة مبثوثة SSE + المصادر |

`/api/search` هو اللي هتربطه بأي واجهة تانية (واتساب، موبايل أب) من غير ما
تلمس منطق البحث.

---

## الخطوات الجاية

1. **شغّل `build_index.py`** وقارن نتيجة الـ eval قبل وبعد.
2. **زوّد أسئلة الـ eval** كل ما تلاقي إجابة غلط — ده اللي بيمنع التحسينات إنها تكسر حاجة تانية.
3. **سجّل الأسئلة الحقيقية** من المستخدمين في ملف/جدول؛ أهم مصدر لتحسين المرادفات.
4. **واتساب**: WhatsApp Business API بيكلّم `/api/chat` بنفس الشكل — الـ backend مش هيتغير.
5. **قبل الإطلاق**: راجع مع محامٍ صياغة التنبيه القانوني، وحط rate limiting، وخزّن مفتاح OpenAI في متغيرات بيئة السيرفر مش في ملف.

## تنبيه

مساعد للاسترشاد فقط. النصوص مفرّغة آليًا وبصريًا من الجريدة الرسمية،
وللاعتماد القانوني يُرجع للنص الرسمي المنشور.
