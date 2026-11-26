import { Chip } from "@mui/material";

export const states = {
  pending: "در انتظار ارسال", accepted: "پذیرفته‌شده توسط سرویس پوش",
  sent: "ارسال‌شده", partial: "ارسال ناقص", failed: "ناموفق", skipped: "ردشده از صف",
  expired: "منقضی", cancelled: "لغوشده", no_devices: "بدون دستگاه",
  no_targets: "بدون گیرنده", not_accepted: "پذیرفته نشد", stale: "اشتراک منقضی",
  ineligible: "فاقد شرایط ارسال",
};

export default function Status({ value }) {
  const accepted = ["sent", "accepted"].includes(value);
  return <Chip size="small" variant="outlined"
    sx={{ height: "auto", maxWidth: "100%", "& .MuiChip-label": { whiteSpace: "normal", py: 0.4 } }}
    label={accepted ? "پذیرفته‌شده توسط سرویس پوش" : states[value] || value}
    color={({ accepted: "info", sent: "info", failed: "error", partial: "warning" })[value] || "default"} />;
}
