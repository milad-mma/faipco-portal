import { Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import AdminRoute from "./components/AdminRoute";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import EmployeesPage from "./pages/EmployeesPage";
import SitesPage from "./pages/SitesPage";
import SyncPage from "./pages/SyncPage";
import NoticesPage from "./pages/NoticesPage";
import NoticeReportsPage from "./pages/NoticeReportsPage";
import AccessManagementPage from "./pages/AccessManagementPage";
import NotFoundPage from "./pages/NotFoundPage";

export default function App() {
  return (
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
        <Route path="/sites" element={<AdminRoute><SitesPage /></AdminRoute>} />
        <Route path="/sync" element={<AdminRoute><SyncPage /></AdminRoute>} />
        <Route path="/access" element={<AdminRoute><AccessManagementPage /></AdminRoute>} />

        {/* برای همه کاربران لاگین‌شده: */}
        <Route path="/notices" element={<NoticesPage />} />
        <Route path="/notice-reports" element={<AdminRoute><NoticeReportsPage /></AdminRoute>} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
