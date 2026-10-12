"""همه‌ی قالب‌های اعلان کلید یکتا، متن پیش‌فرض و متغیرهای موجود در متن دارند."""
from app.services import notification_templates as N


def test_templates_well_formed():
    seen = set()
    for module, items in N.TEMPLATES.items():
        for key, t in items.items():
            assert key.startswith(module + ".") and key not in seen
            seen.add(key)
            assert t["default"].strip() and len(t["default"]) <= N.MAX_TEXT
            for var in t.get("vars", {}):
                assert "{" + var + "}" in t["default"]


def test_fill_replaces_only_known_vars():
    assert N._fill("وام {amount} ریال {x}", {"amount": "1,000"}) == "وام 1,000 ریال {x}"
