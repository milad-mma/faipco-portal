import { useEffect, useState } from "react";
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { fetchNoticeReaders } from "../api/notices";
import { monoFontSx } from "../theme";

export default function NoticeReadersDialog({ noticeId, onClose }) {
  const [readers, setReaders] = useState([]);

  useEffect(() => {
    if (noticeId) {
      fetchNoticeReaders(noticeId).then(setReaders);
    }
  }, [noticeId]);

  return (
    <Dialog open={Boolean(noticeId)} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>چه کسانی این اطلاعیه را دیده‌اند</DialogTitle>
      <DialogContent>
        {readers.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
            هنوز کسی این اطلاعیه را باز نکرده است.
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>نام</TableCell>
                  <TableCell>کد پرسنلی</TableCell>
                  <TableCell>زمان مشاهده</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {readers.map((r) => (
                  <TableRow key={r.user_id}>
                    <TableCell>
                      {r.first_name ? `${r.first_name} ${r.last_name}` : "—"}
                    </TableCell>
                    <TableCell sx={monoFontSx}>{r.personnel_code || "—"}</TableCell>
                    <TableCell sx={monoFontSx}>{new Date(r.read_at).toLocaleString("fa-IR")}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DialogContent>
      <DialogActions sx={{ p: 2.5 }}>
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
}
