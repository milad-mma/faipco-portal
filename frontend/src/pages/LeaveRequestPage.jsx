import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import BackLink from "../components/BackLink";
import JalaliDateTimePicker from "../components/JalaliDateTimePicker";
import {
  decideLeaveRequest,
  fetchActiveLeaveRequestTypes,
  fetchMyLeaveRequests,
  fetchPendingLeaveRequestsForMe,
  submitLeaveRequest,
} from "../api/leaveRequests";

const STATUS_LABELS = { pending: "در حال بررسی", approved: "تائید شده", rejected: "رد شده" };
const STATUS_COLORS = { pending: "warning", approved: "success", rejected: "error" };

function formatCompactTime(compact) {
  if (compact == null) return "—";
  const hour = Math.floor(compact / 100);
  const minute = compact % 100;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function timeStringToCompact(timeStr) {
  if (!timeStr) return null;
  const [h, m] = timeStr.split(":").map(Number);
  return h * 100 + m;
}

function SubmitRequestForm({ onSubmitted }) {
  const [types, setTypes] = useState(null);
  const [typeId, setTypeId] = useState("");
  const [startDate, setStartDate] = useState(new Date());
  const [endDate, setEndDate] = useState(new Date());
  const [startTimeStr, setStartTimeStr] = useState("08:00");
  const [endTimeStr, setEndTimeStr] = useState("10:00");
  const [description, setDescription] = useState("");
  const [source, setSource] = useState("");
  const [destination, setDestination] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    fetchActiveLeaveRequestTypes().then(setTypes);
  }, []);

  const selectedType = types?.find((t) => t.id === Number(typeId));

  async function handleSubmit() {
    setError("");
    if (!selectedType) {
      setError("لطفاً نوع درخواست را انتخاب کنید");
      return;
    }
    setIsSubmitting(true);
    try {
      const toDateOnly = (d) =>
        `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      await submitLeaveRequest({
        leave_type_id: selectedType.id,
        start_date: toDateOnly(startDate),
        end_date: selectedType.is_hourly ? null : toDateOnly(endDate),
        start_hour: selectedType.is_hourly ? timeStringToCompact(startTimeStr) : null,
        end_hour: selectedType.is_hourly ? timeStringToCompact(endTimeStr) : null,
        description,
        source: selectedType.is_mission ? source : null,
        destination: selectedType.is_mission ? destination : null,
      });
      setDescription("");
      setSource("");
      setDestination("");
      onSubmitted();
    } catch (err) {
      setError(err.response?.data?.detail || "ثبت درخواست با خطا مواجه شد.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (types === null) return null;

  if (types.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        هنوز هیچ نوع درخواستی برای سایت شما تعریف نشده - لطفاً با منابع انسانی هماهنگ کنید.
      </Typography>
    );
  }

  return (
    <Card variant="outlined" sx={{ p: 2, maxWidth: 480 }}>
      <Stack spacing={2}>
        {error && <Alert severity="error">{error}</Alert>}
        <TextField select label="نوع درخواست" value={typeId} onChange={(e) => setTypeId(e.target.value)}>
          {types.map((t) => (
            <MenuItem key={t.id} value={t.id}>
              {t.title}
            </MenuItem>
          ))}
        </TextField>

        {selectedType && (
          <>
            <JalaliDateTimePicker value={startDate} onChange={setStartDate} label="تاریخ شروع" />
            {selectedType.is_hourly ? (
              <Stack direction="row" spacing={1.5}>
                <TextField
                  type="time"
                  label="ساعت شروع"
                  value={startTimeStr}
                  onChange={(e) => setStartTimeStr(e.target.value)}
                  sx={{ flex: 1 }}
                />
                <TextField
                  type="time"
                  label="ساعت پایان"
                  value={endTimeStr}
                  onChange={(e) => setEndTimeStr(e.target.value)}
                  sx={{ flex: 1 }}
                />
              </Stack>
            ) : (
              <JalaliDateTimePicker value={endDate} onChange={setEndDate} label="تاریخ پایان" />
            )}

            {selectedType.is_mission && (
              <Stack direction="row" spacing={1.5}>
                <TextField label="مبدأ" value={source} onChange={(e) => setSource(e.target.value)} sx={{ flex: 1 }} />
                <TextField
                  label="مقصد"
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  sx={{ flex: 1 }}
                />
              </Stack>
            )}

            <TextField
              label="توضیحات"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              multiline
              minRows={2}
            />

            <Button variant="contained" onClick={handleSubmit} disabled={isSubmitting}>
              {isSubmitting ? "در حال ثبت..." : "ثبت درخواست"}
            </Button>
          </>
        )}
      </Stack>
    </Card>
  );
}

function MyRequestsTable({ items }) {
  if (items.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        هنوز هیچ درخواستی ثبت نکرده‌اید.
      </Typography>
    );
  }
  return (
    <TableContainer component={Card} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>توضیحات</TableCell>
            <TableCell>تاریخ شروع</TableCell>
            <TableCell>مدت</TableCell>
            <TableCell>وضعیت</TableCell>
            <TableCell>نظر تأییدکننده</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {items.map((item) => (
            <TableRow key={item.request_id}>
              <TableCell>{item.description}</TableCell>
              <TableCell>{item.start_date ? new Date(item.start_date).toLocaleDateString("fa-IR") : "—"}</TableCell>
              <TableCell>
                {item.start_hour != null
                  ? `${formatCompactTime(item.start_hour)} تا ${formatCompactTime(item.end_hour)}`
                  : `${item.duration} روز`}
              </TableCell>
              <TableCell>
                <Chip size="small" color={STATUS_COLORS[item.status]} label={STATUS_LABELS[item.status]} />
              </TableCell>
              <TableCell>{item.manager_idea || "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

function DecideDialog({ item, onClose, onDecided }) {
  const [managerIdea, setManagerIdea] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleDecide(approved) {
    setError("");
    setIsSubmitting(true);
    try {
      await decideLeaveRequest(item.request_id, approved, managerIdea);
      onDecided();
    } catch (err) {
      setError(err.response?.data?.detail || "ثبت تصمیم با خطا مواجه شد.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>تصمیم برای درخواست</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        <Typography variant="body2">{item.description}</Typography>
        {error && <Alert severity="error">{error}</Alert>}
        <TextField
          label="نظر (اختیاری)"
          value={managerIdea}
          onChange={(e) => setManagerIdea(e.target.value)}
          multiline
          minRows={2}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isSubmitting}>
          انصراف
        </Button>
        <Button color="error" onClick={() => handleDecide(false)} disabled={isSubmitting}>
          رد
        </Button>
        <Button variant="contained" color="success" onClick={() => handleDecide(true)} disabled={isSubmitting}>
          تائید
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function PendingApprovalTable({ items, onDecide }) {
  if (items.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        فعلاً هیچ درخواستی منتظر تصمیم شما نیست.
      </Typography>
    );
  }
  return (
    <TableContainer component={Card} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>پرسنل</TableCell>
            <TableCell>توضیحات</TableCell>
            <TableCell>تاریخ شروع</TableCell>
            <TableCell>مدت</TableCell>
            <TableCell>عملیات</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {items.map((item) => (
            <TableRow key={item.request_id}>
              <TableCell>{item.emp_no}</TableCell>
              <TableCell>{item.description}</TableCell>
              <TableCell>{item.start_date ? new Date(item.start_date).toLocaleDateString("fa-IR") : "—"}</TableCell>
              <TableCell>
                {item.start_hour != null
                  ? `${formatCompactTime(item.start_hour)} تا ${formatCompactTime(item.end_hour)}`
                  : `${item.duration} روز`}
              </TableCell>
              <TableCell>
                <Button size="small" variant="outlined" onClick={() => onDecide(item)}>
                  بررسی
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export default function LeaveRequestPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = ["submit", "my-requests", "pending"].indexOf(searchParams.get("tab"));
  const [tab, setTab] = useState(tabFromUrl >= 0 ? tabFromUrl : 0);
  const [myRequests, setMyRequests] = useState(null);
  const [pending, setPending] = useState(null);
  const [decidingItem, setDecidingItem] = useState(null);
  const [error, setError] = useState("");

  function loadMyRequests() {
    fetchMyLeaveRequests()
      .then(setMyRequests)
      .catch((err) => setError(err.response?.data?.detail || "دریافت درخواست‌های من با خطا مواجه شد."));
  }

  function loadPending() {
    fetchPendingLeaveRequestsForMe()
      .then(setPending)
      .catch(() => setPending([]));
  }

  useEffect(() => {
    loadMyRequests();
    loadPending();
  }, []);

  function handleTabChange(newIndex) {
    setTab(newIndex);
    setSearchParams({ tab: ["submit", "my-requests", "pending"][newIndex] });
  }

  const pendingCount = pending?.length || 0;
  const hasPending = pendingCount > 0;

  return (
    <Box>
      <BackLink to="/my-dashboard" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        درخواست مرخصی/ماموریت
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Tabs value={tab} onChange={(_, v) => handleTabChange(v)} sx={{ mb: 2 }}>
        <Tab label="ثبت درخواست جدید" />
        <Tab label="درخواست‌های من" />
        {hasPending && <Tab label={`منتظر تصمیم من (${pendingCount})`} />}
      </Tabs>

      {tab === 0 && (
        <SubmitRequestForm
          onSubmitted={() => {
            handleTabChange(1);
            loadMyRequests();
          }}
        />
      )}

      {tab === 1 && myRequests !== null && <MyRequestsTable items={myRequests} />}

      {tab === 2 && hasPending && <PendingApprovalTable items={pending} onDecide={setDecidingItem} />}

      {decidingItem && (
        <DecideDialog
          item={decidingItem}
          onClose={() => setDecidingItem(null)}
          onDecided={() => {
            setDecidingItem(null);
            loadPending();
            loadMyRequests();
          }}
        />
      )}
    </Box>
  );
}
