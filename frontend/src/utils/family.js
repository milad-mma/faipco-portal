// ابزارهای مشترک فرم «مشخصات خانوادگی» (هم‌سو با backend/app/core/family_rules.py).
import { gregorianToJalali } from "./jalaliDate";

export const CHILD_TYPES = ["son", "daughter"];

// ترتیب ستون‌های هر نوع عضو در فرم
export const MEMBER_COLUMNS = {
  spouse: ["father_name", "national_id", "birth_certificate_no", "birth_date", "marriage_certificate_no", "mobile",
    "is_employed", "employer_name", "is_insured", "receives_child_allowance", "is_disabled"],
  son: ["birth_date", "national_id", "birth_certificate_no", "relation", "other_parent_name", "custody", "is_disabled",
    "is_student", "education_level", "school_name", "student_cert_expiry", "is_employed"],
  daughter: ["birth_date", "national_id", "birth_certificate_no", "relation", "other_parent_name", "custody", "is_disabled",
    "is_married", "marriage_date", "is_employed", "is_student", "education_level", "school_name", "student_cert_expiry"],
}; // prettier-ignore
export const MEMBER_LABEL = { spouse: "همسر", son: "پسر", daughter: "دختر" };
export const STATUS_COLOR = { none: "default", draft: "default", pending: "warning", approved: "success", rejected: "error", returned: "info" };

// کلید تنظیم یک ستون عضو: همسر ← spouse.x ؛ پسر/دختر ← اول بخش اختصاصی، سپس بخش مشترک child
export function memberFieldKey(fieldDefs, memberType, column) {
  const keys = new Set(fieldDefs.map((f) => f.key));
  if (memberType === "spouse") return keys.has(`spouse.${column}`) ? `spouse.${column}` : null;
  for (const section of [memberType, "child"]) {
    if (keys.has(`${section}.${column}`)) return `${section}.${column}`;
  }
  return null;
}

// سن کامل (سال) از تاریخ تولد «YYYY/MM/DD» تا امروز؛ تاریخ نامعتبر → null
export function ageFromJalali(value) {
  const m = /^(\d{4})\/(\d{1,2})\/(\d{1,2})$/.exec(toEn(value || ""));
  if (!m) return null;
  const t = gregorianToJalali(new Date());
  let age = t.jy - Number(m[1]);
  if (t.jm < Number(m[2]) || (t.jm === Number(m[2]) && t.jd < Number(m[3]))) age -= 1;
  return age;
}

// پسر/دختری که به سن تعیین‌شده توسط منابع انسانی (پیش‌فرض ۱۸) رسیده یا از آن گذشته است.
// studyAges: { son: سن سقف پسر، daughter: سن پرسیدن تحصیل دختر } از تنظیمات فرم
export function childReachedStudyAge(member, studyAges) {
  const limit = studyAges?.[member?.member_type];
  if (!CHILD_TYPES.includes(member?.member_type)) return false;
  const age = ageFromJalali(member.birth_date);
  return age !== null && age >= (limit || 18);
}

const STUDY_COLUMNS = ["is_student", "education_level", "school_name", "student_cert_expiry"];

// سن‌های تحصیل از تنظیمات فرم کارمند
export const studyAgesOf = (formSettings) => ({ son: formSettings?.son_max_age, daughter: formSettings?.daughter_study_age });

// فیلدهای وابسته فقط وقتی پاسخ والد «بله» است نمایش داده می‌شوند؛ سؤال‌های تحصیل فرزند فقط بالای سن تعیین‌شده.
// تاریخ اعتبار گواهی تحصیل همراه خود گواهی (فرزند محصل بالای سن تعیین‌شده، و مدرک مخفی نشده باشد)
export function memberFieldApplies(memberType, column, member, formSettings) {
  const studyAges = studyAgesOf(formSettings);
  if (CHILD_TYPES.includes(memberType) && STUDY_COLUMNS.includes(column) && !childReachedStudyAge(member, studyAges)) return false;
  if (column === "student_cert_expiry") return member.is_student === true && formSettings?.documents?.student_certificate?.mode !== "hidden";
  if (column === "employer_name" || column === "is_insured") return member.is_employed === true;
  if (column === "education_level" || column === "school_name") return member.is_student === true;
  if (column === "marriage_date" && memberType === "daughter") return member.is_married === true;
  return true;
}

// آیا نوع مدرک با پاسخ‌های فرم موضوعیت دارد؟ member=null یعنی مدرک کل پرونده
export function documentCondition(docType, form, member, studyAges) {
  const marital = form.marital_status;
  if (docType === "marriage_certificate") return marital === "married";
  if (docType === "separation_document") return marital === "divorced" || marital === "widowed";
  if (docType === "head_of_household") return form.is_head_of_household === true;
  if (!member) return false;
  const t = member.member_type;
  if (docType === "birth_certificate") return true;
  if (docType === "student_certificate") return childReachedStudyAge(member, studyAges) && member.is_student === true;
  if (docType === "disability_certificate") return member.is_disabled === true;
  if (docType === "custody_ruling") return CHILD_TYPES.includes(t) && marital === "divorced" && member.custody === "employee";
  return false;
}

// انواع مدرک قابل آپلود برای پرونده (member=null) یا یک عضو، بر اساس تنظیمات (مخفی‌ها حذف)
export function allowedDocuments(formSettings, form, member) {
  const scope = member ? "member" : "profile";
  return Object.entries(formSettings.doc_types)
    .filter(([key, spec]) => spec.scope === scope && formSettings.documents[key]?.mode !== "hidden" && documentCondition(key, form, member, studyAgesOf(formSettings)))
    .map(([key]) => key);
}

// نمایش بله/خیر/نامشخص
export const yesNo = (v) => (v === true ? "بله" : v === false ? "خیر" : "—");

// ارقام فارسی/عربی → انگلیسی
export const toEn = (v) =>
  String(v ?? "")
    .replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d))
    .replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d));

// ورودی تاریخ شمسی: فقط رقم و «/»، حداکثر ۱۰ کاراکتر؛ بعد از ۴ و ۶ رقم «/» خودکار
export function formatJalaliInput(value) {
  const digits = toEn(value).replace(/[^\d]/g, "").slice(0, 8);
  if (digits.length <= 4) return digits;
  if (digits.length <= 6) return `${digits.slice(0, 4)}/${digits.slice(4)}`;
  return `${digits.slice(0, 4)}/${digits.slice(4, 6)}/${digits.slice(6)}`;
}

// یک Blob را با نام داده‌شده دانلود می‌کند
export function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
