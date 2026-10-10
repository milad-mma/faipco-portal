import { Button, Dialog, DialogActions, DialogContent, Typography } from "@mui/material";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";

/**
 * دیالوگ نتیجه‌ی یک عملیات، با همان ظاهر ماژول بیمه تکمیلی: آیکن بزرگ موفق/خطا، متن و دکمه‌ی «متوجه شدم».
 * ورودی: result ({ severity: "success" | "error", text } یا null = بسته) و onClose.
 */
export default function ResultDialog({ result, onClose }) {
  const success = result?.severity !== "error";
  return (
    <Dialog open={Boolean(result)} onClose={onClose} fullWidth maxWidth="xs">
      <DialogContent sx={{ textAlign: "center", pt: 4 }}>
        {success ? (
          <CheckCircleOutlineIcon color="success" sx={{ fontSize: 64 }} />
        ) : (
          <ErrorOutlineIcon color="error" sx={{ fontSize: 64 }} />
        )}
        <Typography fontWeight={700} sx={{ mt: 1.5, whiteSpace: "pre-line" }}>
          {result?.text}
        </Typography>
      </DialogContent>
      <DialogActions sx={{ justifyContent: "center", pb: 2.5 }}>
        <Button variant="contained" color={success ? "success" : "primary"} onClick={onClose} autoFocus>
          متوجه شدم
        </Button>
      </DialogActions>
    </Dialog>
  );
}
