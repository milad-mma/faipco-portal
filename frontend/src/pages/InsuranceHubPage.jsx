/**
 * صفحه‌ی «بیمه تکمیلی» پرسنل (مسیر /insurance-hub؛ کاشی «بیمه تکمیلی» داشبورد شخصی به این‌جا می‌آید).
 * دو کارت:
 * - «ثبت‌نام بیمه تکمیلی» ← همان فرم ثبت‌نام (/insurance)؛ اگر ثبت‌نام برای سایت پرسنل بسته باشد برچسب «غیرفعال» دارد.
 * - «پیگیری فاکتورهای ارسالی» ← راهنمای متنی (/insurance/invoices) که مدیر بیمه در تنظیمات می‌نویسد؛ همیشه باز است
 *   (پیگیری فاکتور بعد از بسته شدن ثبت‌نام هم لازم است).
 */
import { Box, Grid, Typography } from "@mui/material";
import HowToRegOutlinedIcon from "@mui/icons-material/HowToRegOutlined";
import ReceiptLongOutlinedIcon from "@mui/icons-material/ReceiptLongOutlined";
import { useNavigate } from "react-router-dom";
import BackLink from "../components/BackLink";
import HubCard from "../components/HubCard";
import { useAuth } from "../context/AuthContext";

export default function InsuranceHubPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const registrationDisabled = Boolean(user?.insurance_disabled);

  return (
    <Box sx={{ maxWidth: 900, mx: "auto" }}>
      <BackLink to="/my-dashboard" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>
        بیمه تکمیلی
      </Typography>
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6}>
          <HubCard
            icon={<HowToRegOutlinedIcon />}
            title="ثبت‌نام بیمه تکمیلی"
            description={
              registrationDisabled
                ? "ثبت‌نام در حال حاضر بسته است؛ اطلاعات قبلی خود را می‌توانید ببینید."
                : "ثبت‌نام یا ویرایش اطلاعات خود و اعضای خانواده، و بارگذاری مدارک."
            }
            disabled={registrationDisabled}
            onClick={() => navigate("/insurance")}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <HubCard
            icon={<ReceiptLongOutlinedIcon />}
            title="پیگیری فاکتورهای ارسالی"
            description="نحوه‌ی پیگیری فاکتورهای درمانی که برای بیمه فرستاده‌اید."
            onClick={() => navigate("/insurance/invoices")}
          />
        </Grid>
      </Grid>
    </Box>
  );
}
