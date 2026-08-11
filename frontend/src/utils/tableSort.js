/**
 * ابزار کوچک و عمومی برای Sort سمت کلاینت روی جدول‌ها (بدون نیاز به تغییر API).
 * فیلدهای رشته‌ای با localeCompare فارسی، فیلدهای Boolean با فعال‌ها اول،
 * و بقیه (عدد/تاریخ) با مقایسه معمولی مرتب می‌شوند. مقادیر null/undefined
 * همیشه در انتهای جدول قرار می‌گیرند — چه صعودی و چه نزولی.
 */
function compareValues(a, b, orderBy, order) {
  const aVal = a[orderBy];
  const bVal = b[orderBy];

  const aNull = aVal == null;
  const bNull = bVal == null;
  if (aNull && bNull) return 0;
  if (aNull) return 1;
  if (bNull) return -1;

  let cmp;
  if (typeof aVal === "string" && typeof bVal === "string") {
    cmp = aVal.localeCompare(bVal, "fa");
  } else if (typeof aVal === "boolean" && typeof bVal === "boolean") {
    cmp = aVal === bVal ? 0 : aVal ? -1 : 1;
  } else if (aVal < bVal) {
    cmp = -1;
  } else if (aVal > bVal) {
    cmp = 1;
  } else {
    cmp = 0;
  }

  return order === "desc" ? -cmp : cmp;
}

export function sortRows(rows, order, orderBy) {
  if (!orderBy) return rows;
  return [...rows].sort((a, b) => compareValues(a, b, orderBy, order));
}
