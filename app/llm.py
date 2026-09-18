# -*- coding: utf-8 -*-
"""طبقة الموديل: تكوين الـ prompt، وبثّ الإجابة، وتحويل السؤال لمتجه."""
from .config import settings

SYSTEM_PROMPT = """أنت مساعد قانوني متخصص في قانون العمل المصري رقم 14 لسنة 2025 وقراراته التنفيذية.

قواعد ملزمة:
1. اعتمد حصريًا على النصوص المرفقة في "المصادر". ممنوع تمامًا أن تخترع مادة أو رقمًا أو حكمًا غير موجود فيها.
2. لو المصادر لا تكفي للإجابة، قل ذلك صراحة واقترح صياغة أدق للسؤال. لا تخمّن.
3. اذكر رقم المادة والوثيقة بين قوسين بعد كل حكم تقوله، مثال: (المادة 54 — قانون العمل 14/2025).
4. اقتبس نص المادة حرفيًا عند السؤال عن نصها، ولخّص بلغة بسيطة عند السؤال عن المعنى العملي.
5. رد بالعربية الفصحى المبسّطة. لو المستخدم كتب بالعامية المصرية، خليك مبسّطًا لكن دقيقًا في المصطلح القانوني.
6. لو في تعارض ظاهري بين القانون وقرار تنفيذي، نبّه عليه ووضّح أن القانون هو الأصل.
7. اختم أي إجابة فيها حكم قانوني بسطر: "⚖️ للاعتماد القانوني يُرجع للنص الرسمي المنشور في الجريدة الرسمية، ويُفضّل استشارة محامٍ."
8. ممنوع تضيف "خطوات عملية" أو إجراءات أو جهات أو مواعيد (مكتب العمل، المحكمة العمالية، مدة الطعن…) إلا لو منصوص عليها في المصادر المرفقة ومعاها رقم المادة. لو المستخدم سأل "أعمل إيه؟" والمصادر ما فيهاش الإجراء، قل إن المصادر المتاحة بتحدد الحق الموضوعي بس، واطلب منه يسأل عن الإجراء صراحةً.
9. لو الحكم بيتغيّر حسب نوع العقد (محدد المدة / غير محدد المدة) أو حسب فئة العامل، نبّه على ده بوضوح بدل ما تجاوب عن حالة واحدة وكأنها القاعدة العامة.

اكتب إجابة مركّزة — من فقرة إلى ثلاث فقرات، مع نقاط عند الحاجة."""


def build_context(chunks, max_chars: int):
    """يحوّل نتائج البحث لنص مصادر مرقّم، مع قصّه عند الحد الأقصى."""
    parts, total = [], 0
    used = []
    for n, c in enumerate(chunks, start=1):
        head = f"[{n}] {c.get('وثيقة', '')}"
        if c.get('عنوان'):
            head += f" — {c['عنوان']}"
        if c.get('صفحة'):
            head += f" (صفحة {c['صفحة']})"
        block = f"{head}\n{c['نص']}"
        if total + len(block) > max_chars and parts:
            break
        parts.append(block)
        used.append(c)
        total += len(block)
    return '\n\n---\n\n'.join(parts), used


def embed_query(client, text: str):
    v = client.embeddings.create(model=settings.embedding_model, input=[text]).data[0].embedding
    return v


def stream_answer(client, question: str, context: str, history=None):
    """بثّ الإجابة توكن بتوكن — المستخدم يشوف الرد بيتكتب بدل ما يستنى."""
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    for turn in (history or [])[-6:]:
        if turn.get('role') in ('user', 'assistant') and turn.get('content'):
            messages.append({'role': turn['role'], 'content': turn['content'][:4000]})
    messages.append({
        'role': 'user',
        'content': f"المصادر:\n\n{context}\n\n---\n\nالسؤال: {question}",
    })
    stream = client.chat.completions.create(
        model=settings.chat_model,
        messages=messages,
        temperature=0.1,
        stream=True,
    )
    for event in stream:
        if event.choices and event.choices[0].delta and event.choices[0].delta.content:
            yield event.choices[0].delta.content
