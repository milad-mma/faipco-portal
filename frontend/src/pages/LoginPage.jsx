import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Paper,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { login, employeeLogin } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("staff"); // "staff" | "employee"

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [personnelCode, setPersonnelCode] = useState("");
  const [nationalCode, setNationalCode] = useState("");

  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      if (mode === "staff") {
        await login(username, password);
      } else {
        await employeeLogin(personnelCode, nationalCode);
      }
      navigate("/", { replace: true });
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "ورود ناموفق بود. اطلاعات وارد‌شده را بررسی کنید."
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(160deg, #0E2138 0%, #16324F 55%, #1F4B75 100%)",
        px: 2,
      }}
    >
      <Paper elevation={0} sx={{ width: "100%", maxWidth: 400, p: 4, borderRadius: 3 }}>
        <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", mb: 2 }}>
          <Box
            sx={{
              width: 56,
              height: 56,
              borderRadius: "14px",
              background: "linear-gradient(135deg, #16324F 0%, #1F4B75 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "secondary.main",
              fontWeight: 800,
              fontSize: 24,
              mb: 1.5,
            }}
          >
            F
          </Box>
          <Typography variant="h6" fontWeight={700}>
            ورود به FAIPCO Portal
          </Typography>
          <Typography variant="body2" color="text.secondary">
            پرتال سازمانی مدیریت پرسنل
          </Typography>
        </Box>

        <Tabs
          value={mode}
          onChange={(_, value) => {
            setMode(value);
            setError("");
          }}
          variant="fullWidth"
          sx={{ mb: 2.5 }}
        >
          <Tab value="staff" label="ورود مدیریت" />
          <Tab value="employee" label="ورود پرسنل" />
        </Tabs>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Box component="form" onSubmit={handleSubmit} sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {mode === "staff" ? (
            <>
              <TextField
                label="نام کاربری"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                fullWidth
              />
              <TextField
                label="رمز عبور"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                fullWidth
              />
            </>
          ) : (
            <>
              <TextField
                label="کد پرسنلی"
                value={personnelCode}
                onChange={(e) => setPersonnelCode(e.target.value)}
                required
                autoFocus
                fullWidth
              />
              <TextField
                label="کد ملی"
                type="password"
                value={nationalCode}
                onChange={(e) => setNationalCode(e.target.value)}
                required
                fullWidth
              />
            </>
          )}

          <Button type="submit" variant="contained" size="large" disabled={isSubmitting} sx={{ mt: 1 }}>
            {isSubmitting ? "در حال ورود..." : "ورود"}
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}
