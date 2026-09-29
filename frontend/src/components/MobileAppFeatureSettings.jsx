/**
 * کلید اصلی قابلیت «اپ اندروید» در تنظیمات سامانه.
 * خاموش = انگار قابلیت وجود ندارد: منوها، صفحه‌ها، یادآور نصب/فعال‌سازی، پیش‌نیاز «اپ اندروید و موقعیت» و
 * پایش GPS داخل اپ همه غیرفعال و API‌های /mobile پاسخ 404 می‌دهند. داده‌ها حذف نمی‌شوند.
 */
import { useEffect, useState } from "react";
import { Alert, CircularProgress, FormControlLabel, Stack, Switch, Typography } from "@mui/material";
import { fetchMobileAppFeature, saveMobileAppFeature } from "../api/mobile";
import { useAuth } from "../context/AuthContext";

export default function MobileAppFeatureSettings() {
  const { refetchUser } = useAuth();
  const [enabled, setEnabled] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchMobileAppFeature()
      .then((d) => setEnabled(Boolean(d.enabled)))
      .catch(() => setError("دریافت وضعیت ناموفق بود."));
  }, []);

  async function handleToggle(e) {
    const next = e.target.checked;
    setSaving(true);
    setError("");
    try {
      const d = await saveMobileAppFeature(next);
      setEnabled(Boolean(d.enabled));
      await refetchUser(); // منوها و صفحه‌ها بلافاصله به‌روز شوند
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره ناموفق بود.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack spacing={1}>
      <Typography variant="subtitle1" fontWeight={700}>
        قابلیت اپ اندروید
      </Typography>
      <Typography variant="body2" color="text.secondary">
        تا وقتی خاموش است، هیچ اثری از اپ اندروید در پرتال دیده نمی‌شود: منوها و صفحه‌ها، یادآور نصب و فعال‌سازی، پیش‌نیاز
        «اپ اندروید و موقعیت» و ثبت خودکار ورود و خروج غیرفعال‌اند. گوشی‌ها، رویدادها و نسخه‌های ثبت‌شده حذف نمی‌شوند و با
        روشن کردن دوباره برمی‌گردند.
      </Typography>
      {enabled === null ? (
        !error && <CircularProgress size={20} />
      ) : (
        <FormControlLabel
          control={<Switch checked={enabled} onChange={handleToggle} disabled={saving} />}
          label={enabled ? "روشن" : "خاموش"}
        />
      )}
      {error && <Alert severity="error">{error}</Alert>}
    </Stack>
  );
}
