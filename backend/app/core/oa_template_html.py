"""
پاک‌سازی HTML سربرگ و پابرگ قالب نامه (اتوماسیون فاز ۲، «قالب با کد HTML»).

سازنده‌ی قالب (مجوز automation.templates) چیدمان سربرگ/پابرگ را با HTML و style درون‌خطی می‌نویسد. فهرست بسته:
- تگ‌ها: div, span, p, h1, h2, h3, strong, b, em, i, u, small, br, hr, table, thead, tbody, tr, th, td, img
- ویژگی‌ها: style (فقط ویژگی‌های CSS فهرست پایین، بدون url/expression/…)، dir، colspan/rowspan، alt؛
  img فقط با src="{{logo}}" (لوگوی همان قالب) و width/height عددی — هیچ آدرس بیرونی بارگذاری نمی‌شود.
- جای‌نگهدارها (متن ساده، در نمایش جایگزین می‌شوند): {{logo}} {{title}} {{subtitle}} {{site}} {{number}} {{date}}
  {{attachment}} {{page}} {{pages}}
- script/style/iframe/… کامل حذف؛ تگ ناشناخته حذف و متنش نگه داشته می‌شود.
"""
from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser

PLACEHOLDERS = ("logo", "title", "subtitle", "site", "number", "date", "attachment", "page", "pages")
ALLOWED_TAGS = {
    "div", "span", "p", "h1", "h2", "h3", "strong", "b", "em", "i", "u", "small", "br", "hr",
    "table", "thead", "tbody", "tr", "th", "td", "img",
}
VOID_TAGS = {"br", "hr", "img"}
DROP_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed", "noscript", "template", "svg", "math", "head",
                     "title", "xml", "select", "textarea", "button", "form", "canvas", "video", "audio", "link", "meta"}
CSS_PROPERTIES = {
    "text-align", "vertical-align", "font-size", "font-weight", "font-style", "color", "background-color",
    "border", "border-top", "border-right", "border-bottom", "border-left", "border-color", "border-width",
    "border-style", "border-radius", "border-collapse", "border-spacing",
    "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
    "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
    "width", "height", "max-width", "max-height", "min-width", "min-height",
    "display", "flex", "flex-direction", "flex-wrap", "justify-content", "align-items", "align-self", "gap",
    "line-height", "letter-spacing", "direction", "white-space", "object-fit", "text-decoration", "box-sizing",
    "table-layout", "overflow",
}
DISPLAY_VALUES = {"block", "inline", "inline-block", "flex", "inline-flex", "table", "table-row", "table-cell", "none"}
# هر چیزی که می‌تواند منبع بیرونی بارگذاری کند یا از اعلان فرار کند
_BAD_VALUE = re.compile(r"url\s*\(|expression|javascript|vbscript|@import|\\|<|>|/\*|\*/|behavior|binding", re.I)
_VALUE_OK = re.compile(r"^[\w\s#%.,()\-+'\"!؀-ۿ]*$")
MAX_INPUT = 50_000
MAX_DEPTH = 40


class TemplateHtmlError(ValueError):
    """خطای قابل نمایش (پیام فارسی)."""


def clean_style(value: str) -> str:
    out = []
    for decl in (value or "").split(";"):
        if ":" not in decl:
            continue
        prop, val = decl.split(":", 1)
        prop, val = prop.strip().lower(), val.strip()
        if prop not in CSS_PROPERTIES or not val or len(val) > 200:
            continue
        if _BAD_VALUE.search(val) or not _VALUE_OK.match(val):
            continue
        if prop == "display" and val.lower() not in DISPLAY_VALUES:
            continue
        out.append(f"{prop}: {val}")
    return "; ".join(out)


def _attrs(tag: str, attrs) -> str:
    out = []
    for name, value in attrs:
        name = (name or "").lower()
        value = (value or "").strip()
        if name == "style":
            style = clean_style(value)
            if style:
                out.append(f'style="{escape(style)}"')
        elif name == "dir" and value.lower() in ("rtl", "ltr", "auto"):
            out.append(f'dir="{value.lower()}"')
        elif name in ("colspan", "rowspan") and tag in ("th", "td") and value.isdigit() and 1 <= int(value) <= 50:
            out.append(f'{name}="{int(value)}"')
        elif name == "alt" and tag == "img":
            out.append(f'alt="{escape(value[:100])}"')
        elif name in ("width", "height") and tag == "img" and value.isdigit() and 1 <= int(value) <= 2000:
            out.append(f'{name}="{int(value)}"')
    return (" " + " ".join(out)) if out else ""


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[str] = []
        self.drop = 0

    def _open(self, tag, attrs, closing_void: bool):
        tag = tag.lower()
        if tag in DROP_CONTENT_TAGS:
            if not closing_void:
                self.drop += 1
            return
        if self.drop or tag not in ALLOWED_TAGS:
            return
        if tag == "img":
            src = next(((v or "").strip() for n, v in attrs if (n or "").lower() == "src"), "")
            if src.replace(" ", "") != "{{logo}}":
                return  # فقط لوگوی خود قالب
            self.out.append(f'<img src="{{{{logo}}}}"{_attrs(tag, attrs)}>')
            return
        if tag in VOID_TAGS:
            self.out.append(f"<{tag}{_attrs(tag, attrs)}>")
            return
        if closing_void or len(self.stack) >= MAX_DEPTH:
            return
        self.stack.append(tag)
        self.out.append(f"<{tag}{_attrs(tag, attrs)}>")

    def handle_starttag(self, tag, attrs):
        self._open(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):
        self._open(tag, attrs, True)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in DROP_CONTENT_TAGS:
            self.drop = max(0, self.drop - 1)
            return
        if self.drop or tag in VOID_TAGS or tag not in self.stack:
            return
        while self.stack:
            top = self.stack.pop()
            self.out.append(f"</{top}>")
            if top == tag:
                break

    def handle_data(self, data):
        if not self.drop and data:
            self.out.append(escape(data, quote=False))

    def result(self) -> str:
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return "".join(self.out).strip()


def sanitize_template_html(raw: str | None, label: str = "HTML") -> str:
    """HTML سربرگ/پابرگ → HTML امن. بیش از MAX_INPUT → TemplateHtmlError."""
    if not raw or not raw.strip():
        return ""
    if len(raw) > MAX_INPUT:
        raise TemplateHtmlError(f"{label} بیش از حد طولانی است (حداکثر {MAX_INPUT:,} نویسه)")
    p = _Parser()
    p.feed(raw)
    p.close()
    return p.result()
