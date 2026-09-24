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
 * دیالوگ «تغییرات اخیر پرتال» که هنگام ورود کاربر نمایش داده می‌شود.
 * بدون ورودی (props). اعلان جاری را از سرور می‌گیرد و فقط اگر should_show درست باشد نمایش می‌دهد؛
 * در غیر این صورت null برمی‌گرداند. تصمیم نمایش کاملاً سمت سرور گرفته می‌شود.
 * دو دکمه دارد:
 *   - «بستن»: فقط دیالوگ را می‌بندد و دفعه‌ی بعد دوباره نمایش داده می‌شود.
 *   - «دیگر نمایش نده»: نسخه‌ی فعلی اعلان را برای کاربر ثبت می‌کند؛ با انتشار نسخه‌ی
 *     جدید توسط ادمین، اعلان دوباره ظاهر می‌شود.
 */
export default function AnnouncementDialog() {
  const [announcement, setAnnouncement] = useState(null); // اعلان دریافتی {title, body, should_show, ...}
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false); // در حال ثبت «دیگر نمایش نده»

  // دریافت اعلان جاری هنگام mount و باز کردن دیالوگ در صورت نیاز
  useEffect(() => {
    fetchCurrentAnnouncement()
      .then((data) => {
        if (!data?.should_show) return;
        setAnnouncement(data);
        setOpen(true);
      })
      // خطا بی‌صدا نادیده گرفته می‌شود تا قابلیت جانبی اعلان ورود کاربر را مختل نکند
      .catch(() => {});
  }, []);

  // «دیگر نمایش نده»: نسخه‌ی فعلی را روی کاربر ثبت می‌کند و دیالوگ را می‌بندد
  async function handleDismissForever() {
    setBusy(true);
    try {
      await dismissAnnouncement();
    } catch {
      // حتی اگر ثبت ناموفق باشد، دیالوگ در finally بسته می‌شود
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
        {/* متن اعلان به‌صورت متن ساده (نه HTML) رندر می‌شود تا تزریق اسکریپت ممکن نباشد؛ فقط لینک‌ها
            ([متن](آدرس) یا آدرس خام) به المان لینک تبدیل می‌شوند. whiteSpace شکست خطوط را
            حفظ می‌کند و کلیک روی لینک داخلی پرتال دیالوگ را می‌بندد. */}
        <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", lineHeight: 2 }}>
          <LinkifiedText text={announcement.body} onInternalClick={() => setOpen(false)} />
        </Typography>
      </DialogContent>
      {/* دکمه‌ها: «دیگر نمایش نده» در یک سمت و «بستن» در سمت دیگر */}
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
