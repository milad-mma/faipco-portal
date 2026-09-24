import { useAuth } from "../context/AuthContext";
import ChangePasswordDialog from "./ChangePasswordDialog";

/**
 * نگهبان تغییر رمز اجباری؛ در سطح ریشه (کنار Layout/صفحات) نصب می‌شود. بدون ورودی (props).
 * اگر user.must_change_password درست باشد (پس از ورود یا هر بار خواندن /auth/me)، دیالوگ اجباری
 * تغییر رمز را بدون امکان بستن نمایش می‌دهد تا کاربر رمز را عوض کند؛ در غیر این صورت null برمی‌گرداند.
 */
export default function MandatoryPasswordChangeGuard() {
  const { user } = useAuth();

  if (!user?.must_change_password) return null;

  return <ChangePasswordDialog open onClose={() => {}} mandatory />;
}
