// «امضای من» (پنل کاربری، دارندگان دسترسی اتوماسیون): نمایش امضای فعال، رسم با موس/لمس/قلم یا بارگذاری تصویر،
// حذف اختیاری پس‌زمینه‌ی روشن، غیرفعال‌سازی. سرور تصویر را پاک‌سازی، برش و به PNG تبدیل می‌کند.
// هر ثبت نسخه‌ی تازه است؛ امضای قبلی روی نامه‌های قبلی می‌ماند.
import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  Tab,
  Tabs,
  Typography,
} from "@mui/material";
import { deactivateMySignature, fetchMySignature, fetchMySignatureBlob, saveMySignature } from "../../api/automationLetters";
import { toPersianDigits } from "../../utils/searchText";

// بوم رسم با Pointer Events (موس، لمس، قلم)؛ خروجی PNG شفاف
function SignaturePad({ padRef, onChange }) {
  const canvasRef = useRef(null);
  const drawing = useRef(false);
  const last = useRef(null);

  useEffect(() => {
    const c = canvasRef.current;
    const ratio = window.devicePixelRatio || 1;
    c.width = c.clientWidth * ratio;
    c.height = c.clientHeight * ratio;
    const ctx = c.getContext("2d");
    ctx.scale(ratio, ratio);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "#0b2a6b";
    padRef.current = {
      clear: () => {
        ctx.clearRect(0, 0, c.width, c.height);
        onChange(false);
      },
      toBlob: () => new Promise((resolve) => c.toBlob(resolve, "image/png")),
    };
  }, [padRef, onChange]);

  const pos = (e) => {
    const r = canvasRef.current.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top, p: e.pressure || 0.5 };
  };
  const down = (e) => {
    e.preventDefault();
    canvasRef.current.setPointerCapture(e.pointerId);
    drawing.current = true;
    last.current = pos(e);
  };
  const move = (e) => {
    if (!drawing.current) return;
    const ctx = canvasRef.current.getContext("2d");
    const p = pos(e);
    ctx.lineWidth = 1.5 + p.p * 2.5;
    ctx.beginPath();
    ctx.moveTo(last.current.x, last.current.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    last.current = p;
    onChange(true);
  };
  const up = () => {
    drawing.current = false;
  };

  return (
    <Box
      component="canvas"
      ref={canvasRef}
      onPointerDown={down}
      onPointerMove={move}
      onPointerUp={up}
      onPointerCancel={up}
      sx={{ width: "100%", height: 200, border: "1px dashed", borderColor: "divider", borderRadius: 2, bgcolor: "#fff", touchAction: "none", cursor: "crosshair", display: "block" }}
    />
  );
}

