export function isGeolocationSupported() {
  return "geolocation" in navigator;
}

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
