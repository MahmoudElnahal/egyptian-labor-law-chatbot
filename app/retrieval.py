# -*- coding: utf-8 -*-
"""
محرك بحث هجين فوق مجموعة بيانات قانون العمل.

ثلاث إشارات تتدمج بـ Reciprocal Rank Fusion:
  1) مطابقة رقم المادة   — حرفية ومضمونة، أعلى وزن
  2) BM25 على النص العربي — يشتغل بدون أي API key
  3) embeddings           — اختيارية، تشتغل لو الـ index مبني

السبب في الترتيب ده: أغلب أسئلة قانون العمل بتذكر رقم مادة أو مصطلح محدد
('بدل السفر'، 'الفصل التعسفي')، والمطابقة الحرفية بتغلب البحث الدلالي فيها.
"""
import json
import math
import os
import re
from collections import Counter, defaultdict

from .arabic import tokenize, normalize, extract_article_numbers, extract_law_numbers
from .synonyms import expand

K1 = 1.4
B = 0.72
RRF_K = 60


class Corpus:
    def __init__(self, jsonl_path: str):
        self.docs = []
        with open(jsonl_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    self.docs.append(json.loads(line))
        self._build_bm25()
        self._build_article_index()
        self.embeddings = None
        self.emb_model = None

    # ---------- BM25 ----------
    def _build_bm25(self):
        self.tokens = []
        df = Counter()
        for d in self.docs:
            # المسار جزء من النص المفهرس: اسم القانون والباب بيساعدوا في المطابقة
            blob = (d.get('المسار', '') + ' ' + d.get('عنوان', '') + ' ' + d['نص'])
            toks = tokenize(blob)
            self.tokens.append(Counter(toks))
            df.update(set(toks))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.lengths = [sum(c.values()) for c in self.tokens]
        self.avgdl = sum(self.lengths) / max(1, n)
        self.postings = defaultdict(list)
        for i, c in enumerate(self.tokens):
            for t in c:
                self.postings[t].append(i)

    def bm25(self, query: str, top: int = 40):
        q = expand(tokenize(query))
        if not q:
            return []
        scores = defaultdict(float)
        for t in set(q):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i in self.postings[t]:
                tf = self.tokens[i][t]
                dl = self.lengths[i]
                scores[i] += idf * (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * dl / self.avgdl))
        return sorted(scores.items(), key=lambda x: -x[1])[:top]

    # ---------- مطابقة المواد ----------
    def _build_article_index(self):
        self.by_article = defaultdict(list)
        for i, d in enumerate(self.docs):
            n = d.get('رقم_المادة')
            if n is not None:
                self.by_article[n].append(i)

    def article_lookup(self, query: str):
        nums = extract_article_numbers(query)
        if not nums:
            return []
        laws = set(extract_law_numbers(query))
        hits = []
        for n in nums:
            cands = self.by_article.get(n, [])
            # لو السؤال ذكر 'قانون 14' نرجّح مواد القانون، ولو ذكر رقم قرار نرجّح القرار
            scored = []
            for i in cands:
                d = self.docs[i]
                s = 1.0
                doc_nums = set(int(x) for x in re.findall(r'\d{1,4}', d.get('وثيقة', '')))
                if laws & doc_nums:
                    s += 2.0
                elif not laws and d.get('نوع') == 'قانون':
                    s += 1.0            # الافتراضي: المقصود قانون العمل نفسه
                scored.append((i, s))
            scored.sort(key=lambda x: -x[1])
            hits += scored
        return hits

    # ---------- embeddings (اختيارية) ----------
    def load_embeddings(self, path: str):
        if not os.path.exists(path):
            return False
        import numpy as np
        blob = np.load(path, allow_pickle=True)
        mat = blob['vectors']
        ids = list(blob['ids'])
        if len(ids) != len(self.docs) or ids[0] != self.docs[0]['id']:
            by_id = {d['id']: k for k, d in enumerate(self.docs)}
            order = [by_id[i] for i in ids if i in by_id]
            full = np.zeros((len(self.docs), mat.shape[1]), dtype=mat.dtype)
            for row, k in enumerate(order):
                full[k] = mat[row]
            mat = full
        self.embeddings = mat
        self.emb_model = str(blob['model'])
        return True

    def dense(self, query_vec, top: int = 40):
        if self.embeddings is None:
            return []
        import numpy as np
        q = np.asarray(query_vec, dtype=self.embeddings.dtype)
        q /= (np.linalg.norm(q) + 1e-9)
        sims = self.embeddings @ q
        idx = np.argpartition(-sims, min(top, len(sims) - 1))[:top]
        idx = idx[np.argsort(-sims[idx])]
        return [(int(i), float(sims[i])) for i in idx]

    # ---------- الدمج ----------
    def search(self, query: str, k: int = 8, query_vec=None):
        ranked = {
            'article': self.article_lookup(query),
            'bm25': self.bm25(query),
            'dense': self.dense(query_vec) if query_vec is not None else [],
        }
        weights = {'article': 3.0, 'bm25': 1.0, 'dense': 1.3}
        fused = defaultdict(float)
        why = defaultdict(set)
        for src, lst in ranked.items():
            for rank, (i, _s) in enumerate(lst):
                fused[i] += weights[src] / (RRF_K + rank + 1)
                why[i].add(src)
        out = []
        for i, s in sorted(fused.items(), key=lambda x: -x[1])[:k]:
            d = dict(self.docs[i])
            d['_score'] = round(s, 5)
            d['_signals'] = sorted(why[i])
            out.append(d)
        return out

    def stats(self):
        return {
            'chunks': len(self.docs),
            'مواد_مفهرسة': len(self.by_article),
            'مفردات': len(self.idf),
            'embeddings': bool(self.embeddings is not None),
            'موديل_الـembedding': self.emb_model,
        }
