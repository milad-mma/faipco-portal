import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Typography,
} from "@mui/material";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import { dismissAnnouncement, fetchCurrentAnnouncement } from "../api/announcement";
import LinkifiedText from "./LinkifiedText";

/**
 * دیالوگ «تغییرات اخیر پرتال» — هنگام ورود کاربر نمایش داده می‌شود.
 *
 * ⚠️ دو دکمه با رفتار متفاوت (طبق درخواست صریح کاربر):
 *   - «بستن»: فقط دیالوگ را می‌بندد؛ دفعه بعد دوباره نمایش داده می‌شود.
 *   - «دیگر نمایش نده»: نسخه فعلی را روی کاربر ثبت می‌کند تا دیگر
 *     نمایش داده نشود - ولی اگر ادمین اعلان **جدیدی** منتشر کند، نسخه
 *     بالا می‌رود و دوباره ظاهر می‌شود.
 *
 * ⚠️ تصمیم نمایش سمت سرور گرفته می‌شود (فیلد should_show)، نه اینجا -
 * تا منطق در یک جا بماند و با دستکاری کلاینت دور زدنی نباشد.
 */
export default function AnnouncementDialog() {
  const [announcement, setAnnouncement] = useState(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchCurrentAnnouncement()
      .then((data) => {
        if (!data?.should_show) return;
        setAnnouncement(data);
        setOpen(true);
      })
      // ⚠️ خطا بی‌صدا نادیده گرفته می‌شود: اعلان یک قابلیت جانبی است و
      // نباید ورود کاربر به پرتال را مختل کند.
      .catch(() => {});
  }, []);

  async function handleDismissForever() {
    setBusy(true);
    try {
      await dismissAnnouncement();
    } catch {
      // حتی اگر ثبت نشد، دیالوگ بسته می‌شود - کاربر نباید گیر کند.
    } finally {
      setBusy(false);
      setOpen(false);
    }
  }

  if (!announcement) return null;

  return (
    <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
      <DialogTitle>
        <Stack direction="row" alignItems="center" spacing={1}>
          <CampaignOutlinedIcon color="primary" />
          <Typography fontWeight={700}>{announcement.title || "تغییرات اخیر پرتال"}</Typography>
        </Stack>
      </DialogTitle>
      <DialogContent dividers>
        {/* ⚠️ متن ادمین به‌صورت متن ساده رندر می‌شود (نه HTML) تا امکان
            تزریق اسکریپت وجود نداشته باشد؛ فقط لینک‌ها ([متن](آدرس) یا
            آدرس خام) به المان لینک تبدیل می‌شوند. whiteSpace شکست خطوط را
            حفظ می‌کند. کلیک روی لینک داخلی پرتال دیالوگ را می‌بندد. */}
        <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", lineHeight: 2 }}>
          <LinkifiedText text={announcement.body} onInternalClick={() => setOpen(false)} />
        </Typography>
      </DialogContent>
      <DialogActions sx={{ justifyContent: "space-between", px: 2.5, pb: 2 }}>
        <Button size="small" color="inherit" disabled={busy} onClick={handleDismissForever}>
          دیگر نمایش نده
        </Button>
        <Box>
          <Button variant="contained" onClick={() => setOpen(false)}>
            بستن
          </Button>
        </Box>
      </DialogActions>
    </Dialog>
  );
}
