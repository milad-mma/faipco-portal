/**
 * «کارتابل درخواست» پرسنل (مسیر /requests؛ کاشی «کارتابل درخواست» داشبورد شخصی به این‌جا می‌آید). کارت‌ها:
 * - درخواست مرخصی/ماموریت ← /leave-requests (با شمارنده‌ی درخواست‌های منتظر تصمیم همین کاربر؛ اگر ماژول برای سایت
 *   پرسنل غیرفعال باشد، برچسب «غیرفعال»)
 * - درخواست مساعده (به‌زودی)
 * - درخواست وام ← /loans (شمارنده: ضمانت‌ها و تأییدهای منتظر من؛ اگر وام برای سایت پرسنل فعال نیست برچسب
 *   «غیرفعال»، ولی باز می‌شود تا کارتابل تأیید/ضمانت در دسترس بماند)
 */
import { useEffect, useState } from "react";
import { Box, Grid, Typography } from "@mui/material";
import CalendarMonthOutlinedIcon from "@mui/icons-material/CalendarMonthOutlined";
import PaymentsOutlinedIcon from "@mui/icons-material/PaymentsOutlined";
import AccountBalanceOutlinedIcon from "@mui/icons-material/AccountBalanceOutlined";
import { useNavigate } from "react-router-dom";
import BackLink from "../components/BackLink";
import HubCard from "../components/HubCard";
import { useAuth } from "../context/AuthContext";
import { fetchPendingLeaveRequestCount } from "../api/leaveRequests";
import { fetchLoanInboxCount } from "../api/loans";

export default function RequestsHubPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const leaveDisabled = Boolean(user?.leave_requests_disabled);
  const [pendingLeave, setPendingLeave] = useState(0);
  const [pendingLoans, setPendingLoans] = useState(0);
  const loansDisabled = Boolean(user?.loans_disabled);

  useEffect(() => {
    fetchPendingLeaveRequestCount()
      .then((data) => setPendingLeave(data?.pending_count || 0))
      .catch(() => {});
    fetchLoanInboxCount()
      .then((data) => setPendingLoans(data?.count || 0))
      .catch(() => {});
  }, []);

  return (
    <Box sx={{ maxWidth: 900, mx: "auto" }}>
      <BackLink to="/my-dashboard" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>
        کارتابل درخواست
      </Typography>
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6}>
          <HubCard
            icon={<CalendarMonthOutlinedIcon />}
            title="درخواست مرخصی/ماموریت"
            description={
              leaveDisabled
                ? "ثبت درخواست مرخصی و ماموریت برای سایت شما در حال حاضر غیرفعال است."
                : "ثبت مرخصی، ماموریت و تردد فراموش‌شده، و پیگیری یا تأیید درخواست‌ها."
            }
            disabled={leaveDisabled}
            badge={pendingLeave}
            onClick={leaveDisabled ? undefined : () => navigate("/leave-requests")}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <HubCard
            icon={<PaymentsOutlinedIcon />}
            title="درخواست مساعده"
            description="درخواست پرداخت بخشی از حقوق ماه جاری، پیش از روز پرداخت."
            comingSoon
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <HubCard
            icon={<AccountBalanceOutlinedIcon />}
            title="درخواست وام"
            description={
              loansDisabled
                ? "درخواست وام برای سایت شما فعال نیست؛ ضمانت‌ها و تأییدهای منتظر شما این‌جاست."
                : "ثبت درخواست وام طبق دستورالعمل سایت شما، پیگیری نوبت و اقساط."
            }
            disabled={loansDisabled}
            badge={pendingLoans}
            onClick={() => navigate(loansDisabled && pendingLoans ? "/loans?tab=inbox" : "/loans")}
          />
        </Grid>
      </Grid>
    </Box>
  );
}
