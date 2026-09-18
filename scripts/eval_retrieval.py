#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
قياس جودة البحث — من غير ما يكلّفك مليم.

مجموعة أسئلة بالعامية والفصحى، ولكل سؤال المواد الصحيحة (اتأكدت منها من نص القانون).
بنقيس Recall@k: هل المادة الصح طلعت ضمن أول k نتيجة اللى بتروح للموديل؟

    python scripts/eval_retrieval.py            # بحث لفظي بس (مجاني)
    python scripts/eval_retrieval.py --dense    # بالـ embeddings كمان

شغّله بعد أي تعديل في المرادفات أو أوزان الدمج — لو الرقم نزل، التعديل ضرّ.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.retrieval import Corpus

# (السؤال، المواد المتوقعة في قانون العمل 14/2025)
GOLD = [
    ('إيه نص المادة 54؟',                              [54]),
    ('المادة 90 بتقول إيه؟',                            [90]),
    ('إجازة الوضع مدتها قد إيه؟',                       [54, 55]),
    ('كام يوم إجازة سنوية للعامل؟',                     [124, 125, 126]),
    ('العامل يقدر ينقطع عن الشغل لسبب طارئ كام يوم؟',   [128]),
    ('الراحة الأسبوعية للعامل',                          [120]),
    ('فترة الاختبار أقصاها كام؟',                        [90]),
    ('العامل المريض له إجازة مرضية؟',                    [131]),
    ('تشغيل النساء والمساواة في الأجر',                  [53]),
    ('تشغيل الأطفال والسن المسموح بيه',                  [61, 66, 67]),
    ('الاستقالة إزاي تكون صحيحة؟',                       [167]),
    ('العامل يقدر ينهي العقد لو صاحب العمل أخلّ بالتزاماته؟', [168]),
    ('عقوبة مخالفة حظر السخرة والتمييز',                 [280, 281]),
    ('اتفاق التدرج لازم يكون مكتوب؟',                    [29, 30]),
    ('حظر التحرش والتنمر في مكان العمل',                 [4]),
    ('المفاوضة الجماعية لتسوية النزاع',                  [196]),
    ('الأجر بيتدفع إمتى وفين؟',                          [108]),
    ('التمييز بين الأشخاص في التوظيف',                   [5]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dense', action='store_true', help='استخدم الـ embeddings كمان')
    ap.add_argument('-k', type=int, default=8)
    args = ap.parse_args()

    c = Corpus(settings.corpus_path)
    use_dense = False
    if args.dense:
        if c.load_embeddings(settings.index_path) and settings.has_openai:
            from openai import OpenAI
            from app.llm import embed_query
            client = OpenAI(api_key=settings.openai_api_key)
            use_dense = True
        else:
            print('⚠ مفيش فهرس embeddings أو مفتاح — هكمّل بالبحث اللفظي بس.\n')

    print(f'الفهرس: {c.stats()}\nالتقييم على {len(GOLD)} سؤال بـ k={args.k}\n')
    hit_top1 = hits = 0
    misses = []
    for q, gold in GOLD:
        qv = embed_query(client, q) if use_dense else None
        res = c.search(q, k=args.k, query_vec=qv)
        found = [r.get('رقم_المادة') for r in res if r.get('نوع') == 'قانون']
        ok = any(g in found for g in gold)
        top1 = bool(found) and found[0] in gold
        hits += ok
        hit_top1 += top1
        mark = '✓' if ok else '✗'
        pos = (found.index(next(g for g in gold if g in found)) + 1) if ok else '-'
        print(f'{mark} [{pos}] {q}')
        print(f'    متوقع {gold} | رجع {found[:6]}')
        if not ok:
            misses.append(q)

    n = len(GOLD)
    print(f'\nRecall@{args.k}: {hits}/{n} = {hits / n:.0%}')
    print(f'أول نتيجة صح:  {hit_top1}/{n} = {hit_top1 / n:.0%}')
    if misses:
        print('\nالأسئلة اللي فشلت:')
        for m in misses:
            print('  -', m)


if __name__ == '__main__':
    main()
