# -*- coding: utf-8 -*-
import json, os, re, sys, hashlib

# مجلد ملفات الـ Markdown — الافتراضي: markdown-dataset جنب المشروع
OUT = os.environ.get('MD_DIR') or (
    sys.argv[1] if len(sys.argv) > 1 else
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'markdown-dataset'))
FILES = [
    ('01-قانون-العمل-14-لسنة-2025.md', 'قانون العمل رقم 14 لسنة 2025', 'قانون'),
    ('02-القرارات-واللوائح-التنفيذية.md', 'القرارات الوزارية واللوائح التنفيذية', 'قرار'),
    ('03-سؤال-وجواب-في-قانون-العمل.md', 'سؤال وجواب في قانون العمل — الجزء الأول', 'دليل'),
]
PAGE = re.compile(r'<!--\s*(?:المصدر:\s*(.+?)\s*\|\s*)?صفحة\s*(\d+)\s*-->')
MAXC = 2800

def clean_body(txt):
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    return txt.strip()

def flush(chunks, meta, buf):
    txt = clean_body('\n'.join(buf))
    if not txt or len(txt) < 15:
        return
    parts = [txt]
    if len(txt) > MAXC:
        parts, cur = [], ''
        for para in txt.split('\n\n'):
            if len(cur) + len(para) > MAXC and cur:
                parts.append(cur.strip()); cur = ''
            cur += para + '\n\n'
        if cur.strip(): parts.append(cur.strip())
    for i, p in enumerate(parts):
        m = {k: v for k, v in meta.items() if v is not None}
        if len(parts) > 1:
            m['جزء'] = '%d/%d' % (i + 1, len(parts))
        m['نص'] = p
        m['عدد_الحروف'] = len(p)
        m['id'] = hashlib.md5((m['ملف'] + str(m.get('عنوان')) + str(m.get('جزء', '')) + p[:60]).encode()).hexdigest()[:16]
        chunks.append(m)

def parse(path, docname, kind):
    chunks = []
    ctx = {1: docname, 2: None, 3: None, 4: None}
    meta, buf, page, src = None, [], None, None
    lines = open(os.path.join(OUT, path), encoding='utf-8').read().split('\n')
    if lines and lines[0].strip() == '---':          # تخطي الـ front matter
        end = lines[1:].index('---') + 1
        lines = lines[end + 1:]
    def base(lvl):
        return {'ملف': path, 'وثيقة': ctx[1], 'نوع': kind,
                'الكتاب': ctx[2] if (ctx[2] or '').startswith('الكتاب') else None,
                'الباب': ctx[3] if (ctx[3] or '').startswith('الباب') else (ctx[2] if (ctx[2] or '').startswith('الباب') else None),
                'الفصل': ctx[4] if (ctx[4] or '').startswith('الفصل') else (ctx[3] if (ctx[3] or '').startswith('الفصل') else None),
                'المسار': ' > '.join([x for x in [ctx[1], ctx[2], ctx[3], ctx[4]] if x]),
                'صفحة': page, 'ملف_المصدر': src}
    for line in lines:
        pm = PAGE.search(line)
        if pm:
            if pm.group(1): src = pm.group(1)
            page = int(pm.group(2))
            continue
        h = re.match(r'^(#{1,6})\s+(.*\S)\s*$', line)
        if h:
            lvl, title = len(h.group(1)), h.group(2).strip()
            if buf:
                flush(chunks, meta or dict(base(lvl), **{'عنوان': ctx[2] or ctx[1]}), buf)
                buf = []
            if lvl == 1:
                ctx.update({1: title, 2: None, 3: None, 4: None}); meta = None; continue
            for k in range(lvl, 5):
                ctx[k] = None
            if lvl <= 4:
                ctx[lvl] = title
            art = re.match(r'^المادة\s+(\d+)', title)
            m = base(lvl)
            m['عنوان'] = title
            if art:
                m['رقم_المادة'] = int(art.group(1))
            if title.startswith('س:'):
                m['نوع'] = 'سؤال وجواب'; m['سؤال'] = title[2:].strip()
            meta = m
            buf = [title]
            continue
        buf.append(line)
    if buf:
        flush(chunks, meta or dict(base(2), **{'عنوان': ctx[2] or ctx[1]}), buf)
    return chunks

all_chunks = []
for p, d, k in FILES:
    c = parse(p, d, k)
    print(p, '->', len(c), 'chunks')
    all_chunks += c

with open(os.path.join(OUT, 'corpus-chunks.jsonl'), 'w', encoding='utf-8') as f:
    for c in all_chunks:
        f.write(json.dumps(c, ensure_ascii=False) + '\n')
_data = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'corpus-chunks.jsonl')
os.makedirs(os.path.dirname(_data), exist_ok=True)
with open(_data, 'w', encoding='utf-8') as f:
    for c in all_chunks:
        f.write(json.dumps(c, ensure_ascii=False) + '\n')
print('TOTAL', len(all_chunks), '|', sum(c['عدد_الحروف'] for c in all_chunks), 'chars ->', _data)
