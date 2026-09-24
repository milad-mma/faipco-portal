/**
 * کارت «جابه‌جایی بین سایت‌ها» در صفحه‌ی مدیریت دسترسی.
 *
 * وقتی Sync پرسنلی را از یک سایت به سایت دیگر منتقل می‌کند (واحدش در کاراوب به
 * شاخه‌ی سایت دیگری رفته)، نقش‌های سایتی و سرپرستی واحدهای سایت قبلی او خودکار
 * حذف نمی‌شوند. این کارت فهرست این افراد را با نقش‌ها و سرپرستی‌های فعلی‌شان نشان
 * می‌دهد تا مدیر تصمیم بگیرد کدام بماند و کدام حذف شود، و بعد مورد را «بررسی شد» بزند.
 * اگر موردی در انتظار بازبینی نباشد، چیزی رندر نمی‌شود.
 *
 * ورودی: onOpenAccess(employee) برای باز کردن دیالوگ دسترسی همان پرسنل، و refreshKey
 * که با تغییرش فهرست دوباره بارگذاری می‌شود.
 */
import { useEffect, useState } from "react";
import { Alert, Box, Button, Card, Chip, Stack, Typography } from "@mui/material";
import SwapHorizOutlinedIcon from "@mui/icons-material/SwapHorizOutlined";
import { fetchPendingSiteTransfers, markSiteTransferReviewed } from "../api/users";
import { roleDisplayName } from "../utils/roleLabels";

export default function SiteTransferReviewCard({ onOpenAccess, refreshKey }) {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null); // موردی که درخواست «بررسی شد» آن در جریان است

  // بارگذاری فهرست موارد بازبینی‌نشده (در شروع و بعد از هر تغییر refreshKey)
  useEffect(() => {
    fetchPendingSiteTransfers()
      .then(setItems)
      .catch(() => setError("دریافت فهرست جابه‌جایی‌ها با خطا مواجه شد."));
  }, [refreshKey]);

  // یک مورد را بازبینی‌شده علامت می‌زند و از فهرست حذف می‌کند
  async function handleReviewed(id) {
    setBusyId(id);
    try {
      await markSiteTransferReviewed(id);
      setItems((prev) => prev.filter((t) => t.id !== id));
    } catch {
      setError("ثبت بازبینی با خطا مواجه شد.");
    } finally {
      setBusyId(null);
    }
  }

  if (!items.length && !error) return null;

  return (
    <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3, borderColor: "warning.main" }}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
        <SwapHorizOutlinedIcon color="warning" />
        <Typography variant="h6" fontWeight={700}>
          جابه‌جایی بین سایت‌ها ({items.length.toLocaleString("fa-IR")})
        </Typography>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        این افراد در همگام‌سازی به سایت دیگری منتقل شده‌اند. نقش‌ها، سرپرستی‌ها و مسئولیت‌های سایت قبلی‌شان
        (نارنجی) هنوز برقرار است؛ نقش و سرپرستی را از «دسترسی‌ها» و مسئولیت‌های مرخصی/ارزیابی را از صفحه‌ی تنظیمات
        همان بخش حذف کنید و سپس «بررسی شد» را بزنید.
      </Typography>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Stack spacing={1.5}>
        {items.map((t) => (
          <Box key={t.id} sx={{ p: 1.5, border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
            {/* نام، مسیر جابه‌جایی و تاریخ */}
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} justifyContent="space-between">
              <Typography fontWeight={700}>
                {t.first_name} {t.last_name}{" "}
                <Typography component="span" variant="caption" color="text.secondary">
                  ({t.personnel_code})
                </Typography>
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {t.from_site_name || "—"} ← {t.to_site_name || "—"} ·{" "}
                {new Date(t.transferred_at).toLocaleDateString("fa-IR")}
              </Typography>
            </Stack>

            {/* نقش‌ها و سرپرستی‌های فعلی؛ موارد سایت قبلی نارنجی */}
            <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
              {!t.has_user && <Chip size="small" variant="outlined" label="حساب کاربری ندارد" />}
              {t.roles.length === 0 && t.old_site_departments.length === 0 && !(t.other_assignments || []).length && (
                <Chip size="small" variant="outlined" label="نقش یا مسئولیتی ندارد" />
              )}
              {t.roles.map((r, i) => (
                <Chip
                  key={`r${i}`}
                  size="small"
                  color={r.is_old_site ? "warning" : "default"}
                  label={`${roleDisplayName(r.role_name)} — ${r.site_name || "سراسری"}`}
                />
              ))}
              {t.old_site_departments.map((d) => (
                <Chip key={`d${d}`} size="small" color="warning" variant="outlined" label={`سرپرست واحد ${d}`} />
              ))}
              {(t.other_assignments || []).map((a) => (
                <Chip key={`o${a}`} size="small" color="warning" variant="outlined" label={a} />
              ))}
            </Stack>

            {/* اقدام‌ها */}
            <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
              <Button
                size="small"
                variant="outlined"
                onClick={() =>
                  onOpenAccess({
                    id: t.employee_id,
                    first_name: t.first_name,
                    last_name: t.last_name,
                    personnel_code: t.personnel_code,
                    site_id: t.site_id,
                  })
                }
              >
                دسترسی‌ها
              </Button>
              <Button size="small" variant="contained" onClick={() => handleReviewed(t.id)} disabled={busyId === t.id}>
                بررسی شد
              </Button>
            </Stack>
          </Box>
        ))}
      </Stack>
    </Card>
  );
}
