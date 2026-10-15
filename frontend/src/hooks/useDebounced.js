import { useEffect, useState } from "react";

/**
 * مقدار ورودی را با تأخیر (پیش‌فرض ۳۰۰ms) برمی‌گرداند؛ برای جست‌وجوی زنده‌ی سمت سرور تا با هر حرف یک درخواست نرود.
 * ورودی: value (معمولاً متن جست‌وجو)، delay به میلی‌ثانیه. خروجی: آخرین مقدار پایدار.
 */
export default function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}
