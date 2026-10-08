/**
 * صفحه‌ی «بیمه تکمیلی» پرسنل (مسیر /insurance-hub؛ کاشی «بیمه تکمیلی» داشبورد شخصی به این‌جا می‌آید).
 * دو کارت:
 * - «ثبت‌نام بیمه تکمیلی» ← همان فرم ثبت‌نام (/insurance)؛ اگر ثبت‌نام برای سایت پرسنل بسته باشد برچسب «غیرفعال» دارد.
 * - «پیگیری فاکتورهای ارسالی» ← راهنمای متنی (/insurance/invoices) که مدیر بیمه در تنظیمات می‌نویسد؛ همیشه باز است
 *   (پیگیری فاکتور بعد از بسته شدن ثبت‌نام هم لازم است).
 */
import { Box, Card, CardActionArea, Chip, Grid, Stack, Typography } from "@mui/material";
import HowToRegOutlinedIcon from "@mui/icons-material/HowToRegOutlined";
import ReceiptLongOutlinedIcon from "@mui/icons-material/ReceiptLongOutlined";
import ChevronLeftOutlinedIcon from "@mui/icons-material/ChevronLeftOutlined";
import { useNavigate } from "react-router-dom";
import BackLink from "../components/BackLink";
import { useAuth } from "../context/AuthContext";

function HubCard({ icon, title, description, onClick, disabled }) {
  return (
    <Card variant="outlined" sx={{ borderRadius: 3, height: "100%", opacity: disabled ? 0.6 : 1 }}>
      <CardActionArea onClick={onClick} sx={{ p: 3, height: "100%", display: "flex", alignItems: "flex-start" }}>
        <Stack direction="row" spacing={2} alignItems="flex-start" sx={{ width: "100%" }}>
          <Box
            sx={{
              width: 52,
              height: 52,
              borderRadius: 2.5,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              bgcolor: "action.hover",
              color: "primary.main",
              flexShrink: 0,
              "& svg": { fontSize: 30 },
            }}
          >
            {icon}
          </Box>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
              <Typography fontWeight={800}>{title}</Typography>
              {disabled && <Chip size="small" label="غیرفعال" sx={{ height: 20, fontSize: 11 }} />}
            </Stack>
            <Typography variant="body2" color="text.secondary">
              {description}
            </Typography>
          </Box>
          <ChevronLeftOutlinedIcon color="action" sx={{ alignSelf: "center" }} />
        </Stack>
      </CardActionArea>
    </Card>
  );
}

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
