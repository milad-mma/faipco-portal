"""خواندن کاربرگ فارسی فرم ارزیابی؛ نتیجه فقط پس از اعتبارسنجی کامل ذخیره می‌شود."""
from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import load_workbook

from app.schemas.evaluation_content import EvaluationQuestionIn
from app.services.payroll_common import PayrollParseError
from app.services.payroll_xlsx import check_xlsx_size

HEADERS = ("دسته‌بندی", "وزن دسته", "متن سؤال", "نوع سؤال", "وزن سؤال", "اجباری", "گزینه‌ها و امتیاز", "توضیح سؤال")
TYPES = {"تک‌انتخابی": "single_choice", "چندانتخابی": "multiple_choice", "امتیازی": "rating",
         "بله/خیر": "yes_no", "متن آزاد": "text", "عدد": "number", "تاریخ": "date"}
MAX_BYTES = 2 * 1024 * 1024


class FormExcelError(ValueError):
    """خطای قابل‌نمایش به کاربر هنگام ورود فرم."""


def number(value, field, low, high):
    try:
        value = Decimal(value.replace("٫", "."))
        if value.is_finite() and low <= value <= high and value == value.quantize(Decimal(".01")):
            return float(value)
    except InvalidOperation:
        pass
    raise FormExcelError(f"«{field}» باید عددی از {low} تا {high} با حداکثر دو رقم اعشار باشد.")


def add_row(categories, values):
    title, cat_weight, text, kind, weight, required, choices, description = values
    if not title or len(title) > 255 or not text:
        raise FormExcelError("نام دسته (حداکثر ۲۵۵ نویسه) و متن سؤال را وارد کنید.")
    cat_weight = number(cat_weight, HEADERS[1], 0, 100)
    if title not in categories:
        categories[title] = dict(title=title, weight=cat_weight, sort_order=len(categories), questions=[])
    category = categories[title]
    if cat_weight != category["weight"]:
        raise FormExcelError("وزن دسته با ردیف قبلی همین دسته یکسان نیست.")
    if kind not in TYPES or required not in ("بله", "خیر"):
        raise FormExcelError("نوع سؤال و مقدار ستون اجباری را از فهرست نمونه انتخاب کنید.")
    options = []
    for line in choices.splitlines():
        if not line.strip():
            continue
        label, separator, score = line.rpartition("|")
        if not separator or not 1 <= len(label.strip()) <= 255:
            raise FormExcelError("هر گزینه باید به شکل «متن گزینه | امتیاز» در یک خط نوشته شود.")
        options.append(dict(label=label.strip(), score=number(score.strip(), "امتیاز", Decimal("-9999.99"), Decimal("9999.99")),
                            sort_order=len(options)))
    if TYPES[kind] in ("text", "number", "date") and options:
        raise FormExcelError("برای این نوع سؤال ستون گزینه‌ها را خالی بگذارید.")
    try:
        question = EvaluationQuestionIn(text=text, description=description or None, question_type=TYPES[kind],
            required=required == "بله", weight=number(weight, HEADERS[4], 0, 100),
            sort_order=len(category["questions"]), options=options)
    except FormExcelError:
        raise
    except ValueError as exc:
        raise FormExcelError("برای سؤال گزینه‌دار حداقل دو گزینه همراه امتیاز وارد کنید.") from exc
    category["questions"].append(question)


OPTION_TYPES = {"single_choice", "multiple_choice", "rating", "yes_no"}
SHEETS = {**TYPES, "بله یا خیر": "yes_no"}
DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def simple_headers(option_count):
    headers = ["سؤال"]
    for index in range(1, option_count + 1):
        suffix = str(index).translate(DIGITS)
        headers.extend([f"گزینه {suffix}", f"امتیاز {suffix}"])
    return tuple(headers)


def simple_question(values, kind):
    text, *pairs = values
    if not text:
        raise FormExcelError("سؤال را در ستون اول بنویسید.")
    options = []
    for index in range(0, len(pairs), 2):
        label, raw_score = pairs[index:index + 2]
        if not label and not raw_score:
            continue
        if not label or not raw_score or len(label) > 255:
            raise FormExcelError(f"متن و امتیاز گزینه {index // 2 + 1} را کامل کنید.")
        score = number(raw_score, "امتیاز", Decimal("-9999.99"), Decimal("9999.99"))
        options.append(dict(label=label, score=score, sort_order=len(options)))
    if kind in OPTION_TYPES and len(options) < 2:
        raise FormExcelError("حداقل دو گزینه با امتیاز وارد کنید.")
    return EvaluationQuestionIn(text=text, question_type=kind, options=options)


