import { useAuth } from "../context/AuthContext";
import ChangePasswordDialog from "./ChangePasswordDialog";

/**
 * در سطح ریشه (کنار Layout/صفحات) نصب می‌شود — هر بار user.must_change_password
 * را چک می‌کند (بعد از ورود، یا بعد از هر Refresh که /auth/me دوباره خوانده
 * می‌شود) و در صورت True بودن، Dialog اجباری تغییر رمز را نشان می‌دهد؛ کاربر
 * تا رمز را عوض نکند به بقیه پنل دسترسی ندارد.
 */
export default function MandatoryPasswordChangeGuard() {
  const { user } = useAuth();

  if (!user?.must_change_password) return null;

  return <ChangePasswordDialog open onClose={() => {}} mandatory />;
}