export default function MySignatureDialog({ open, onClose }) {
  const [data, setData] = useState(null);
  const [imgUrl, setImgUrl] = useState(null);
  const [mode, setMode] = useState("view"); // view | draw | upload
  const [hasInk, setHasInk] = useState(false);
  const [file, setFile] = useState(null);
  const [filePreview, setFilePreview] = useState(null);
  const [removeBg, setRemoveBg] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const padRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    setMode("view");
    setError("");
    fetchMySignature()
      .then(setData)
      .catch((err) => setError(err.response?.data?.detail || "دریافت امضا ناموفق بود."));
  }, [open]);

  // تصویر امضای فعال
  useEffect(() => {
    if (!data?.active) {
      setImgUrl(null);
      return undefined;
    }
    let url = null;
    let alive = true;
    fetchMySignatureBlob(data.active.id)
      .then((b) => {
        if (!alive) return;
        url = URL.createObjectURL(b);
        setImgUrl(url);
      })
      .catch(() => {});
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [data?.active?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!file) {
      setFilePreview(null);
      return undefined;
    }
    const u = URL.createObjectURL(file);
    setFilePreview(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);

  async function save() {
    setBusy(true);
    setError("");
    try {
      const blob = mode === "draw" ? await padRef.current.toBlob() : file;
      setData(await saveMySignature(blob, mode, mode === "upload" && removeBg));
      setMode("view");
      setFile(null);
      setHasInk(false);
    } catch (err) {
      setError(err.response?.data?.detail || "ثبت امضا ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  async function deactivate() {
    setBusy(true);
    setError("");
    try {
      setData(await deactivateMySignature());
    } catch (err) {
      setError(err.response?.data?.detail || "انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} fullWidth maxWidth="sm">
      <DialogTitle>امضای من</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          این امضا وقتی «امضا شود» را در نوشتن نامه بزنید، پایین نامه کنار نام و سمت شما می‌نشیند. هیچ‌کس دیگری نمی‌تواند با
          امضای شما نامه امضا کند. امضای تصویری تأیید سازمانی داخلی است، نه امضای دیجیتال.
        </Typography>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {!data && !error && <CircularProgress size={24} />}

        {data && mode === "view" && (
          <Stack spacing={2} alignItems="center">
            {data.active ? (
              <>
                <Box sx={{ p: 2, border: "1px solid", borderColor: "divider", borderRadius: 2, bgcolor: "#fff", width: "100%", textAlign: "center" }}>
                  {imgUrl ? <Box component="img" src={imgUrl} alt="امضا" sx={{ maxWidth: "100%", maxHeight: 140 }} /> : <CircularProgress size={20} />}
                </Box>
                <Typography variant="caption" color="text.secondary">
                  نسخه‌ی {toPersianDigits(data.active.version_no)} — ثبت {new Date(data.active.created_at).toLocaleDateString("fa-IR")}
                </Typography>
              </>
            ) : (
              <Alert severity="info" sx={{ width: "100%" }}>هنوز امضایی ثبت نکرده‌اید.</Alert>
            )}
            <Stack direction="row" spacing={1} flexWrap="wrap" justifyContent="center">
              <Button variant="contained" onClick={() => setMode("draw")} disabled={busy} sx={{ height: 40 }}>رسم امضا</Button>
              <Button variant="outlined" onClick={() => setMode("upload")} disabled={busy} sx={{ height: 40 }}>بارگذاری تصویر</Button>
              {data.active && (
                <Button color="error" onClick={deactivate} disabled={busy} sx={{ height: 40 }}>غیرفعال کردن</Button>
              )}
            </Stack>
          </Stack>
        )}

        {data && mode !== "view" && (
          <>
            <Tabs value={mode} onChange={(_, v) => setMode(v)} sx={{ mb: 2 }}>
              <Tab value="draw" label="رسم" />
              <Tab value="upload" label="بارگذاری" />
            </Tabs>
            {mode === "draw" && (
              <Stack spacing={1}>
                <SignaturePad padRef={padRef} onChange={setHasInk} />
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="caption" color="text.secondary">با موس، انگشت یا قلم داخل کادر امضا کنید.</Typography>
                  <Button size="small" onClick={() => padRef.current?.clear()} disabled={busy}>پاک کردن</Button>
                </Stack>
              </Stack>
            )}
            {mode === "upload" && (
              <Stack spacing={1.5}>
                <Button variant="outlined" component="label" sx={{ height: 40, alignSelf: "flex-start" }}>
                  انتخاب تصویر (PNG، JPG یا WEBP تا ۲ مگابایت)
                  <input hidden type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setFile(e.target.files?.[0] || null)} />
                </Button>
                {filePreview && (
                  <Box sx={{ p: 1, border: "1px solid", borderColor: "divider", borderRadius: 2, bgcolor: "#fff", textAlign: "center" }}>
                    <Box component="img" src={filePreview} alt="" sx={{ maxWidth: "100%", maxHeight: 160 }} />
                  </Box>
                )}
                <FormControlLabel
                  control={<Checkbox checked={removeBg} onChange={(e) => setRemoveBg(e.target.checked)} />}
                  label="حذف پس‌زمینه‌ی سفید کاغذ"
                />
              </Stack>
            )}
            <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 1 }}>
              حاشیه‌ی خالی خودکار بریده می‌شود. با ثبت امضای جدید، امضای قبلی فقط برای نامه‌های بعدی کنار می‌رود.
            </Typography>
          </>
        )}
      </DialogContent>
      <DialogActions>
        {mode !== "view" ? (
          <>
            <Button onClick={() => setMode("view")} disabled={busy}>انصراف</Button>
            <Button variant="contained" onClick={save} disabled={busy || (mode === "draw" ? !hasInk : !file)}>
              {busy ? "در حال ثبت..." : "ثبت امضا"}
            </Button>
          </>
        ) : (
          <Button onClick={onClose} disabled={busy}>بستن</Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
