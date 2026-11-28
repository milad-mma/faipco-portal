import { useEffect, useState } from "react";
import { Alert, Button, Card, Stack, Typography } from "@mui/material";
import { enablePushNotifications, getPushRegistrationStatus, observePushRegistration } from "../utils/push";

const labels = {
  granted: "مجاز", denied: "مسدود", prompt: "در انتظار اجازه", default: "در انتظار اجازه",
  unsupported: "در این مرورگر در دسترس نیست", unknown: "نیاز به بررسی",
};

export default function WebPermissions() {
  const [location, setLocation] = useState(navigator.geolocation ? "unknown" : "unsupported");
  const [push, setPush] = useState(getPushRegistrationStatus);
  const [message, setMessage] = useState("");
  const [locating, setLocating] = useState(false);
  const appleMobile = /iPhone|iPad|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const installed = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone;

  useEffect(() => observePushRegistration(setPush), []);
  useEffect(() => {
    let active = true;
    let permission;
    const update = () => { if (active && permission) setLocation(permission.state); };
    async function read() {
      if (!navigator.geolocation || !navigator.permissions) return;
      try {
        const result = await navigator.permissions.query({ name: "geolocation" });
        if (!active) return;
        if (permission) permission.onchange = null;
        permission = result;
        permission.onchange = update;
        update();
      } catch { /* Some browsers only expose the status after a user request. */ }
    }
    read();
    window.addEventListener("focus", read);
    return () => {
      active = false;
      if (permission) permission.onchange = null;
      window.removeEventListener("focus", read);
    };
  }, []);

  function requestLocation() {
    setMessage("");
    setLocating(true);
    navigator.geolocation.getCurrentPosition(() => {
      setLocation("granted");
      setLocating(false);
    }, error => {
      setLocating(false);
      if (error.code === 1) setLocation("denied");
      else setMessage("موقعیت دریافت نشد. موقعیت‌یاب دستگاه را بررسی کنید و دوباره تلاش کنید.");
    }, { timeout: 10000 });
  }

  return <Card variant="outlined" sx={{ p: 2.5, mb: 2 }}>
    <Stack spacing={1.5} alignItems="flex-start">
      <Typography fontWeight={700}>موقعیت هنگام استفاده از وب‌اپ</Typography>
      <Typography>{labels[location]}</Typography>
      {["unknown", "prompt"].includes(location) && <Button disabled={locating} onClick={requestLocation}>
        {locating ? "در حال بررسی…" : "درخواست دسترسی به موقعیت"}
      </Button>}
      <Typography fontWeight={700}>اعلان‌های این وب‌اپ</Typography>
      <Typography>{push.registered ? "برای این حساب و مرورگر ثبت شده" : labels[push.permission]}</Typography>
      {push.permission === "unsupported" && appleMobile && !installed && <Typography>
        در iOS ۱۶٫۴ یا بالاتر، از منوی اشتراک‌گذاری «افزودن به صفحهٔ اصلی» را انتخاب کنید و پرتال را از آیکن آن باز کنید.
      </Typography>}
      {["default", "granted"].includes(push.permission) && !push.registered &&
        <Button disabled={push.checking} onClick={async () => {
          setMessage("");
          try { await enablePushNotifications(); } catch (error) { setMessage(error.message); }
        }}>{push.checking ? "در حال ثبت…" : "فعال‌سازی اعلان‌های وب‌اپ"}</Button>}
      {(location === "denied" || push.permission === "denied") && <Typography>
        برای تغییر دسترسی مسدودشده، تنظیمات مجوزهای این سایت یا وب‌اپ را در دستگاه باز کنید.
      </Typography>}
      {message && <Alert severity="warning">{message}</Alert>}
    </Stack>
  </Card>;
}
