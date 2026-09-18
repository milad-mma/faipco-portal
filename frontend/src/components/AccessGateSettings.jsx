import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Card,
  CircularProgress,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { fetchAccessGateSettings, updateAccessGateSetting } from "../api/accessGate";

/**
 * ⚠️ طبق درخواست صریح کاربر: هر ترکیب «نوع اجبار × قابلیت» جداگانه
 * قابل فعال/غیرفعال‌سازی است - اگر ادمین نخواست این اجبار باشد، بتواند
 * تک‌تک یا همه را خاموش کند.
 *
 * ⚠️ پیش‌فرض همه خاموش است - این یک محدودیت است و نباید با به‌روزرسانی،
 * ناگهان همه کاربران قفل شوند.
 */
const FEATURE_LABELS = {
  payroll_receipt: "مشاهده فیش حقوقی",
  attendance_card: "مشاهده فیش کارکرد",
  attendance_report: "مشاهده گزارش تردد",
  leave_request: "ثبت درخواست مرخصی/ماموریت",
  evaluation_result: "مشاهده نتیجه ارزیابی عملکرد",
};

const GATE_LABELS = {
  unread_notices: "خواندن اطلاعیه‌ها",
  pending_evaluations: "تکمیل ارزیابی‌ها",
};

const GATES = ["unread_notices", "pending_evaluations"];
const FEATURES = [
  "payroll_receipt",
  "attendance_card",
  "attendance_report",
  "leave_request",
  "evaluation_result",
];

export default function AccessGateSettings() {
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState("");
  const [savingKey, setSavingKey] = useState(null);

  useEffect(() => {
    fetchAccessGateSettings()
      .then(setSettings)
      .catch((err) => {
        setError(err.response?.data?.detail || "دریافت تنظیمات با خطا مواجه شد.");
        setSettings([]);
      });
  }, []);

  function isEnabled(gate, feature) {
    return Boolean(settings?.find((s) => s.gate === gate && s.feature === feature)?.enabled);
  }

  async function handleToggle(gate, feature, enabled) {
    const key = `${gate}:${feature}`;
    setError("");
    setSavingKey(key);
    // ⚠️ به‌روزرسانی خوش‌بینانه - تا سوییچ بلافاصله واکنش نشان دهد؛ در
    // صورت خطا به حالت قبل برمی‌گردد.
    setSettings((prev) =>
      prev.map((s) => (s.gate === gate && s.feature === feature ? { ...s, enabled } : s))
    );
    try {
      await updateAccessGateSetting(gate, feature, enabled);
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره تنظیمات با خطا مواجه شد.");
      setSettings((prev) =>
        prev.map((s) => (s.gate === gate && s.feature === feature ? { ...s, enabled: !enabled } : s))
      );
    } finally {
      setSavingKey(null);
    }
  }

  if (settings === null) {
    return (
      <Stack alignItems="center" sx={{ py: 3 }}>
        <CircularProgress size={28} />
      </Stack>
    );
  }

  return (
    <Box>
      <Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>
        پیش‌نیازهای دسترسی
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        با فعال‌کردن هر گزینه، کاربر تا زمانی که اطلاعیه‌های خوانده‌نشده یا ارزیابی‌های انجام‌نشده خود را
        تکمیل نکند، به آن بخش دسترسی نخواهد داشت. همه گزینه‌ها به‌صورت پیش‌فرض غیرفعال هستند.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Alert severity="info" sx={{ mb: 2 }}>
        اطلاعیه‌های فیش حقوقی و فیش کارکرد در شمارش «خوانده‌نشده» حساب نمی‌شوند — وگرنه برای دیدن فیش،
        خواندن همان فیش لازم می‌شد. همچنین مدیر ارشد سامانه هرگز با این محدودیت‌ها قفل نمی‌شود.
      </Alert>

      <Card variant="outlined" sx={{ borderRadius: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>دسترسی به</TableCell>
              {GATES.map((g) => (
                <TableCell key={g} align="center">
                  مشروط به {GATE_LABELS[g]}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {FEATURES.map((f) => (
              <TableRow key={f}>
                <TableCell>{FEATURE_LABELS[f]}</TableCell>
                {GATES.map((g) => (
                  <TableCell key={g} align="center">
                    <Switch
                      size="small"
                      checked={isEnabled(g, f)}
                      disabled={savingKey === `${g}:${f}`}
                      onChange={(e) => handleToggle(g, f, e.target.checked)}
                    />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </Box>
  );
}
