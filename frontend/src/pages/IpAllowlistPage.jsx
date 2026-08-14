import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  Divider,
  IconButton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import WifiOffOutlinedIcon from "@mui/icons-material/WifiOffOutlined";
import { addIpAllowlistEntry, deleteIpAllowlistEntry, fetchIpAllowlist } from "../api/system";
import { monoFontSx } from "../theme";

export default function IpAllowlistPage() {
  const [entries, setEntries] = useState(null);
  const [cidr, setCidr] = useState("");
  const [label, setLabel] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  function load() {
    fetchIpAllowlist().then(setEntries);
  }

  useEffect(() => {
    load();
  }, []);

  async function handleAdd() {
    setError("");
    if (!cidr.trim()) {
      setError("رنج/IP را وارد کنید.");
      return;
    }
    setIsSaving(true);
    try {
      await addIpAllowlistEntry({ cidr: cidr.trim(), label: label.trim() });
      setCidr("");
      setLabel("");
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "افزودن ناموفق بود.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(id) {
    if (!window.confirm("این رنج حذف شود؟")) return;
    await deleteIpAllowlistEntry(id);
    load();
  }

  const isEnforced = entries && entries.length > 0;

  return (
    <Box sx={{ maxWidth: 720, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        رنج‌های IP مجاز برای ورود
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        اگر حداقل یک رنج اینجا ثبت کنید، ورود به پرتال فقط از همان رنج‌ها امکان‌پذیر می‌شود — هرکسی
        از بیرون آن‌ها (مثلاً با VPN) بخواهد وارد شود، پیامی می‌بیند که VPN خود را خاموش کند.
      </Typography>

      {entries === null ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          <Alert severity={isEnforced ? "warning" : "info"} sx={{ mb: 3 }}>
            {isEnforced
              ? "این محدودیت الان فعال است — فقط IP های زیر اجازه ورود دارند."
              : "الان هیچ رنجی ثبت نشده، پس این محدودیت غیرفعال است و همه می‌توانند از هر جایی وارد شوند."}
          </Alert>

          <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2 }}>
              افزودن رنج جدید
            </Typography>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}
            <Stack spacing={2}>
              <TextField
                label="IP یا رنج (CIDR)"
                placeholder="مثال: 203.0.113.5/32 یا 192.168.1.0/24"
                value={cidr}
                onChange={(e) => setCidr(e.target.value)}
                disabled={isSaving}
                sx={{ direction: "ltr", "& input": { textAlign: "left", ...monoFontSx } }}
              />
              <TextField
                label="برچسب (اختیاری)"
                placeholder="مثال: دفتر مرکزی"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                disabled={isSaving}
              />
              <Box>
                <Button
                  variant="contained"
                  startIcon={isSaving ? <CircularProgress size={18} color="inherit" /> : <AddOutlinedIcon />}
                  onClick={handleAdd}
                  disabled={isSaving}
                >
                  افزودن
                </Button>
              </Box>
            </Stack>
          </Card>

          <Card variant="outlined" sx={{ borderRadius: 3 }}>
            {entries.length === 0 ? (
              <Box sx={{ p: 4, textAlign: "center" }}>
                <WifiOffOutlinedIcon sx={{ fontSize: 32, color: "text.secondary", mb: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  هنوز هیچ رنجی ثبت نشده.
                </Typography>
              </Box>
            ) : (
              entries.map((entry, index) => (
                <Box key={entry.id}>
                  {index > 0 && <Divider />}
                  <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ p: 2 }}>
                    <Box>
                      <Typography variant="body2" fontWeight={600} sx={{ ...monoFontSx, direction: "ltr" }}>
                        {entry.cidr}
                      </Typography>
                      {entry.label && (
                        <Typography variant="caption" color="text.secondary">
                          {entry.label}
                        </Typography>
                      )}
                    </Box>
                    <IconButton size="small" color="error" onClick={() => handleDelete(entry.id)}>
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </Stack>
                </Box>
              ))
            )}
          </Card>
        </>
      )}
    </Box>
  );
}
