import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Paper,
  TextField,
  Typography,
} from "@mui/material";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      await login(username, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || "ورود ناموفق بود. نام کاربری یا رمز عبور را بررسی کنید.");
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
        <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", mb: 3 }}>
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

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Box component="form" onSubmit={handleSubmit} sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
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
          <Button type="submit" variant="contained" size="large" disabled={isSubmitting} sx={{ mt: 1 }}>
            {isSubmitting ? "در حال ورود..." : "ورود"}
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}
