import { Alert, Button } from "@mui/material";
import { useNavigate } from "react-router-dom";

/**
 * ⚠️ طبق تصمیم صریح کاربر: محدودیت هم در UI و هم سمت سرور اعمال می‌شود.
 * این کامپوننت لایه UI است - **قبل از** کلیک هشدار می‌دهد و مسیر رفع را
 * نشان می‌دهد، تا کاربر با یک ۴۰۳ خشک روبه‌رو نشود.
 *
 * سمت سرور همچنان مستقل بررسی می‌کند، پس این فقط تجربه کاربری است، نه
 * خودِ کنترل دسترسی - با دستکاری فرانت‌اند دور زدنی نیست.
 */
export default function AccessGateNotice({ status, feature }) {
  const navigate = useNavigate();

  const gate = status?.blocked_features?.[feature];
  if (!gate) return null;

  const isNotices = gate === "unread_notices";
  const count = isNotices ? status.unread_notices : status.pending_evaluations;

  return (
    <Alert
      severity="warning"
      sx={{ mb: 2 }}
      action={
        <Button
          color="inherit"
          size="small"
          onClick={() => navigate(isNotices ? "/notices" : "/my-performance?tab=1")}
        >
          {isNotices ? "مشاهده اطلاعیه‌ها" : "انجام ارزیابی‌ها"}
        </Button>
      }
    >
      {isNotices
        ? `برای دسترسی به این بخش، ابتدا باید ${count.toLocaleString("fa-IR")} اطلاعیه خوانده‌نشده خود را مطالعه کنید.`
        : `برای دسترسی به این بخش، ابتدا باید ${count.toLocaleString("fa-IR")} ارزیابی انجام‌نشده خود را تکمیل کنید.`}
    </Alert>
  );
}
