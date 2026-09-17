import { useEffect, useState } from "react";
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
  TextField,
  Typography,
} from "@mui/material";
import BackLink from "../components/BackLink";
import JalaliDateTimePicker from "../components/JalaliDateTimePicker";
import { useAuth } from "../context/AuthContext";
import { fetchSites } from "../api/sites";
import {
  adminUpdateLeaveRequest,
  fetchAllLeaveRequestsForSite,
  fetchLeaveRequestTypes,
} from "../api/leaveRequestsAdmin";

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

function compactTimeToString(compact) {
  if (compact == null) return "";
  const hour = Math.floor(compact / 100);
  const minute = compact % 100;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function toDateOnly(date) {
  if (!date) return null;
  const d = new Date(date);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function EditDialog({ siteId, item, types, onClose, onSaved, canEdit }) {
  const [status, setStatus] = useState(item.status);
  const [managerIdea, setManagerIdea] = useState(item.manager_idea || "");
  const [typeId, setTypeId] = useState(item.type_id || "");
  const [duration, setDuration] = useState(item.duration || "");
  const [startDate, setStartDate] = useState(item.start_date ? new Date(item.start_date) : new Date());
  const [endDate, setEndDate] = useState(item.end_date ? new Date(item.end_date) : new Date());
  const [startTimeStr, setStartTimeStr] = useState(compactTimeToString(item.start_hour) || "08:00");
  const [endTimeStr, setEndTimeStr] = useState(compactTimeToString(item.end_hour) || "10:00");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  const selectedType = types?.find((t) => t.id === typeId);
  const isHourly = selectedType ? selectedType.is_hourly : item.start_hour != null;

  async function handleSave() {
    setError("");
    setIsSaving(true);
    try {
      const payload = { manager_idea: managerIdea, duration };
      if (status !== item.status) {
        payload.is_final_approved = status === "approved" ? true : status === "rejected" ? false : null;
      }
      if (typeId && typeId !== item.type_id) {
        payload.leave_type_id = typeId;
      }
      payload.start_date = toDateOnly(startDate);
      if (isHourly) {
        payload.start_hour = timeStringToCompact(startTimeStr);
        payload.end_hour = timeStringToCompact(endTimeStr);
      } else {
        payload.end_date = toDateOnly(endDate);
      }
      await adminUpdateLeaveRequest(siteId, item.request_id, payload);
      onSaved();
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره تغییرات با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{canEdit ? "ویرایش درخواست" : "جزئیات درخواست"}</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        <Typography variant="body2" fontWeight={700}>
          {item.type_title || "—"}
        </Typography>
        {item.description && <Typography variant="body2">{item.description}</Typography>}
        {error && <Alert severity="error">{error}</Alert>}
        {canEdit ? (
          <>
            <TextField select label="وضعیت" value={status} onChange={(e) => setStatus(e.target.value)}>
              <MenuItem value="pending">در حال بررسی</MenuItem>
              <MenuItem value="approved">تائید شده</MenuItem>
              <MenuItem value="rejected">رد شده</MenuItem>
            </TextField>
            {types && types.length > 0 && (
              <TextField select label="نوع درخواست" value={typeId} onChange={(e) => setTypeId(e.target.value)}>
                {types.map((t) => (
                  <MenuItem key={t.id} value={t.id}>
                    {t.title}
                  </MenuItem>
                ))}
              </TextField>
            )}
            <Stack direction="row" spacing={1.5}>
              <JalaliDateTimePicker value={startDate} onChange={setStartDate} label="تاریخ شروع" />
              {!isHourly && <JalaliDateTimePicker value={endDate} onChange={setEndDate} label="تاریخ پایان" />}
            </Stack>
            {isHourly && (
              <Stack direction="row" spacing={1.5}>
                <TextField
                  type="time"
                  label="ساعت شروع"
                  value={startTimeStr}
                  onChange={(e) => setStartTimeStr(e.target.value)}
                  sx={{ flex: 1 }}
                  InputLabelProps={{ shrink: true }}
                />
                <TextField
                  type="time"
                  label="ساعت پایان"
                  value={endTimeStr}
                  onChange={(e) => setEndTimeStr(e.target.value)}
                  sx={{ flex: 1 }}
                  InputLabelProps={{ shrink: true }}
                />
              </Stack>
            )}
            <TextField label="مدت (خام)" value={duration} onChange={(e) => setDuration(e.target.value)} />
            <TextField
              label="نظر تأییدکننده"
              value={managerIdea}
              onChange={(e) => setManagerIdea(e.target.value)}
              multiline
              minRows={2}
            />
          </>
        ) : (
          <Chip color={STATUS_COLORS[item.status]} label={STATUS_LABELS[item.status]} sx={{ alignSelf: "start" }} />
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isSaving}>
          {canEdit ? "انصراف" : "بستن"}
        </Button>
        {canEdit && (
          <Button variant="contained" onClick={handleSave} disabled={isSaving}>
            {isSaving ? "در حال ذخیره..." : "ذخیره"}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}

export default function LeaveRequestsAdminListPage() {
  const { user } = useAuth();
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState("");
  const [requests, setRequests] = useState(null);
  const [types, setTypes] = useState([]);
  const [selectedItem, setSelectedItem] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchSites().then((data) => {
      setSites(data);
      if (data.length > 0) setSiteId(data[0].id);
    });
  }, []);

  function load() {
    if (!siteId) return;
    setError("");
    fetchAllLeaveRequestsForSite(siteId)
      .then(setRequests)
      .catch((err) => setError(err.response?.data?.detail || "دریافت درخواست‌ها با خطا مواجه شد."));
  }

  useEffect(load, [siteId]);

  const canEdit = Boolean(user?.can_manage_leave_requests);

  useEffect(() => {
    if (!siteId || !canEdit) return;
    fetchLeaveRequestTypes(siteId)
      .then(setTypes)
      .catch(() => setTypes([]));
  }, [siteId, canEdit]);

  return (
    <Box>
      <BackLink to="/access" label="بازگشت" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        همه درخواست‌های مرخصی/ماموریت
      </Typography>

      <TextField
        select
        label="سایت"
        value={siteId}
        onChange={(e) => setSiteId(e.target.value)}
        sx={{ minWidth: 240, mb: 2 }}
      >
        {sites.map((site) => (
          <MenuItem key={site.id} value={site.id}>
            {site.name}
          </MenuItem>
        ))}
      </TextField>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {requests !== null && (
        <TableContainer component={Card} variant="outlined" sx={{ mt: 3 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>نام و نام خانوادگی</TableCell>
                <TableCell>نوع درخواست</TableCell>
                <TableCell>توضیحات</TableCell>
                <TableCell>تاریخ شروع</TableCell>
                <TableCell>مدت</TableCell>
                <TableCell>وضعیت</TableCell>
                <TableCell>عملیات</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {requests.map((item) => (
                <TableRow key={item.request_id}>
                  <TableCell>{item.requester_name || item.emp_no}</TableCell>
                  <TableCell>{item.type_title || "—"}</TableCell>
                  <TableCell>{item.description || "—"}</TableCell>
                  <TableCell>
                    {item.start_date ? new Date(item.start_date).toLocaleDateString("fa-IR") : "—"}
                  </TableCell>
                  <TableCell>
                    {item.start_hour != null
                      ? `${formatCompactTime(item.start_hour)} تا ${formatCompactTime(item.end_hour)}`
                      : `${item.duration} روز`}
                  </TableCell>
                  <TableCell>
                    <Chip size="small" color={STATUS_COLORS[item.status]} label={STATUS_LABELS[item.status]} />
                  </TableCell>
                  <TableCell>
                    <Button size="small" variant="outlined" onClick={() => setSelectedItem(item)}>
                      {canEdit ? "ویرایش" : "جزئیات"}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {selectedItem && (
        <EditDialog
          siteId={siteId}
          item={selectedItem}
          types={types}
          canEdit={canEdit}
          onClose={() => setSelectedItem(null)}
          onSaved={() => {
            setSelectedItem(null);
            load();
          }}
        />
      )}
    </Box>
  );
}
