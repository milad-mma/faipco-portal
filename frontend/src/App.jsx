import { useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import AdminRoute from "./components/AdminRoute";
import SiteNoticeReportRoute from "./components/SiteNoticeReportRoute";
import PermissionRoute from "./components/PermissionRoute";
import Layout from "./components/Layout";
import SplashScreen from "./components/SplashScreen";
import { useAuth } from "./context/AuthContext";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import EmployeesPage from "./pages/EmployeesPage";
import DepartmentsPage from "./pages/DepartmentsPage";
import SitesPage from "./pages/SitesPage";
import SiteSettingsPage from "./pages/SiteSettingsPage";
import SyncPage from "./pages/SyncPage";
import NoticesPage from "./pages/NoticesPage";
import MyVehiclesPage from "./pages/MyVehiclesPage";
import VehiclesReportPage from "./pages/VehiclesReportPage";
import NewNoticePage from "./pages/NewNoticePage";
import PersonalDashboardPage from "./pages/PersonalDashboardPage";
import ProfilePage from "./pages/ProfilePage";
import NoticeReportsPage from "./pages/NoticeReportsPage";
import AccessManagementPage from "./pages/AccessManagementPage";
import RoleManagementPage from "./pages/RoleManagementPage";
import BulkRoleAssignmentPage from "./pages/BulkRoleAssignmentPage";
import BackupPage from "./pages/BackupPage";
import UpdatePage from "./pages/UpdatePage";
import IpAllowlistPage from "./pages/IpAllowlistPage";
import AttendanceClockPage from "./pages/AttendanceClockPage";
import PresenceReportPage from "./pages/PresenceReportPage";
import ClockInOutReportPage from "./pages/ClockInOutReportPage";
import BirthdayMessagesPage from "./pages/BirthdayMessagesPage";
import NotFoundPage from "./pages/NotFoundPage";

const SPLASH_FADE_MS = 400;

export default function App() {
  // به‌جای یک تایمر ثابت دلخواه (که قبلاً همیشه ۲ ثانیه صبر می‌کرد، حتی
  // وقتی اپ زودتر آماده بود، و باعث می‌شد هر صفحه‌ای — از جمله «اطلاعیه
  // جدید» اگر کاربر رویش Refresh می‌زد — با یک تأخیر ثابت و بی‌دلیل باز
  // شود)، اسپلش دقیقاً تا وقتی isLoading واقعی احراز هویت (چک اولیه
  // Session) تمام شود نمایش داده می‌شود — نه بیشتر، نه کمتر.
  const { isLoading } = useAuth();
  const [showSplash, setShowSplash] = useState(true);

  useEffect(() => {
    if (isLoading) return;
    const removeTimer = setTimeout(() => setShowSplash(false), SPLASH_FADE_MS);
    return () => clearTimeout(removeTimer);
  }, [isLoading]);

  return (
    <>
      {showSplash && <SplashScreen visible={isLoading} />}
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          {/* فقط Admin: */}
          <Route path="/" element={<AdminRoute><DashboardPage /></AdminRoute>} />
          <Route path="/employees" element={<AdminRoute><EmployeesPage /></AdminRoute>} />
          <Route path="/departments" element={<AdminRoute><DepartmentsPage /></AdminRoute>} />
          <Route path="/sites" element={<AdminRoute><SitesPage /></AdminRoute>} />
          <Route path="/sites/:siteId/settings" element={<AdminRoute><SiteSettingsPage /></AdminRoute>} />
          <Route path="/sync" element={<AdminRoute><SyncPage /></AdminRoute>} />
          <Route path="/access" element={<AdminRoute><AccessManagementPage /></AdminRoute>} />
          <Route path="/role-management" element={<AdminRoute><RoleManagementPage /></AdminRoute>} />
          <Route path="/bulk-role-assignment" element={<AdminRoute><BulkRoleAssignmentPage /></AdminRoute>} />
          <Route path="/backup" element={<AdminRoute><BackupPage /></AdminRoute>} />
          <Route path="/update" element={<AdminRoute><UpdatePage /></AdminRoute>} />
          <Route path="/ip-allowlist" element={<AdminRoute><IpAllowlistPage /></AdminRoute>} />
          <Route path="/presence-report" element={<AdminRoute><PresenceReportPage /></AdminRoute>} />
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

          {/* برای همه کاربران لاگین‌شده: */}
          <Route path="/notices" element={<NoticesPage />} />
          <Route path="/notices/new" element={<NewNoticePage />} />
          <Route path="/my-dashboard" element={<PersonalDashboardPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/my-vehicles" element={<MyVehiclesPage />} />
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
            path="/attendance-clock"
            element={
              <PermissionRoute check={(u) => u?.can_clock_in_out && !u?.is_superuser}>
                <AttendanceClockPage />
              </PermissionRoute>
            }
          />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </>
  );
}
