/**
 * ورود/خروج‌های یک نفر در یک روز را در یک ردیف ترکیب می‌کند — ولی چون یک نفر
 * ممکن است چند بار در یک روز ورود/خروج بزند (مثلاً برای ناهار)، همه جفت‌های
 * ورود/خروج آن روز به‌صورت لیستی از Session ها نگه داشته می‌شوند، نه فقط
 * اولین ورود و آخرین خروج. گروه‌بندی بر اساس تاریخ شمسی (نمایشی) انجام
 * می‌شود، نه تاریخ خام UTC — تا دقیقاً همان روزی که کاربر می‌بیند باشد.
 */
export function groupLogsByDay(logs) {
  const dayBuckets = new Map();

  for (const log of logs) {
    const dateKey = new Date(log.created_at).toLocaleDateString("fa-IR");
    const employeeKey = log.employee_id ?? "me"; // گزارش شخصی employee_id ندارد، همه یک نفرند
    const key = `${employeeKey}__${dateKey}`;

    if (!dayBuckets.has(key)) {
      dayBuckets.set(key, {
        key,
        dateLabel: dateKey,
        employeeId: log.employee_id,
        employeeName: log.employee_name,
        personnelCode: log.personnel_code,
        events: [],
      });
    }
    dayBuckets.get(key).events.push(log);
  }

  const rows = [];
  for (const bucket of dayBuckets.values()) {
    const sortedEvents = [...bucket.events].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

    // جفت‌کردن پی‌درپی: هر «ورود» با اولین «خروج» بعدش جفت می‌شود — اگر یک
    // ورود بدون خروج بماند (هنوز داخل است) یا یک خروج بی‌جفت باشد (حالت
    // نادر)، همان‌طور ناقص نمایش داده می‌شود، نه اینکه گم شود.
    const sessions = [];
    let pendingCheckIn = null;
    for (const event of sortedEvents) {
      if (event.log_type === "check_in") {
        if (pendingCheckIn) {
          sessions.push({ checkIn: pendingCheckIn, checkOut: null });
        }
        pendingCheckIn = event;
      } else if (event.log_type === "check_out") {
        sessions.push({ checkIn: pendingCheckIn, checkOut: event });
        pendingCheckIn = null;
      }
    }
    if (pendingCheckIn) {
      sessions.push({ checkIn: pendingCheckIn, checkOut: null });
    }

    const lastEvent = sortedEvents[sortedEvents.length - 1];
    rows.push({
      key: bucket.key,
      dateLabel: bucket.dateLabel,
      employeeId: bucket.employeeId,
      employeeName: bucket.employeeName,
      personnelCode: bucket.personnelCode,
      sessions,
      sortTime: new Date(lastEvent.created_at).getTime(),
    });
  }

  return rows.sort((a, b) => b.sortTime - a.sortTime);
}
