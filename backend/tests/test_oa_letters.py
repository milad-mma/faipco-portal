"""تست پاک‌سازی HTML نامه و قواعد قالب (اتوماسیون فاز ۲)."""

from app.core.oa_html import HtmlTooLarge, plain_text, sanitize_html
from app.core import oa_letter_rules as r


def _raises(exc, fn, *a):
    try:
        fn(*a)
    except exc as e:
        return str(e)
    raise AssertionError(f"expected {exc.__name__}")


def test_allowed_markup_survives():
    html = ('<h2 dir="rtl">عنوان</h2><p style="text-align: center">متن <strong>پررنگ</strong> <em>کج</em> <u>زیر</u></p>'
            '<ul><li>یک</li><li>دو</li></ul><blockquote>نقل</blockquote>'
            '<table><tbody><tr><th colspan="2">سر</th></tr><tr><td>۱</td><td rowspan="1">۲</td></tr></tbody></table><p>a<br>b</p>')
    out = sanitize_html(html)
    for frag in ('<h2 dir="rtl">', 'style="text-align: center"', "<strong>", "<em>", "<u>", "<ul><li>",
                 "<blockquote>", '<th colspan="2">', '<td rowspan="1">', "a<br>b"):
        assert frag in out, frag


def test_xss_vectors_removed():
    vectors = [
        '<script>alert(1)</script><p>ok</p>',
        '<img src=x onerror=alert(1)>',
        '<p onclick="alert(1)">x</p>',
        '<a href="javascript:alert(1)">لینک</a>',
        '<svg><script>alert(1)</script></svg>',
        '<iframe src="https://evil"></iframe>',
        '<p style="background:url(javascript:alert(1))">x</p>',
        '<p style="text-align:center; position:fixed">x</p>',
        '<style>body{display:none}</style>',
        '<math><mtext><img src=x onerror=alert(1)></mtext></math>',
        '<!-- <script>alert(1)</script> -->',
        '<p>&lt;script&gt;</p>',
        '<object data="x.swf"></object><embed src="x">',
        '<form action="/x"><input name=a></form>',
        '<td>بدون جدول</td><tr><td>x</td></tr>',
        '<p dir="javascript:x" colspan="999">x</p>',
    ]
    for v in vectors:
        out = sanitize_html(v)
        low = out.lower()
        for bad in ("<script", "onerror", "onclick", "javascript:", "<img", "<iframe", "<svg", "<style", "<object",
                    "<embed", "<form", "<input", "position", "background", "<a ", "<math", "<td", "<tr"):
            assert bad not in low, (v, out)
    assert sanitize_html('<p>&lt;script&gt;</p>') == "<p>&lt;script&gt;</p>"
    assert sanitize_html('<p style="text-align:center; position:fixed">x</p>') == '<p style="text-align: center">x</p>'


def test_word_paste_normalized():
    word = ('<div class="WordSection1"><p class="MsoNormal" style="margin:0;text-align:justify;font-family:Tahoma">'
            '<b>بند</b> <i>یک</i><o:p></o:p></p><h1>تیتر</h1><font color=red>قرمز</font></div>')
    out = sanitize_html(word)
    assert out.startswith("<p style") and "<p><p" not in out
    assert "<strong>بند</strong>" in out and "<em>یک</em>" in out and "<h2>تیتر</h2>" in out
    assert 'style="text-align: justify"' in out and "class=" not in out and "font" not in out and "قرمز" in out


def test_wellformed_and_limits():
    assert sanitize_html("<p><strong>باز") == "<p><strong>باز</strong></p>"
    assert sanitize_html("</p>متن</strong>") == "متن"
    assert sanitize_html("") == "" and sanitize_html(None) == ""
    _raises(HtmlTooLarge, sanitize_html, "x" * 2_000_001)
    deep = "<blockquote>" * 200 + "x"
    assert sanitize_html(deep).count("<blockquote>") <= 64
    assert plain_text("<h2>الف</h2><p>ب<br>پ</p>") == "الف ب پ"


def test_layout_validation():
    d = r.default_layouts()
    assert set(d) == {"A4", "A5"} and d["A5"]["font_size_pt"] < d["A4"]["font_size_pt"]
    ok = r.validate_layouts({"A4": {"header": {"title": " شرکت ", "logo_file_id": "7"}, "extra": 1}, "A5": {}})
    assert ok["A4"]["header"]["title"] == "شرکت" and ok["A4"]["header"]["logo_file_id"] == 7 and "extra" not in ok["A4"]
    assert "حاشیه" in _raises(r.LetterRulesError, r.validate_layout, "A4", {"margins_mm": {"top": 2}})
    assert "چپ و راست" in _raises(r.LetterRulesError, r.validate_layout, "A5",
                                   {"margins_mm": {"left": 50, "right": 50}})
    assert "جای کافی" in _raises(r.LetterRulesError, r.validate_layout, "A5",
                                  {"margins_mm": {"top": 60, "bottom": 60}, "header": {"height_mm": 90}})
    _raises(r.LetterRulesError, r.validate_layout, "A3", {})
    w, h = r.body_area_mm("A4", ok["A4"])
    assert w == 170 and h == 297 - 15 - 15 - 35 - 12


def test_content_hash_detects_effective_changes():
    base = dict(subject="س", body_html="<p>x</p>", paper_size="A4", template_version_id=1)
    h = r.content_hash(**base)
    assert h == r.content_hash(**base)
    assert h != r.content_hash(**{**base, "paper_size": "A5"})
    assert h != r.content_hash(**{**base, "body_html": "<p>y</p>"})
    assert h != r.content_hash(**{**base, "template_version_id": 2})
    assert r.content_hash(**base, recipients=[2, 1]) == r.content_hash(**base, recipients=[1, 2])
    assert r.content_hash(**base, attachments=[1, 2]) != r.content_hash(**base, attachments=[2, 1])  # ترتیب پیوست مؤثر است
    assert r.clean_subject("  الف\nب ") == "الف ب"
