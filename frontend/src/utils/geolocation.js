/**
 * کمک‌تابع‌های موقعیت‌یابی مرورگر (Geolocation API) با پیام‌های خطای فارسی.
 */
// خروجی: true اگر مرورگر از Geolocation پشتیبانی کند
export function isGeolocationSupported() {
  return "geolocation" in navigator;
}

/**
 * موقعیت فعلی دستگاه را می‌گیرد. ورودی: گزینه‌های Geolocation (پیش‌فرض: دقت بالا، Timeout پانزده ثانیه).
 * خروجی: Promise با { latitude, longitude, accuracyMeters }؛ در صورت رد دسترسی یا خطا با پیام فارسی reject می‌شود.
 */
export function getCurrentPosition(options = { enableHighAccuracy: true, timeout: 15000 }) {
  return new Promise((resolve, reject) => {
    if (!isGeolocationSupported()) {
      reject(new Error("مرورگر شما از موقعیت‌یابی پشتیبانی نمی‌کند."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracyMeters: position.coords.accuracy,
        });
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) {
          reject(new Error("دسترسی به موقعیت مکانی رد شد — از تنظیمات مرورگر اجازه بدهید."));
        } else {
          reject(new Error("دریافت موقعیت مکانی ناموفق بود."));
        }
      },
      options
    );
  });
}
