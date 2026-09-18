#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
يبني فهرس الـ embeddings من corpus-chunks.jsonl باستخدام OpenAI.

    python scripts/build_index.py

بيحتاج OPENAI_API_KEY في البيئة أو في ملف .env.
التكلفة التقديرية: 798 chunk ≈ 150 ألف توكن ≈ أقل من 0.02 دولار بـ text-embedding-3-small
(أو ~0.02 دولار بـ 3-large). مرة واحدة بس — بعدها الفهرس متخزن على الديسك.

بنعمل embedding لـ "المسار + النص" مش النص وحده: المسار فيه اسم القانون والباب،
وده بيخلي المودیل يفرّق بين مادة في قانون العمل ومادة بنفس الرقم في قرار وزاري.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from openai import OpenAI

from app.config import settings

BATCH = 100


def embed_text(doc):
    path = doc.get('المسار') or doc.get('وثيقة', '')
    return (path + '\n' + doc['نص']).strip()


def main():
    if not settings.openai_api_key:
        sys.exit('مفيش OPENAI_API_KEY — حطه في ملف .env أو في متغيرات البيئة.')

    docs = [json.loads(l) for l in open(settings.corpus_path, encoding='utf-8') if l.strip()]
    print(f'{len(docs)} chunk | الموديل: {settings.embedding_model}')

    client = OpenAI(api_key=settings.openai_api_key)
    vectors, ids = [], []
    t0 = time.time()
    for start in range(0, len(docs), BATCH):
        batch = docs[start:start + BATCH]
        for attempt in range(5):
            try:
                resp = client.embeddings.create(
                    model=settings.embedding_model,
                    input=[embed_text(d) for d in batch],
                )
                break
            except Exception as e:                       # rate limit أو انقطاع شبكة
                if attempt == 4:
                    raise
                wait = 2 ** attempt
                print(f'  إعادة محاولة بعد {wait}ث ({e.__class__.__name__})')
                time.sleep(wait)
        for d, item in zip(batch, resp.data):
            v = np.asarray(item.embedding, dtype=np.float32)
            vectors.append(v / (np.linalg.norm(v) + 1e-9))   # نطبّعها مرة واحدة هنا
            ids.append(d['id'])
        done = min(start + BATCH, len(docs))
        print(f'  {done}/{len(docs)}  ({time.time() - t0:.0f}ث)')

    mat = np.vstack(vectors)
    os.makedirs(os.path.dirname(settings.index_path), exist_ok=True)
    np.savez_compressed(settings.index_path, vectors=mat,
                        ids=np.array(ids), model=settings.embedding_model)
    print(f'تم: {settings.index_path} | {mat.shape[0]} متجه × {mat.shape[1]} بُعد')


if __name__ == '__main__':
    main()
