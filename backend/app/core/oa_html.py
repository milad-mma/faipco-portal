"""
پاک‌سازی HTML متن نامه (docs/office-automation-spec.md بخش ۹.۲؛ docs/office-automation.md فاز ۲).

فهرست بسته (allowlist) — هر چیز دیگری حذف می‌شود:
- تگ‌ها: p, h2, h3, strong, em, u, s, ul, ol, li, table, thead, tbody, tr, th, td, blockquote, br, span
- ویژگی‌ها: dir (rtl/ltr/auto) روی همه؛ colspan/rowspan (۱ تا ۵۰) روی th/td؛ style فقط «text-align: right|center|left|justify»
  روی p/h2/h3/li/th/td/blockquote.
- تگ ناشناخته حذف و متنش نگه داشته می‌شود (مثلاً div/font/a از Word)؛ محتوای script/style/iframe/object/… کامل حذف می‌شود.
- همه‌ی متن‌ها escape می‌شوند؛ کامنت، CDATA، processing instruction حذف؛ خروجی همیشه HTML خوش‌ساخت (تگ‌های باز بسته می‌شوند).
پیاده‌سازی با html.parser استاندارد (بدون وابستگی) تا در همه‌جا قابل تست باشد. سرور منبع حقیقت است؛ ویرایشگر فقط راهنماست.
"""
from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser

ALLOWED_TAGS = {
    "p", "h2", "h3", "strong", "em", "u", "s", "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td",
    "blockquote", "br", "span",
}
VOID_TAGS = {"br"}
# تگ‌هایی که محتوایشان هم حذف می‌شود (نه فقط خود تگ)
DROP_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed", "noscript", "template", "svg", "math", "head",
                     "title", "xml", "select", "textarea", "button", "form", "canvas", "video", "audio"}
# معادل‌سازی تگ‌های رایج Word/مرورگر
ALIASES = {"b": "strong", "i": "em", "strike": "s", "del": "s", "h1": "h2", "h4": "h3", "h5": "h3", "h6": "h3",
           }
ALIGN_TAGS = {"p", "h2", "h3", "li", "th", "td", "blockquote"}
ALIGN_RE = re.compile(r"^\s*text-align\s*:\s*(right|center|left|justify)\s*;?\s*$", re.I)
MAX_INPUT = 2_000_000  # حدود ۲ مگابایت HTML
MAX_DEPTH = 64


class HtmlTooLarge(ValueError):
    pass


def _clean_attrs(tag: str, attrs: list[tuple[str, str | None]]) -> str:
    out = []
    for name, value in attrs:
        name = (name or "").lower()
        value = (value or "").strip()
        if name == "dir" and value.lower() in ("rtl", "ltr", "auto"):
            out.append(f'dir="{value.lower()}"')
        elif name in ("colspan", "rowspan") and tag in ("th", "td") and value.isdigit() and 1 <= int(value) <= 50:
            out.append(f'{name}="{int(value)}"')
        elif name == "style" and tag in ALIGN_TAGS:
            # فقط یک اعلان text-align؛ در style چندگانه‌ی Word همان یکی برداشته می‌شود
            for decl in value.split(";"):
                m = ALIGN_RE.match(decl)
                if m:
                    out.append(f'style="text-align: {m.group(1).lower()}"')
                    break
    return (" " + " ".join(out)) if out else ""


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[str] = []
        self.drop_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in DROP_CONTENT_TAGS:
            self.drop_depth += 1
            return
        if self.drop_depth:
            return
        tag = ALIASES.get(tag, tag)
        if tag not in ALLOWED_TAGS:
            return
        if tag in VOID_TAGS:
            self.out.append("<br>")
            return
        if len(self.stack) >= MAX_DEPTH:
            return
        # جدول: فقط ساختار معتبر (tr داخل table/thead/tbody، td/th داخل tr)
        if tag in ("tr",) and not any(t in ("table", "thead", "tbody") for t in self.stack):
            return
        if tag in ("td", "th") and (not self.stack or "tr" not in self.stack):
            return
        if tag in ("thead", "tbody") and "table" not in self.stack:
            return
        if tag == "li" and not any(t in ("ul", "ol") for t in self.stack):
            tag = "p"
        self.stack.append(tag)
        self.out.append(f"<{tag}{_clean_attrs(tag, attrs)}>")

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if self.drop_depth or tag in DROP_CONTENT_TAGS:
            return
        if ALIASES.get(tag, tag) == "br":
            self.out.append("<br>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in DROP_CONTENT_TAGS:
            if self.drop_depth:
                self.drop_depth -= 1
            return
        if self.drop_depth:
            return
        tag = ALIASES.get(tag, tag)
        if tag not in ALLOWED_TAGS or tag in VOID_TAGS or tag not in self.stack:
            return
        while self.stack:
            top = self.stack.pop()
            self.out.append(f"</{top}>")
            if top == tag:
                break

    def handle_data(self, data):
        if not self.drop_depth and data:
            self.out.append(escape(data, quote=False))

    def handle_comment(self, data):
        pass

    def handle_decl(self, decl):
        pass

    def handle_pi(self, data):
        pass

    def unknown_decl(self, data):
        pass

    def result(self) -> str:
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return "".join(self.out)


def sanitize_html(raw: str | None) -> str:
    """HTML ورودی کاربر → HTML امن با فهرست بسته. ورودی بزرگ‌تر از MAX_INPUT → HtmlTooLarge."""
    if not raw:
        return ""
    if len(raw) > MAX_INPUT:
        raise HtmlTooLarge("متن نامه بیش از حد طولانی است")
    s = _Sanitizer()
    s.feed(raw)
    s.close()
    html = s.result()
    # پاراگراف‌های خالی پشت‌سرهم (paste از Word) به یکی کاهش می‌یابد
    html = re.sub(r"(?:<p>\s*</p>){3,}", "<p></p><p></p>", html)
    return html.strip()


def plain_text(html: str) -> str:
    """متن خالص (برای جست‌وجو و پیش‌نمایش کوتاه)."""

    class _T(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []

        def handle_data(self, data):
            self.parts.append(data)

        def handle_starttag(self, tag, attrs):
            if tag in ("p", "br", "li", "tr", "h2", "h3"):
                self.parts.append(" ")

    t = _T()
    t.feed(html or "")
    return re.sub(r"\s+", " ", "".join(t.parts)).strip()
