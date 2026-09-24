// Cache سبک «نمایش فوری آخرین داده، سپس تازه‌سازی» (stale-while-revalidate) در حافظه‌ی تب.
// هدف: وقتی کاربر بین صفحه‌ها جابه‌جا می‌شود (داشبورد ← گزارش ← داشبورد)، داده‌ی قبلی
// بلافاصله نمایش داده شود و درخواست تازه در پس‌زمینه جایگزینش کند؛ به‌جای اسپینر در هر بار ورود.
// داده فقط در حافظه‌ی همین تب است (نه localStorage) و با عوض شدن کاربر کاملاً پاک می‌شود.

const store = new Map(); // key -> { data, at }
const inflight = new Map(); // key -> Promise؛ درخواست هم‌زمان تکراری برای یک کلید فقط یک‌بار ارسال می‌شود
let owner = null; // شناسه‌ی کاربر صاحب داده‌ها

// AuthContext با هر تغییر کاربر (ورود، خروج، تعویض حساب) این را صدا می‌زند
export function setCacheOwner(userId) {
  const next = userId ?? null;
  if (next !== owner) {
    store.clear();
    inflight.clear();
    owner = next;
  }
}

// پاک کردن کامل (مثلاً بعد از خروج)
export function clearApiCache() {
  store.clear();
  inflight.clear();
}

// حذف یک یا چند کلید (مثلاً بعد از ثبت درخواست جدید که فهرست را عوض می‌کند)
export function invalidateCache(...keys) {
  for (const k of keys) {
    store.delete(k);
    inflight.delete(k);
  }
}

// آخرین داده‌ی ذخیره‌شده برای کلید (یا undefined)
export function peekCache(key) {
  return store.get(key)?.data;
}

/**
 * اگر داده‌ی قبلی برای key هست، همان لحظه onData(cached, true) صدا زده می‌شود؛ سپس fetcher اجرا
 * و با پاسخ تازه onData(fresh, false) صدا زده می‌شود. خطای fetcher به caller برمی‌گردد (Promise رد می‌شود).
 * maxAgeMs: اگر داده‌ی موجود جوان‌تر از این باشد درخواست تازه ارسال نمی‌شود (پیش‌فرض ۰ = همیشه تازه‌سازی).
 */
export function swr(key, fetcher, onData, { maxAgeMs = 0 } = {}) {
  const hit = store.get(key);
  if (hit) {
    onData(hit.data, true);
    if (maxAgeMs && Date.now() - hit.at < maxAgeMs) return Promise.resolve(hit.data);
  }
  const requestOwner = owner;
  let p = inflight.get(key);
  if (!p) {
    p = Promise.resolve()
      .then(fetcher)
      .then((data) => {
        // اگر در این فاصله کاربر عوض شده، پاسخ ذخیره نمی‌شود
        if (owner === requestOwner) store.set(key, { data, at: Date.now() });
        return data;
      })
      .finally(() => {
        if (inflight.get(key) === p) inflight.delete(key);
      });
    inflight.set(key, p);
  }
  return p.then((data) => {
    onData(data, false);
    return data;
  });
}
