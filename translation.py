"""On-the-fly UI translation for the whole site.

There is no gettext/Flask-Babel setup in this app — every template has hardcoded
English strings. Rather than hand-wrapping ~1,500+ strings in `_()` calls, this
module translates the *rendered HTML* of a response: it walks the text nodes and
a small whitelist of attributes, translates each unique string once via the free
Google Translate web endpoint (no API key required), and caches the result in the
`translation_cache` table so every later view of that string is a DB lookup, not
a network call.

Not gettext-quality (proper nouns, ticket numbers embedded in prose, etc. can get
swept in), but it covers the whole rendered page with no per-template work, which
is the right tradeoff for a site this size with no existing i18n scaffolding.
"""
import hashlib
import html as html_lib
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

SUPPORTED_LANGUAGES = {"en": "English", "bn": "বাংলা"}

_SKIP_BLOCK_RE = re.compile(r"(<(script|style|textarea)\b[^>]*>.*?</\2>)", re.IGNORECASE | re.DOTALL)
_TEXT_NODE_RE = re.compile(r">([^<>]+)<")
_ATTR_RE = re.compile(r'\b(placeholder|title|aria-label|alt)="([^"]*)"')
_LETTER_RE = re.compile(r"[A-Za-z]{2,}")

_FREE_ENDPOINT = "https://translate.googleapis.com/translate_a/single"


def _looks_translatable(s):
    s = s.strip()
    if not s or len(s) > 500:
        return False
    return bool(_LETTER_RE.search(s))


def _hash(lang, text):
    return hashlib.sha256(f"{lang}:{text}".encode("utf-8")).hexdigest()


def _free_translate(text, target):
    params = urllib.parse.urlencode({
        "client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": text,
    })
    req = urllib.request.Request(
        f"{_FREE_ENDPOINT}?{params}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return "".join(seg[0] for seg in data[0] if seg[0])


def _safe_translate(text, lang):
    try:
        return _free_translate(text, lang)
    except Exception:
        return text


def translate_one(text, lang):
    """Translate a single string, using the cache. For ad hoc (non-HTML-pass) use."""
    if lang == "en" or not _looks_translatable(text):
        return text
    from models import db, TranslationCache
    h = _hash(lang, text)
    row = TranslationCache.query.filter_by(lang=lang, text_hash=h).first()
    if row:
        return row.translated_text
    translated = _safe_translate(text, lang)
    db.session.add(TranslationCache(lang=lang, text_hash=h, source_text=text[:4000], translated_text=translated[:4000]))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return translated


def translate_html(html_str, lang):
    """Translate every text node and whitelisted attribute in a rendered HTML page."""
    if lang == "en" or lang not in SUPPORTED_LANGUAGES:
        return html_str

    from models import db, TranslationCache

    # Protect script/style/textarea contents from being touched.
    blocks = []

    def _protect(m):
        blocks.append(m.group(1))
        # Digits-only, null-delimited — must contain no letters, or it would look like
        # ordinary translatable text and get sent to the translator itself.
        return f"\x00{len(blocks) - 1}\x00"

    protected = _SKIP_BLOCK_RE.sub(_protect, html_str)

    # Collect unique translatable strings (text nodes + whitelisted attrs).
    texts = set()
    for m in _TEXT_NODE_RE.finditer(protected):
        raw = html_lib.unescape(m.group(1)).strip()
        if _looks_translatable(raw):
            texts.add(raw)
    for m in _ATTR_RE.finditer(protected):
        raw = html_lib.unescape(m.group(2)).strip()
        if _looks_translatable(raw):
            texts.add(raw)

    if not texts:
        return html_str

    hashes = {t: _hash(lang, t) for t in texts}
    existing_rows = TranslationCache.query.filter(
        TranslationCache.lang == lang,
        TranslationCache.text_hash.in_(list(hashes.values())),
    ).all()
    translations = {row.text_hash: row.translated_text for row in existing_rows}

    misses = [t for t in texts if hashes[t] not in translations]
    if misses:
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda t: (t, _safe_translate(t, lang)), misses))
        for t, translated in results:
            h = hashes[t]
            translations[h] = translated
            db.session.add(TranslationCache(
                lang=lang, text_hash=h, source_text=t[:4000], translated_text=translated[:4000],
            ))
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    by_text = {t: translations[hashes[t]] for t in texts if hashes[t] in translations}

    def _sub_text(m):
        inner = m.group(1)
        stripped = inner.strip()
        if not stripped:
            return m.group(0)
        raw = html_lib.unescape(stripped)
        if raw in by_text:
            leading = inner[:len(inner) - len(inner.lstrip())]
            trailing = inner[len(inner.rstrip()):]
            return ">" + leading + html_lib.escape(by_text[raw]) + trailing + "<"
        return m.group(0)

    def _sub_attr(m):
        attr, val = m.group(1), m.group(2)
        raw = html_lib.unescape(val.strip())
        if raw in by_text:
            return f'{attr}="{html_lib.escape(by_text[raw])}"'
        return m.group(0)

    out = _TEXT_NODE_RE.sub(_sub_text, protected)
    out = _ATTR_RE.sub(_sub_attr, out)

    for i, block in enumerate(blocks):
        out = out.replace(f"\x00{i}\x00", block)

    out = out.replace('<html lang="en"', f'<html lang="{lang}"', 1)
    return out
