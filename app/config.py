# -*- coding: utf-8 -*-
"""إعدادات المشروع — كلها قابلة للضبط من متغيرات البيئة أو ملف .env."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_dotenv():
    path = os.path.join(ROOT, '.env')
    if not os.path.exists(path):
        return
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


class Settings:
    openai_api_key = os.getenv('OPENAI_API_KEY', '')
    chat_model = os.getenv('CHAT_MODEL', 'gpt-4.1')
    embedding_model = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-large')

    corpus_path = os.getenv('CORPUS_PATH', os.path.join(ROOT, 'data', 'corpus-chunks.jsonl'))
    index_path = os.getenv('INDEX_PATH', os.path.join(ROOT, 'data', 'embeddings.npz'))

    top_k = int(os.getenv('TOP_K', '8'))          # عدد المقاطع اللي بتروح للموديل
    max_context_chars = int(os.getenv('MAX_CONTEXT_CHARS', '14000'))
    host = os.getenv('HOST', '127.0.0.1')
    port = int(os.getenv('PORT', '8000'))

    @property
    def has_openai(self):
        return bool(self.openai_api_key)


settings = Settings()
