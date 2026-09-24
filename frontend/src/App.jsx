/**
 * کامپوننت ریشه‌ی برنامه: نمایش اسپلش تا آماده شدن احراز هویت و برندینگ،
 * و تعریف همه‌ی مسیرهای (Route) برنامه به همراه محافظ‌های دسترسی هر مسیر.
 * مسیرهای داخلی داخل Layout و پشت ProtectedRoute (نیازمند ورود) قرار دارند.
 */
import { Suspense, useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import AdminRoute from "./components/AdminRoute";
import SiteNoticeReportRoute from "./components/SiteNoticeReportRoute";
import PermissionRoute from "./components/PermissionRoute";
import Layout from "./components/Layout";
import SplashScreen from "./components/SplashScreen";
import { useAuth } from "./context/AuthContext";
import lazyPage from "./utils/lazyPage";
import { useBranding } from "./context/BrandingContext";
import LoginPage from "./pages/LoginPage";
import PersonalDashboardPage from "./pages/PersonalDashboardPage";
import NotFoundPage from "./pages/NotFoundPage";

// صفحه‌ها به‌صورت تنبل (هر صفحه یک chunk جدا) بارگذاری می‌شوند تا بار اول فقط کد لازم دانلود و اجرا شود؛
// ورود و داشبورد شخصی (پرکاربردترین مسیرها) مستقیم import شده‌اند
const ForgotPasswordPage = lazyPage(() => import("./pages/ForgotPasswordPage"));
const ResetPasswordPage = lazyPage(() => import("./pages/ResetPasswordPage"));
const DashboardPage = lazyPage(() => import("./pages/DashboardPage"));
const EmployeesPage = lazyPage(() => import("./pages/EmployeesPage"));
const DepartmentsPage = lazyPage(() => import("./pages/DepartmentsPage"));
const SitesPage = lazyPage(() => import("./pages/SitesPage"));
const SiteSettingsPage = lazyPage(() => import("./pages/SiteSettingsPage"));
const SyncPage = lazyPage(() => import("./pages/SyncPage"));
const NoticesPage = lazyPage(() => import("./pages/NoticesPage"));
const MyVehiclesPage = lazyPage(() => import("./pages/MyVehiclesPage"));
const InsurancePage = lazyPage(() => import("./pages/InsurancePage"));
const InsuranceAdminPage = lazyPage(() => import("./pages/InsuranceAdminPage"));
const LeaveRequestPage = lazyPage(() => import("./pages/LeaveRequestPage"));
const LeaveRequestsAdminListPage = lazyPage(() => import("./pages/LeaveRequestsAdminListPage"));
const LeaveRequestStructurePage = lazyPage(() => import("./pages/LeaveRequestStructurePage"));
const MyPerformancePage = lazyPage(() => import("./pages/MyPerformancePage"));
const EvaluationFillPage = lazyPage(() => import("./pages/EvaluationFillPage"));
const VehiclesReportPage = lazyPage(() => import("./pages/VehiclesReportPage"));
const NewNoticePage = lazyPage(() => import("./pages/NewNoticePage"));
const ProfilePage = lazyPage(() => import("./pages/ProfilePage"));
const NoticeReportsPage = lazyPage(() => import("./pages/NoticeReportsPage"));
const FeedbackReportPage = lazyPage(() => import("./pages/FeedbackReportPage"));
const FeedbackSubmitPage = lazyPage(() => import("./pages/FeedbackSubmitPage"));
const AccessManagementPage = lazyPage(() => import("./pages/AccessManagementPage"));
const RoleManagementPage = lazyPage(() => import("./pages/RoleManagementPage"));
const SystemSettingsPage = lazyPage(() => import("./pages/SystemSettingsPage"));
const BulkRoleAssignmentPage = lazyPage(() => import("./pages/BulkRoleAssignmentPage"));
const BackupPage = lazyPage(() => import("./pages/BackupPage"));
const UpdatePage = lazyPage(() => import("./pages/UpdatePage"));
const IpAllowlistPage = lazyPage(() => import("./pages/IpAllowlistPage"));
const AttendanceClockPage = lazyPage(() => import("./pages/AttendanceClockPage"));
const MonthlyAttendanceReportPage = lazyPage(() => import("./pages/MonthlyAttendanceReportPage"));
const PresenceReportPage = lazyPage(() => import("./pages/PresenceReportPage"));
const ClockInOutReportPage = lazyPage(() => import("./pages/ClockInOutReportPage"));
const BirthdayMessagesPage = lazyPage(() => import("./pages/BirthdayMessagesPage"));
const EvaluationStructurePage = lazyPage(() => import("./pages/EvaluationStructurePage"));
const EvaluationPeriodsPage = lazyPage(() => import("./pages/EvaluationPeriodsPage"));
const EvaluationFormsPage = lazyPage(() => import("./pages/EvaluationFormsPage"));
const EvaluationReportsPage = lazyPage(() => import("./pages/EvaluationReportsPage"));
const EvaluationFormBuilderPage = lazyPage(() => import("./pages/EvaluationFormBuilderPage"));

const SPLASH_FADE_MS = 400; // مدت انیمیشن محو شدن اسپلش پیش از حذف کامل آن (میلی‌ثانیه)

/**
 * کامپوننت اصلی برنامه؛ ورودی ندارد.
 * اسپلش را تا پایان بارگذاری احراز هویت و برندینگ نشان می‌دهد و سپس جدول مسیرها را رندر می‌کند.
 */
export default function App() {
  // اسپلش دقیقاً تا پایان چک اولیه‌ی Session (احراز هویت) و بارگذاری برندینگ نمایش داده می‌شود
  const { isLoading: authIsLoading } = useAuth();
  const { isLoading: brandingIsLoading } = useBranding();
  // تا هر دو آماده نشوند اسپلش کنار نمی‌رود تا صفحه با مقادیر پیش‌فرض ظاهر نشود
  const isLoading = authIsLoading || brandingIsLoading;
  const [showSplash, setShowSplash] = useState(true);

  // پس از پایان بارگذاری، اسپلش را بعد از اتمام انیمیشن محو شدن از DOM حذف می‌کند
  useEffect(() => {
    if (isLoading) return;
    const removeTimer = setTimeout(() => setShowSplash(false), SPLASH_FADE_MS);
    return () => clearTimeout(removeTimer);
  }, [isLoading]);

  return (
    <>
      {showSplash && <SplashScreen visible={isLoading} />}
      {/* مرز Suspense برای صفحه‌های تنبل بیرون از Layout (فراموشی/بازنشانی رمز)؛ صفحه‌های داخل Layout مرز خودشان را دارند */}
      <Suspense fallback={null}>
      <Routes>
        {/* مسیرهای عمومی (بدون نیاز به ورود): ورود، فراموشی و بازنشانی رمز عبور */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />

        {/* مسیرهای داخلی: نیازمند ورود و نمایش داخل Layout اصلی (منو و نوار بالا) */}
        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          {/* داشبورد مدیریتی و به‌روزرسانی فقط برای Admin؛ گزارش حضور برای دارندگان مجوز لاگ تردد */}
          <Route path="/" element={<AdminRoute><DashboardPage /></AdminRoute>} />
          <Route path="/update" element={<AdminRoute><UpdatePage /></AdminRoute>} />
          <Route
            path="/presence-report"
            element={<PermissionRoute check={(u) => u?.can_view_attendance_logs}><PresenceReportPage /></PermissionRoute>}
          />

          {/* فهرست پرسنل: برای هر کاربری که مجوز مشاهده، ویرایش یا ایجاد پرسنل دارد */}
          <Route
            path="/employees"
            element={
              <PermissionRoute check={(u) => u?.can_view_employees || u?.can_update_employees || u?.can_create_employees}>
                <EmployeesPage />
              </PermissionRoute>
            }
          />

          {/* صفحات مدیریتی: برای Admin یا هر نقشی که مجوز متناظر آن صفحه را دارد (بررسی با PermissionRoute) */}
          <Route
            path="/departments"
            element={<PermissionRoute check={(u) => u?.can_manage_sites}><DepartmentsPage /></PermissionRoute>}
          />
          <Route
            path="/sites"
            element={<PermissionRoute check={(u) => u?.can_view_sites}><SitesPage /></PermissionRoute>}
          />
          <Route
            path="/sites/:siteId/settings"
            element={<PermissionRoute check={(u) => u?.can_manage_sites}><SiteSettingsPage /></PermissionRoute>}
          />
          <Route
            path="/performance/structure"
            element={
              <PermissionRoute check={(u) => u?.can_manage_performance_structure}>
                <EvaluationStructurePage />
              </PermissionRoute>
            }
          />
          <Route
            path="/performance/periods"
            element={
              <PermissionRoute check={(u) => u?.can_manage_performance_periods}>
                <EvaluationPeriodsPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/performance/forms"
            element={
              <PermissionRoute check={(u) => u?.can_manage_performance_forms}>
                <EvaluationFormsPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/performance/forms/:formId"
            element={
              <PermissionRoute check={(u) => u?.can_manage_performance_forms}>
                <EvaluationFormBuilderPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/performance/reports"
            element={
              <PermissionRoute check={(u) => u?.can_view_performance_reports}>
                <EvaluationReportsPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/sync"
            element={
              <PermissionRoute check={(u) => u?.can_manage_sync || u?.can_view_sync || u?.can_run_sync}>
                <SyncPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/access"
            element={<PermissionRoute check={(u) => u?.can_manage_users}><AccessManagementPage /></PermissionRoute>}
          />
          <Route
            path="/role-management"
            element={<PermissionRoute check={(u) => u?.can_manage_roles}><RoleManagementPage /></PermissionRoute>}
          />
          <Route
            path="/system-settings"
            element={<PermissionRoute check={(u) => u?.can_manage_system_settings}><SystemSettingsPage /></PermissionRoute>}
          />
          <Route
            path="/bulk-role-assignment"
            element={<PermissionRoute check={(u) => u?.can_manage_users}><BulkRoleAssignmentPage /></PermissionRoute>}
          />
          <Route
            path="/backup"
            element={
              <PermissionRoute check={(u) => u?.can_manage_backup || u?.can_bust_cache}>
                <BackupPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/ip-allowlist"
            element={<PermissionRoute check={(u) => u?.can_manage_ip_allowlist}><IpAllowlistPage /></PermissionRoute>}
          />
          <Route
            path="/clock-in-out-report"
            element={
              <PermissionRoute check={(u) => u?.can_view_clock_records}>
                <ClockInOutReportPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/birthday-messages"
            element={
              <PermissionRoute check={(u) => u?.can_manage_birthday_messages}>
                <BirthdayMessagesPage />
              </PermissionRoute>
            }
          />

          {/* صفحات شخصی و عمومی برای همه‌ی کاربران واردشده؛ زیرصفحه‌های مدیریتی آن‌ها با مجوز جداگانه */}
          <Route path="/notices" element={<NoticesPage />} />
          <Route path="/notices/new" element={<NewNoticePage />} />
          <Route path="/my-dashboard" element={<PersonalDashboardPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/feedback" element={<FeedbackSubmitPage />} />
          <Route path="/my-vehicles" element={<MyVehiclesPage />} />
          <Route path="/insurance" element={<InsurancePage />} />
          <Route
            path="/insurance/admin"
            element={<PermissionRoute check={(u) => u?.can_view_insurance}><InsuranceAdminPage /></PermissionRoute>}
          />
          <Route path="/leave-requests" element={<LeaveRequestPage />} />
          <Route
            path="/leave-requests/settings"
            element={
              <PermissionRoute check={(u) => u?.can_manage_sites}>
                <LeaveRequestStructurePage />
              </PermissionRoute>
            }
          />
          <Route
            path="/leave-requests/all"
            element={
              <PermissionRoute check={(u) => u?.can_view_leave_requests || u?.can_manage_leave_requests}>
                <LeaveRequestsAdminListPage />
              </PermissionRoute>
            }
          />
          <Route path="/my-performance" element={<MyPerformancePage />} />
          <Route path="/my-performance/evaluate/:assignmentId" element={<EvaluationFillPage />} />
          <Route path="/my-performance/edit-evaluation/:evaluationId" element={<EvaluationFillPage />} />
          <Route
            path="/vehicle-report"
            element={
              <PermissionRoute check={(u) => u?.can_view_vehicles_report}>
                <VehiclesReportPage />
              </PermissionRoute>
            }
          />
          <Route path="/notice-reports" element={<SiteNoticeReportRoute><NoticeReportsPage /></SiteNoticeReportRoute>} />
          <Route
            path="/feedback-report"
            element={
              <PermissionRoute check={(u) => u?.can_view_feedback}>
                <FeedbackReportPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/attendance-clock"
            element={
              <PermissionRoute check={(u) => u?.can_clock_in_out && !u?.is_superuser}>
                <AttendanceClockPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/monthly-attendance"
            element={
              <PermissionRoute check={(u) => u?.has_monthly_attendance}>
                <MonthlyAttendanceReportPage />
              </PermissionRoute>
            }
          />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      </Suspense>
    </>
  );
}
