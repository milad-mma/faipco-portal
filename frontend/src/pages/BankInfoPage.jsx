/**
 * صفحه‌ی «اطلاعات بانکی» پرسنل (پنل کاربری): برای هر بانکی که منابع انسانی برای سایت تعریف کرده، شماره حساب / شبا /
 * شماره کارت (بر اساس تنظیمات همان بانک) ثبت یا تغییر داده می‌شود. تغییر آزاد است و در سابقه ثبت می‌شود.
 * بانک‌های اجباریِ تکمیل‌نشده با هشدار مشخص می‌شوند (docs/bank-accounts.md).
 */
import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Card,
  Chip,
  CircularProgress,
  Collapse,
  Link,
  Stack,
  Typography,
} from "@mui/material";
import AccountBalanceOutlinedIcon from "@mui/icons-material/AccountBalanceOutlined";
import BackLink from "../components/BackLink";
import BankAccountForm from "../components/BankAccountForm";
import { useAuth } from "../context/AuthContext";
import { fetchMyBankHistory, fetchMyBankInfo, saveMyBankAccount } from "../api/bankAccounts";
import { faDateTime } from "../utils/dateTimeFa";

export default function BankInfoPage() {
  const { refetchUser } = useAuth();
  const [info, setInfo] = useState(null);
  const [error, setError] = useState("");
  const [history, setHistory] = useState(null);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    fetchMyBankInfo()
      .then(setInfo)
      .catch((err) => setError(err.response?.data?.detail || "دریافت اطلاعات بانکی با خطا مواجه شد."));
  }, []);

  async function handleSave(bankId, payload) {
    const next = await saveMyBankAccount(bankId, payload);
    setInfo(next);
    setHistory(null);
    refetchUser?.()?.catch?.(() => {});
  }

  function toggleHistory() {
    const next = !showHistory;
    setShowHistory(next);
    if (next && history === null) {
      fetchMyBankHistory()
        .then(setHistory)
        .catch(() => setHistory([]));
    }
  }

  return (
    <Box sx={{ maxWidth: { xs: "100%", md: 640 }, mx: "auto" }}>
      <BackLink to="/profile" label="بازگشت به پروفایل" />
      <Typography variant="h5" fontWeight={800} sx={{ mb: 2 }}>
        اطلاعات بانکی
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}
      {!info && !error && <CircularProgress size={24} />}

      {info && info.banks.length === 0 && (
        <Alert severity="info">هنوز بانکی برای سایت شما تعریف نشده است.</Alert>
      )}

      {info?.missing_required && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          لطفاً اطلاعات {info.missing_banks.join("، ")} را کامل کنید.
        </Alert>
      )}

      <Stack spacing={2}>
        {info?.banks.map((bank) => (
          <Card key={bank.id} variant="outlined" sx={{ borderRadius: 2, p: 2.5 }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
              <AccountBalanceOutlinedIcon color="action" />
              <Typography fontWeight={700} sx={{ flex: 1 }}>
                {bank.name}
              </Typography>
              {bank.complete ? (
                <Chip size="small" color="success" variant="outlined" label="تکمیل" />
              ) : (
                <Chip
                  size="small"
                  color={bank.is_required ? "warning" : "default"}
                  variant="outlined"
                  label={bank.is_required ? "تکمیل نشده" : "اختیاری"}
                />
              )}
            </Stack>
            <BankAccountForm
              key={bank.id}
              bank={bank}
              onSave={(payload) => handleSave(bank.id, payload)}
            />
            {bank.updated_at && (
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
                آخرین تغییر: {faDateTime(bank.updated_at)}
              </Typography>
            )}
          </Card>
        ))}
      </Stack>

      {info?.banks.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Link component="button" type="button" onClick={toggleHistory} underline="hover">
            {showHistory ? "بستن سابقه‌ی تغییرات" : "سابقه‌ی تغییرات"}
          </Link>
          <Collapse in={showHistory}>
            <BankHistoryList items={history} />
          </Collapse>
        </Box>
      )}
    </Box>
  );
}

// فهرست سابقه‌ی تغییرات (مشترک با پنل منابع انسانی)
export function BankHistoryList({ items }) {
  if (items === null) return <CircularProgress size={20} sx={{ mt: 1 }} />;
  if (!items.length)
    return (
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
        تغییری ثبت نشده است.
      </Typography>
    );
  return (
    <Stack spacing={1} sx={{ mt: 1 }}>
      {items.map((h) => (
        <Card key={h.id} variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
          <Typography variant="body2" fontWeight={700}>
            {h.bank_name}
            <Typography component="span" variant="caption" color="text.secondary" sx={{ mr: 1 }}>
              {faDateTime(h.created_at)} — {h.changed_by_name || "—"}
              {h.by_admin ? " (منابع انسانی)" : ""}
            </Typography>
          </Typography>
          {h.changes.map((c) => (
            <Typography key={c.field} variant="caption" sx={{ display: "block" }}>
              {c.label}:{" "}
              <Box component="span" dir="ltr" sx={{ color: "text.secondary" }}>
                {c.old}
              </Box>{" "}
              ←{" "}
              <Box component="span" dir="ltr">
                {c.new}
              </Box>
            </Typography>
          ))}
        </Card>
      ))}
    </Stack>
  );
}
