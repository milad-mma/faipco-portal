import { useState } from "react";
import { Alert, Box, Button, Card, CircularProgress, Divider, Stack, Typography } from "@mui/material";
import CloudDownloadOutlinedIcon from "@mui/icons-material/CloudDownloadOutlined";
import WarningAmberOutlinedIcon from "@mui/icons-material/WarningAmberOutlined";
import { downloadBackupArchive } from "../api/backup";
import { monoFontSx } from "../theme";

export default function BackupPage() {
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState("");

  async function handleDownload() {
    setError("");
    setIsDownloading(true);
    try {
      const blob = await downloadBackupArchive();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      const stamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, "");
      a.href = url;
      a.download = `faipco-backup-${stamp}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      setError(err.response?.data?.detail || "ساخت بکاپ ناموفق بود.");
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <Box sx={{ maxWidth: 720, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        پشتیبان‌گیری
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        یک بکاپ کامل و قابل‌جابه‌جایی از کل پرتال بسازید — طوری طراحی شده که با بازیابی روی
        یک سرور دیگر، دقیقاً همان اطلاعات بالا بیاید؛ انگار پروژه Clone شده باشد.
      </Typography>

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
          چه چیزی داخل بکاپ است؟
        </Typography>
        <Typography variant="body2" color="text.secondary" component="ul" sx={{ pl: 2.5, m: 0 }}>
          <li>همه پرسنل، سایت‌ها، واحدهای سازمانی، سمت‌ها</li>
          <li>همه اطلاعیه‌ها (متنی، فیش حقوقی، فیش کارکرد) و آمار بازدید آن‌ها</li>
          <li>همه کاربران، نقش‌ها و مجوزهای دسترسی</li>
          <li>تنظیمات Sync هر سایت و تاریخچه Sync</li>
          <li>
            <strong>کلید رمزنگاری رمز عبور اتصال دیتابیس سایت‌ها</strong> — بدون این کلید، رمزهای
            عبور اتصال روی سرور جدید برای همیشه غیرقابل‌بازیابی می‌شوند
          </li>
        </Typography>

        <Divider sx={{ my: 2.5 }} />

        <Button
          variant="contained"
          size="large"
          startIcon={isDownloading ? <CircularProgress size={18} color="inherit" /> : <CloudDownloadOutlinedIcon />}
          onClick={handleDownload}
          disabled={isDownloading}
        >
          {isDownloading ? "در حال آماده‌سازی بکاپ..." : "دانلود بکاپ کامل"}
        </Button>
      </Card>

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
          <WarningAmberOutlinedIcon color="warning" fontSize="small" />
          <Typography variant="subtitle2" fontWeight={700}>
            بازیابی روی سرور دیگر (Clone)
          </Typography>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          به‌دلایل امنیتی، بازیابی از داخل همین پنل وب انجام نمی‌شود — چون بازنویسی کامل
          دیتابیسِ در حال کار از داخل خودِ همان برنامه ریسک واقعی دارد. به‌جایش، فایل بکاپ را
          روی یک <strong>نصب کاملاً تازه</strong> (سرور جدید، یا همین سرور با پوشه نصب خالی)
          بازیابی کنید:
        </Typography>
        <Box
          sx={{
            p: 2,
            borderRadius: 2,
            backgroundColor: "rgba(22, 50, 79, 0.06)",
            ...monoFontSx,
            fontSize: 13,
            direction: "ltr",
            textAlign: "left",
            overflowX: "auto",
          }}
        >
          sudo bash install.sh --restore-backup /path/to/faipco-backup-....zip
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1.5, display: "block" }}>
          همان گزینه‌های معمول نصب (مثل <code>--domain</code>) را هم می‌توانید کنار همین دستور
          بدهید. اگر روی همان مسیر نصب موجود اجرا کنید (نه یک پوشه/سرور تازه)، برای جلوگیری از
          خطر از‌بین‌رفتن داده زنده، نصب‌کننده با خطا متوقف می‌شود.
        </Typography>
      </Card>
    </Box>
  );
}
