import { useEffect, useState } from "react";
import { Box, Button, CircularProgress, Snackbar, Typography } from "@mui/material";
import SystemUpdateAltOutlinedIcon from "@mui/icons-material/SystemUpdateAltOutlined";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import {
  applyPendingUpdate, consumeAppliedUpdateReceipt, UPDATE_READY_EVENT,
} from "../utils/serviceWorker";
import {
  UPDATE_TITLE, UPDATE_ACTION, UPDATE_ACTIVATING_TEXT, UPDATE_ACTIVATING_ACTION,
  UPDATE_RELOADING_TEXT, UPDATE_RELOADING_ACTION, UPDATE_RETRY_ACTION,
  updateReadyDescription, updateSuccessMessage, updateErrorMessage,
} from "../utils/updateFeedback";

/** Unified PWA/TWA prompt: visible feedback on tap, then one-time success
 * confirmation on the reloaded page. Never remove authentication data. */
export default function UpdatePrompt() {
  const [isOpen, setIsOpen] = useState(false);
  const [phase, setPhase] = useState("idle");
  const [error, setError] = useState(null);
  const [updateKind, setUpdateKind] = useState("release");
  const [completedKind, setCompletedKind] = useState(() => consumeAppliedUpdateReceipt());

  useEffect(() => {
    function handleUpdateReady(event) {
      setUpdateKind(event.detail?.kind === "cache_refresh" ? "cache_refresh" : "release");
      setError(null);
      setPhase("idle");
      setIsOpen(true);
    }
    window.addEventListener(UPDATE_READY_EVENT, handleUpdateReady);
    return () => window.removeEventListener(UPDATE_READY_EVENT, handleUpdateReady);
  }, []);

  async function handleReloadClick() {
    if (phase !== "idle") return;
    setPhase("activating");
    setError(null);
    try {
      const result = await applyPendingUpdate({ onPhase: setPhase });
      if (!result?.ok) {
        setError(updateErrorMessage(result?.reason));
        setPhase("idle");
      }
      // On success, keep the visible "opening" state until navigation occurs.
    } catch {
      setError(updateErrorMessage("unexpected"));
      setPhase("idle");
    }
  }

  const isApplying = phase !== "idle";
  const showingCompletion = !isOpen && completedKind != null;
  const message = showingCompletion
    ? <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        <CheckCircleOutlineIcon color="success" fontSize="small" />
        <Typography variant="body2">{updateSuccessMessage(completedKind)}</Typography>
      </Box>
    : <Box sx={{ maxWidth: 420, py: 0.25 }}>
        <Typography variant="subtitle2" fontWeight={700}>
          {error ? "به‌روزرسانی کامل نشد" : UPDATE_TITLE}
        </Typography>
        <Typography variant="body2" sx={{ mt: 0.4 }}>
          {error || (phase === "reloading"
            ? UPDATE_RELOADING_TEXT
            : phase === "activating"
              ? UPDATE_ACTIVATING_TEXT
              : updateReadyDescription(updateKind))}
        </Typography>
      </Box>;

  return (
    <Snackbar
      open={isOpen || showingCompletion}
      anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      autoHideDuration={showingCompletion ? 6500 : null}
      onClose={(_event, reason) => { if (reason !== "clickaway" && showingCompletion) setCompletedKind(null); }}
      message={message}
      action={isOpen ? (
        <Button
          color="inherit"
          size="small"
          disabled={isApplying}
          startIcon={isApplying
            ? <CircularProgress size={16} color="inherit" />
            : <SystemUpdateAltOutlinedIcon fontSize="small" />}
          onClick={handleReloadClick}
          sx={{ minHeight: 40, whiteSpace: "nowrap", "&.Mui-disabled": { color: "inherit", opacity: 0.8 } }}
        >
          {phase === "reloading" ? UPDATE_RELOADING_ACTION
            : phase === "activating" ? UPDATE_ACTIVATING_ACTION
              : error ? UPDATE_RETRY_ACTION : UPDATE_ACTION}
        </Button>
      ) : null}
      sx={{ "& .MuiSnackbarContent-root": { flexWrap: "wrap", gap: 1.5 } }}
    />
  );
}
