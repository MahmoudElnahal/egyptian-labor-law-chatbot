# -*- coding: utf-8 -*-
"""
واجهة HTTP للشات بوت.

  GET  /                 صفحة الشات
  GET  /api/health       حالة الفهرس والمفتاح
  POST /api/search       بحث خام — بيرجّع المقاطع من غير موديل (مفيد للتجربة والتقييم)
  POST /api/chat         إجابة مبثوثة (SSE) + المصادر
"""
import json
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .config import ROOT, settings
from .llm import build_context, embed_query, stream_answer
from .retrieval import Corpus

app = FastAPI(title='شات بوت قانون العمل المصري')
corpus = Corpus(settings.corpus_path)
corpus.load_embeddings(settings.index_path)

_client = None


def client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


class Ask(BaseModel):
    question: str
    history: list = []
    k: int = 0


def retrieve(question: str, k: int):
    k = k or settings.top_k
    qv = None
    if corpus.embeddings is not None and settings.has_openai:
        try:
            qv = embed_query(client(), question)
        except Exception:
            qv = None                      # الدنيا متوقفتش: BM25 لوحده بيشتغل
    return corpus.search(question, k=k, query_vec=qv)


@app.get('/api/health')
def health():
    return {
        'ok': True,
        'openai': settings.has_openai,
        'chat_model': settings.chat_model,
        **corpus.stats(),
    }


@app.post('/api/search')
def search(req: Ask):
    hits = retrieve(req.question, req.k)
    return {'results': [{k: v for k, v in h.items() if k != 'نص'} | {'نص': h['نص']} for h in hits]}


@app.post('/api/chat')
def chat(req: Ask):
    hits = retrieve(req.question, req.k)
    context, used = build_context(hits, settings.max_context_chars)

    def gen():
        yield 'event: sources\ndata: ' + json.dumps(
            [{'وثيقة': u.get('وثيقة'), 'عنوان': u.get('عنوان'), 'صفحة': u.get('صفحة'),
              'ملف': u.get('ملف'), 'نص': u['نص'][:600]} for u in used], ensure_ascii=False) + '\n\n'
        if not settings.has_openai:
            msg = ('مفيش OPENAI_API_KEY متظبّط، فالبوت عرض المصادر من غير صياغة إجابة. '
                   'حط المفتاح في ملف .env وأعد التشغيل.')
            yield 'data: ' + json.dumps({'delta': msg}, ensure_ascii=False) + '\n\n'
            yield 'event: done\ndata: {}\n\n'
            return
        try:
            for piece in stream_answer(client(), req.question, context, req.history):
                yield 'data: ' + json.dumps({'delta': piece}, ensure_ascii=False) + '\n\n'
        except Exception as e:
            yield 'data: ' + json.dumps({'delta': f'\n\n[خطأ من الموديل: {e}]'}, ensure_ascii=False) + '\n\n'
        yield 'event: done\ndata: {}\n\n'

    return StreamingResponse(gen(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.get('/')
def index():
    return FileResponse(os.path.join(ROOT, 'web', 'index.html'))
