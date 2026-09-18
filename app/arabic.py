# -*- coding: utf-8 -*-
"""تطبيع النص العربي للبحث + تحويل الأرقام المكتوبة بالحروف."""
import re
import unicodedata

_DIACRITICS = re.compile(r'[ً-ْٰـ]')
_NONWORD = re.compile(r'[^\wء-ي]+')

# لواحق وسوابق شائعة نشيلها عشان "العامل" و"للعامل" و"بالعمال" يطابقوا بعض
_PREFIXES = ('وال', 'بال', 'كال', 'فال', 'لل', 'ال', 'و', 'ف', 'ب', 'ك', 'ل')
_SUFFIXES = ('ها', 'هم', 'هن', 'كم', 'كن', 'نا', 'ية', 'ات', 'ين', 'ون', 'ان', 'ه', 'ة', 'ي')

STOPWORDS = {
    'فى', 'في', 'من', 'على', 'الى', 'إلى', 'عن', 'مع', 'هذا', 'هذه', 'ذلك', 'التى', 'التي',
    'الذى', 'الذي', 'او', 'أو', 'ان', 'أن', 'إن', 'ما', 'لا', 'كل', 'قد', 'كان', 'يكون',
    'هو', 'هى', 'هي', 'به', 'بها', 'له', 'لها', 'بين', 'عند', 'بعد', 'قبل', 'حتى', 'ثم',
    'كما', 'اى', 'أي', 'ايه', 'إيه', 'ازاي', 'إزاي', 'يعني', 'يعنى', 'هل', 'هى',
}

# الأرقام المكتوبة بالحروف — عشان "المادة المائة" أو "المادة عشرين" تتفهم
_WORD_NUMS = {
    'صفر': 0, 'واحد': 1, 'اثنين': 2, 'اثنان': 2, 'ثلاثة': 3, 'ثلاث': 3, 'اربعة': 4, 'اربع': 4,
    'خمسة': 5, 'خمس': 5, 'ستة': 6, 'ست': 6, 'سبعة': 7, 'سبع': 7, 'ثمانية': 8, 'ثمان': 8,
    'تسعة': 9, 'تسع': 9, 'عشرة': 10, 'عشر': 10, 'عشرين': 20, 'ثلاثين': 30, 'اربعين': 40,
    'خمسين': 50, 'ستين': 60, 'سبعين': 70, 'ثمانين': 80, 'تسعين': 90, 'مائة': 100, 'مئة': 100,
    'الاولى': 1, 'الثانية': 2, 'الثالثة': 3, 'الرابعة': 4, 'الخامسة': 5, 'السادسة': 6,
    'السابعة': 7, 'الثامنة': 8, 'التاسعة': 9, 'العاشرة': 10,
}

_AR_DIGITS = {chr(0x0660 + i): str(i) for i in range(10)}
_AR_DIGITS.update({chr(0x06F0 + i): str(i) for i in range(10)})


def normalize(text: str) -> str:
    """توحيد شكل النص: حروف موحّدة، بدون تشكيل، أرقام لاتينية."""
    if not text:
        return ''
    text = unicodedata.normalize('NFKC', text)
    text = ''.join(_AR_DIGITS.get(c, c) for c in text)
    text = _DIACRITICS.sub('', text)
    text = re.sub(r'[أإآٱ]', 'ا', text)
    text = re.sub(r'[ىئ]', 'ي', text)
    text = text.replace('ؤ', 'و').replace('ة', 'ه')
    text = re.sub(r'ـ', '', text)
    return text


def stem(word: str) -> str:
    """تجريد خفيف — مش صرفي كامل، بس بيرفع نسبة المطابقة كتير في العربي."""
    w = word
    for p in _PREFIXES:
        if w.startswith(p) and len(w) - len(p) >= 3:
            w = w[len(p):]
            break
    for s in _SUFFIXES:
        if w.endswith(s) and len(w) - len(s) >= 3:
            w = w[:-len(s)]
            break
    return w


def tokenize(text: str, do_stem: bool = True) -> list:
    text = normalize(text)
    tokens = [t for t in _NONWORD.split(text) if t and t not in STOPWORDS and len(t) > 1]
    if do_stem:
        tokens = [stem(t) for t in tokens]
    return [t for t in tokens if len(t) > 1]


def extract_article_numbers(query: str) -> list:
    """يستخرج أرقام المواد المذكورة في السؤال: 'المادة 120'، 'مادة رقم ٤٥'، 'المادة العشرين'."""
    q = normalize(query)
    nums = []
    for m in re.finditer(r'(?:الماده|ماده|بند)\s*(?:رقم\s*)?\(?\s*(\d{1,3})\s*\)?', q):
        nums.append(int(m.group(1)))
    for m in re.finditer(r'(?:الماده|ماده)\s+([ء-ي]+)(?:\s+([ء-ي]+))?', q):
        w1, w2 = m.group(1), m.group(2)
        v = _WORD_NUMS.get(w1)
        if v is not None:
            if w2 and _WORD_NUMS.get(w2):
                v += _WORD_NUMS[w2] if _WORD_NUMS[w2] >= 10 else 0
            nums.append(v)
    return sorted(set(nums))


def extract_law_numbers(query: str) -> list:
    """أرقام القوانين/القرارات المذكورة: 'قانون 14 لسنة 2025'، 'قرار 162'."""
    q = normalize(query)
    out = []
    for m in re.finditer(r'(?:قانون|قرار)\s*(?:رقم\s*)?\(?\s*(\d{1,4})\s*\)?', q):
        out.append(int(m.group(1)))
    return sorted(set(out))
