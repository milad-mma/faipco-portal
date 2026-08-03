import { useState } from "react";
import {
  Button,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import { monoFontSx } from "../theme";
import NoticeReadersDialog from "./NoticeReadersDialog";

const PRIORITY_LABELS = {
  low: "کم",
  normal: "عادی",
  high: "بالا",
  urgent: "فوری",
};

export default function NoticeReportTable({ notices, showSender = false }) {
  const [readersNoticeId, setReadersNoticeId] = useState(null);

  if (notices.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
        هنوز اطلاعیه‌ای ثبت نشده.
      </Typography>
    );
  }

  return (
    <>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>تاریخ و ساعت ارسال</TableCell>
              {showSender && <TableCell>فرستنده</TableCell>}
              <TableCell>عنوان</TableCell>
              <TableCell>اولویت</TableCell>
              <TableCell>مقصد(ها)</TableCell>
              <TableCell align="center">مخاطبان</TableCell>
              <TableCell align="center">دیده‌شده</TableCell>
              <TableCell align="center">جزئیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {notices.map((n) => (
              <TableRow key={n.id} hover>
                <TableCell sx={monoFontSx}>
                  {new Date(n.publish_at || n.created_at).toLocaleString("fa-IR")}
                </TableCell>
                {showSender && <TableCell>{n.sender_name}</TableCell>}
                <TableCell>{n.title}</TableCell>
                <TableCell>
                  <Chip size="small" label={PRIORITY_LABELS[n.priority] || n.priority} />
                </TableCell>
                <TableCell>
                  <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                    {n.targets.map((t, i) => (
                      <Chip key={i} size="small" variant="outlined" label={t.label} />
                    ))}
                  </Stack>
                </TableCell>
                <TableCell sx={monoFontSx} align="center">
                  {n.audience_count}
                </TableCell>
                <TableCell sx={monoFontSx} align="center">
                  {n.read_count} / {n.audience_count}
                </TableCell>
                <TableCell align="center">
                  <Button
                    size="small"
                    startIcon={<VisibilityOutlinedIcon />}
                    onClick={() => setReadersNoticeId(n.id)}
                  >
                    چه کسانی دیدند
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <NoticeReadersDialog noticeId={readersNoticeId} onClose={() => setReadersNoticeId(null)} />
    </>
  );
}
