"""
منطق خالص تقسیم درخت واحدهای سازمانی بین سایت‌ها (بدون دیتابیس، قابل تست).

وقتی چند سایت پرتال پرسنلشان را از یک دیتابیس منبع مشترک (مثلاً یک کاراوب)
می‌خوانند، هر سایت یک یا چند «واحد ریشه» دارد. قاعده‌ی تعلق:

    هر واحد متعلق به سایتی است که نزدیک‌ترین ریشه‌ی بالادستش (یا خودش) را دارد.

یعنی از هر واحد با ستون «واحد بالادست» (مثل Sections.TFather) بالا می‌رویم
و اولین واحدی که ریشه‌ی یک سایت است، سایت آن واحد را تعیین می‌کند. واحدی که
به هیچ ریشه‌ای نرسد «بی‌سایت» است (None).

این قاعده هم ساختار «چند ریشه‌ی جدا» را پوشش می‌دهد و هم ساختار تودرتو
(مثلاً «مدیریت» زیر «مدیریت (HO)»): زیرشاخه‌ی داخلی به ریشه‌ی نزدیک‌ترش می‌رسد.
"""
from __future__ import annotations


class OrgTreeError(ValueError):
    """خطای تنظیمات ریشه‌ها (مثلاً یک واحد ریشه‌ی دو سایت)."""


def normalize_code(value) -> str | None:
    """کد واحد را به رشته‌ی trim‌شده تبدیل می‌کند (عدد اعشاری صحیح مثل 12.0 → «12»)؛ None یا رشته‌ی خالی → None."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # 12.0 → "12" (درایورهای عددی)
    text = str(value).strip()
    return text or None


def build_parent_map(rows: list[dict], id_column: str, parent_column: str) -> dict[str, str | None]:
    """
    ورودی: ردیف‌های خام جدول واحدها و نام ستون کد و ستون واحد بالادست.
    خروجی: دیکشنری «کد واحد → کد واحد بالادست (یا None برای واحد بدون بالادست)».
    ردیف‌های بدون کد نادیده گرفته می‌شوند؛ بالادستی که برابر خود واحد است None حساب می‌شود.
    """
    parents: dict[str, str | None] = {}
    for row in rows:
        code = normalize_code(row.get(id_column))
        if code is None:
            continue
        parent = normalize_code(row.get(parent_column))
        parents[code] = parent if parent != code else None
    return parents


def validate_roots(roots_by_site: dict[int, set[str]]) -> None:
    """
    بررسی می‌کند هیچ واحدی ریشه‌ی بیش از یک سایت نباشد؛ در غیر این صورت OrgTreeError
    با فهرست واحدهای تکراری می‌دهد.
    """
    owner: dict[str, int] = {}
    duplicates: set[str] = set()
    for site_id, roots in roots_by_site.items():
        for code in roots:
            if code in owner and owner[code] != site_id:
                duplicates.add(code)
            owner.setdefault(code, site_id)
    if duplicates:
        raise OrgTreeError("این واحدها ریشه‌ی بیش از یک سایت تعیین شده‌اند: " + "، ".join(sorted(duplicates)))


def assign_units_to_sites(
    parents: dict[str, str | None], roots_by_site: dict[int, set[str]]
) -> dict[str, int | None]:
    """
    ورودی: نقشه‌ی بالادست واحدها و ریشه‌های هر سایت.
    خروجی: دیکشنری «کد واحد → شناسه سایت (یا None اگر زیر هیچ ریشه‌ای نیست)» برای همه‌ی واحدها.
    ریشه‌ای که در جدول واحدها وجود ندارد هم در خروجی می‌آید (به سایت خودش).
    حلقه در درخت (داده‌ی خراب منبع) باعث قفل نمی‌شود: مسیر حلقه‌دار بی‌سایت حساب می‌شود.
    """
    validate_roots(roots_by_site)
    root_owner = {code: site_id for site_id, roots in roots_by_site.items() for code in roots}
    result: dict[str, int | None] = {}

    for start in set(parents) | set(root_owner):
        if start in result:
            continue
        # بالا رفتن از واحد تا رسیدن به یک ریشه، یک واحد از قبل حل‌شده، بالای درخت یا حلقه
        path: list[str] = []
        visited: set[str] = set()
        current: str | None = start
        owner: int | None = None
        while current is not None:
            if current in root_owner:
                owner = root_owner[current]
                break
            if current in result:
                owner = result[current]
                break
            if current in visited:  # حلقه در داده‌ی منبع
                owner = None
                break
            visited.add(current)
            path.append(current)
            current = parents.get(current)
        # همه‌ی واحدهای مسیر همان سایتِ پیداشده را می‌گیرند (کش برای واحدهای بعدی)
        for code in path:
            result[code] = owner
        if start in root_owner:
            result[start] = root_owner[start]
    return result


def descendants_count(parents: dict[str, str | None], code: str) -> int:
    """تعداد همه‌ی زیرواحدهای (مستقیم و غیرمستقیم) یک واحد؛ برای نمایش در پیش‌نمایش تنظیمات."""
    children: dict[str, list[str]] = {}
    for child, parent in parents.items():
        if parent is not None:
            children.setdefault(parent, []).append(child)
    count = 0
    stack = list(children.get(code, []))
    seen: set[str] = set()
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        count += 1
        stack.extend(children.get(node, []))
    return count
