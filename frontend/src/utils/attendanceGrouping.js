/**
 * ورود/خروج‌های یک نفر در یک روز را در یک ردیف ترکیب می‌کند — اولین ورود و
 * آخرین خروج همان روز (اگر به‌هر دلیلی چند بار ثبت زده باشد).
 * گروه‌بندی بر اساس تاریخ شمسی (نمایشی) انجام می‌شود، نه تاریخ خام UTC —
 * تا دقیقاً همان روزی که کاربر می‌بیند گروه‌بندی هم بر همان اساس باشد.
 */
export function groupLogsByDay(logs) {
  const groups = new Map();

  for (const log of logs) {
    const dateKey = new Date(log.created_at).toLocaleDateString("fa-IR");
    const employeeKey = log.employee_id ?? "me"; // گزارش شخصی employee_id ندارد، همه یک نفرند
    const key = `${employeeKey}__${dateKey}`;

    if (!groups.has(key)) {
      groups.set(key, {
        key,
        dateLabel: dateKey,
        employeeId: log.employee_id,
        employeeName: log.employee_name,
        personnelCode: log.personnel_code,
        checkIn: null,
        checkOut: null,
        sortTime: new Date(log.created_at).getTime(),
      });
    }
    const group = groups.get(key);
    group.sortTime = Math.max(group.sortTime, new Date(log.created_at).getTime());

    if (log.log_type === "check_in") {
      if (!group.checkIn || new Date(log.created_at) < new Date(group.checkIn.created_at)) {
        group.checkIn = log;
      }
    } else if (log.log_type === "check_out") {
      if (!group.checkOut || new Date(log.created_at) > new Date(group.checkOut.created_at)) {
        group.checkOut = log;
      }
    }
  }

  return Array.from(groups.values()).sort((a, b) => b.sortTime - a.sortTime);
}