def read_sheet(book):
    # Files downloaded before the per-type templates still have their own weights and categories.
    legacy = "سؤال‌ها" in book.sheetnames
    names = [name for name in book.sheetnames if name in SHEETS]
    if legacy and names or not legacy and len(names) != 1:
        raise FormExcelError("فایل نمونه یکی از انواع سؤال را انتخاب کنید.")
    sheet = book["سؤال‌ها" if legacy else names[0]]
    sheet.reset_dimensions()
    rows = sheet.iter_rows()
    kind = None if legacy else SHEETS[sheet.title]
    if not legacy:
        next(rows, None)  # راهنمای کوتاه بالای جدول
    headers = tuple(cell.value for cell in next(rows, ()))
    if legacy:
        expected = HEADERS
    else:
        count = (len(headers) - 1) // 2
        if kind in OPTION_TYPES and count < 2:
            raise FormExcelError("ستون‌های گزینه و امتیاز را مطابق نمونه نگه دارید.")
        expected = simple_headers(count if kind in OPTION_TYPES else 0)
    if headers != expected:
        raise FormExcelError("عنوان ستون‌های جدول باید مطابق فایل نمونه باشد.")
    categories, questions = {}, []
    first = 2 if legacy else 3
    for index, row in enumerate(rows, first):
        if index >= first + 2000:
            raise FormExcelError("حداکثر ۲۰۰۰ ردیف سؤال مجاز است.")
        if all(cell.value is None for cell in row):
            continue
        if any(cell.data_type in ("f", "e") for cell in row):
            raise FormExcelError(f"ردیف {index} شامل فرمول یا خطای اکسل است. مقدار سلول را وارد کنید.")
        if any(cell.value is not None for cell in row[len(headers):]):
            raise FormExcelError(f"ردیف {index} دارای ستون اضافه است.")
        values = [str(c.value).strip() if c.value is not None else "" for c in row[:len(headers)]]
        values.extend([""] * (len(headers) - len(values)))
        try:
            if legacy:
                add_row(categories, values)
            else:
                questions.append(simple_question(values, kind))
        except FormExcelError as exc:
            raise FormExcelError(f"ردیف {index} — {exc}") from exc
    if not categories and not questions:
        raise FormExcelError("حداقل یک سؤال وارد کنید.")
    return list(categories.values()), questions


def read_form_excel(content):
    if len(content) > MAX_BYTES:
        raise FormExcelError("حجم فایل باید حداکثر ۲ مگابایت باشد.")
    try:
        check_xlsx_size(content, max_bytes=12 * 1024 * 1024)
    except PayrollParseError as exc:
        raise FormExcelError("فایل XLSX معتبر نیست یا حجم محتوای آن بیش از حد مجاز است.") from exc
    try:
        book = load_workbook(BytesIO(content), read_only=True, data_only=False, keep_links=False)
        try:
            return read_sheet(book)
        finally:
            book.close()
    except FormExcelError:
        raise
    except Exception as exc:
        raise FormExcelError("فایل اکسل قابل خواندن نیست. آن را با فرمت XLSX ذخیره کنید.") from exc

def combine_form_files(parsed):
    """نمونه‌های ساده در یک دسته با وزن‌های برابر قرار می‌گیرند."""
    questions = []
    for categories, rows in parsed:
        if categories:
            if len(parsed) != 1:
                raise FormExcelError("نمونه قدیمی را به‌تنهایی بارگذاری کنید.")
            return categories
        questions.extend(rows)
    if not 1 <= len(questions) <= 2000:
        raise FormExcelError("هر فرم باید بین ۱ تا ۲۰۰۰ سؤال داشته باشد.")
    share, remainder = divmod(10000, len(questions))
    for index, question in enumerate(questions):
        question.sort_order = index
        question.weight = (share + int(index < remainder)) / 100
    return [dict(title="سؤال‌های ارزیابی", weight=100, sort_order=0, questions=questions)]
