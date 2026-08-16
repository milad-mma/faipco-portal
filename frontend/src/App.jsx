import { useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import AdminRoute from "./components/AdminRoute";
import PermissionRoute from "./components/PermissionRoute";
import Layout from "./components/Layout";
import SplashScreen from "./components/SplashScreen";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import EmployeesPage from "./pages/EmployeesPage";
import DepartmentsPage from "./pages/DepartmentsPage";
import SitesPage from "./pages/SitesPage";
import SiteSettingsPage from "./pages/SiteSettingsPage";
import SyncPage from "./pages/SyncPage";
import NoticesPage from "./pages/NoticesPage";
import NewNoticePage from "./pages/NewNoticePage";
import NoticeReportsPage from "./pages/NoticeReportsPage";
import AccessManagementPage from "./pages/AccessManagementPage";
import BulkRoleAssignmentPage from "./pages/BulkRoleAssignmentPage";
import BackupPage from "./pages/BackupPage";
import IpAllowlistPage from "./pages/IpAllowlistPage";
import AttendanceClockPage from "./pages/AttendanceClockPage";
import PresenceReportPage from "./pages/PresenceReportPage";
import ClockInOutReportPage from "./pages/ClockInOutReportPage";
import BirthdayMessagesPage from "./pages/BirthdayMessagesPage";
import NotFoundPage from "./pages/NotFoundPage";

const SPLASH_DURATION_MS = 2000;
const SPLASH_FADE_MS = 400;

export default function App() {
  const [showSplash, setShowSplash] = useState(true);
  const [splashVisible, setSplashVisible] = useState(true);

  useEffect(() => {
    const hideTimer = setTimeout(() => setSplashVisible(false), SPLASH_DURATION_MS);
    const removeTimer = setTimeout(() => setShowSplash(false), SPLASH_DURATION_MS + SPLASH_FADE_MS);
    return () => {
      clearTimeout(hideTimer);
      clearTimeout(removeTimer);
    };
  }, []);

  return (
    <>
      {showSplash && <SplashScreen visible={splashVisible} />}
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
          <Route path="/bulk-role-assignment" element={<AdminRoute><BulkRoleAssignmentPage /></AdminRoute>} />
          <Route path="/backup" element={<AdminRoute><BackupPage /></AdminRoute>} />
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
          <Route path="/notice-reports" element={<AdminRoute><NoticeReportsPage /></AdminRoute>} />
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
