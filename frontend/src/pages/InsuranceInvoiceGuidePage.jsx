/**
 * «پیگیری فاکتورهای ارسالی» بیمه تکمیلی (مسیر /insurance/invoices): متن راهنمایی که مدیر بیمه در
 * «مدیریت بیمه تکمیلی ← تنظیمات ← راهنمای پیگیری فاکتورها» می‌نویسد. متن ساده با لینک‌های قابل کلیک
 * ([متن](آدرس) یا آدرس خام؛ LinkifiedText — بدون رندر HTML، امن). خطوط و پاراگراف‌ها همان‌طور که نوشته شده‌اند.
 */
import { useEffect, useState } from "react";
import { Alert, Box, Card, CircularProgress, Typography } from "@mui/material";
import BackLink from "../components/BackLink";
import LinkifiedText from "../components/LinkifiedText";
import { fetchInsuranceInvoiceGuide } from "../api/insurance";

export default function InsuranceInvoiceGuidePage() {
  const [text, setText] = useState(null); // null = در حال بارگذاری
  const [error, setError] = useState("");

  useEffect(() => {
    fetchInsuranceInvoiceGuide()
      .then((data) => setText(data.text || ""))
      .catch(() => setError("دریافت راهنما ناموفق بود. لطفاً دوباره تلاش کنید."));
  }, []);

  return (
    <Box sx={{ maxWidth: 900, mx: "auto" }}>
      <BackLink to="/insurance-hub" label="بازگشت به بیمه تکمیلی" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>
        پیگیری فاکتورهای ارسالی
      </Typography>
      {error ? (
        <Alert severity="error">{error}</Alert>
      ) : text === null ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : text.trim() === "" ? (
        <Alert severity="info">راهنمای پیگیری فاکتورها هنوز نوشته نشده است.</Alert>
      ) : (
        <Card variant="outlined" sx={{ borderRadius: 3, p: { xs: 2.5, sm: 3.5 } }}>
          <Typography
            component="div"
            sx={{ whiteSpace: "pre-line", lineHeight: 2, overflowWrap: "anywhere", "& a": { fontWeight: 700 } }}
          >
            <LinkifiedText text={text} />
          </Typography>
        </Card>
      )}
    </Box>
  );
}
