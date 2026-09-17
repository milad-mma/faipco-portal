import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Card,
  Chip,
  IconButton,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TextField,
  Typography,
} from "@mui/material";
import CheckOutlinedIcon from "@mui/icons-material/CheckOutlined";
import CloseOutlinedIcon from "@mui/icons-material/CloseOutlined";
import BackLink from "../components/BackLink";
import JalaliDateTimePicker from "../components/JalaliDateTimePicker";
import { useAuth } from "../context/AuthContext";
import { fetchSites } from "../api/sites";
import { adminUpdateLeaveRequest, fetchAllLeaveRequestsForSite, fetchLeaveRequestTypes } from "../api/leaveRequestsAdmin";

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

// ⚠️ طبق درخواست صریح کاربر: «مدت» دیگر یک فیلد خام نیست - همیشه از
// روی ساعت/تاریخ شروع و پایان محاسبه و نمایش داده می‌شود (نه ویرایش
// مستقیم) - ساعتی: به ساعت و دقیقه؛ روزانه: به تعداد روز.
function formatDuration(item) {
  if (item.start_hour != null && item.end_hour != null) {
    const startMinutes = Math.floor(item.start_hour / 100) * 60 + (item.start_hour % 100);
    const endMinutes = Math.floor(item.end_hour / 100) * 60 + (item.end_hour % 100);
    const diff = endMinutes - startMinutes;
    if (diff <= 0) return "—";
    const h = Math.floor(diff / 60);
    const m = diff % 60;
    return h > 0 ? `${h} ساعت${m > 0 ? ` و ${m} دقیقه` : ""}` : `${m} دقیقه`;
  }
  if (item.start_date && item.end_date) {
    const start = new Date(item.start_date);
    const end = new Date(item.end_date);
    const days = Math.round((end - start) / (1000 * 60 * 60 * 24)) + 1;
    return days > 0 ? `${days} روز` : "—";
  }
  return "—";
}

function EditableText({ value, onSave, multiline }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value || "");
  const [saving, setSaving] = useState(false);

  if (!editing) {
    return (
      <Box
        onClick={() => {
          setDraft(value || "");
          setEditing(true);
        }}
        sx={{ cursor: "pointer", minHeight: 24, "&:hover": { bgcolor: "action.hover" }, borderRadius: 1, px: 0.5 }}
      >
        {value || "—"}
      </Box>
    );
  }
  return (
    <Stack direction="row" spacing={0.5} alignItems="center">
      <TextField
        size="small"
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        multiline={multiline}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !multiline) handleSave();
          if (e.key === "Escape") setEditing(false);
        }}
      />
      <IconButton size="small" color="success" disabled={saving} onClick={handleSave}>
        <CheckOutlinedIcon fontSize="small" />
      </IconButton>
      <IconButton size="small" onClick={() => setEditing(false)} disabled={saving}>
        <CloseOutlinedIcon fontSize="small" />
      </IconButton>
    </Stack>
  );

  async function handleSave() {
    setSaving(true);
    await onSave(draft);
    setSaving(false);
    setEditing(false);
  }
}

function EditableSelect({ value, options, onSave, renderValue }) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  if (!editing) {
    return (
      <Box
        onClick={() => setEditing(true)}
        sx={{ cursor: "pointer", minHeight: 24, "&:hover": { bgcolor: "action.hover" }, borderRadius: 1, px: 0.5 }}
      >
        {renderValue(value)}
      </Box>
    );
  }
  return (
    <TextField
      select
      size="small"
      autoFocus
      value={value}
      disabled={saving}
      onChange={async (e) => {
        setSaving(true);
        await onSave(e.target.value);
        setSaving(false);
        setEditing(false);
      }}
      onBlur={() => setEditing(false)}
      sx={{ minWidth: 140 }}
    >
      {options.map((o) => (
        <MenuItem key={o.value} value={o.value}>
          {o.label}
        </MenuItem>
      ))}
    </TextField>
  );
}

function EditableTimeRange({ item, onSave }) {
  const isHourly = item.start_hour != null;
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [startDate, setStartDate] = useState(item.start_date ? new Date(item.start_date) : new Date());
  const [endDate, setEndDate] = useState(item.end_date ? new Date(item.end_date) : new Date());
  const [startTimeStr, setStartTimeStr] = useState(compactTimeToString(item.start_hour) || "08:00");
  const [endTimeStr, setEndTimeStr] = useState(compactTimeToString(item.end_hour) || "10:00");

  if (!editing) {
    const label = isHourly
      ? `${formatCompactTime(item.start_hour)} تا ${formatCompactTime(item.end_hour)}`
      : `${item.start_date ? new Date(item.start_date).toLocaleDateString("fa-IR") : "—"} تا ${
          item.end_date ? new Date(item.end_date).toLocaleDateString("fa-IR") : "—"
        }`;
    return (
      <Box
        onClick={() => setEditing(true)}
        sx={{ cursor: "pointer", minHeight: 24, "&:hover": { bgcolor: "action.hover" }, borderRadius: 1, px: 0.5 }}
      >
        {label}
      </Box>
    );
  }

  async function handleSave() {
    setSaving(true);
    const payload = { start_date: toDateOnly(startDate) };
    if (isHourly) {
      payload.start_hour = timeStringToCompact(startTimeStr);
      payload.end_hour = timeStringToCompact(endTimeStr);
    } else {
      payload.end_date = toDateOnly(endDate);
    }
    await onSave(payload);
    setSaving(false);
    setEditing(false);
  }

  return (
    <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 260 }}>
      {isHourly ? (
        <>
          <JalaliDateTimePicker value={startDate} onChange={setStartDate} label="تاریخ" showTime={false} />
          <TextField
            type="time"
            size="small"
            label="شروع"
            value={startTimeStr}
            onChange={(e) => setStartTimeStr(e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ width: 110 }}
          />
          <TextField
            type="time"
            size="small"
            label="پایان"
            value={endTimeStr}
            onChange={(e) => setEndTimeStr(e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ width: 110 }}
          />
        </>
      ) : (
        <>
          <JalaliDateTimePicker value={startDate} onChange={setStartDate} label="تاریخ شروع" showTime={false} />
          <JalaliDateTimePicker value={endDate} onChange={setEndDate} label="تاریخ پایان" showTime={false} />
        </>
      )}
      <IconButton size="small" color="success" disabled={saving} onClick={handleSave}>
        <CheckOutlinedIcon fontSize="small" />
      </IconButton>
      <IconButton size="small" onClick={() => setEditing(false)} disabled={saving}>
        <CloseOutlinedIcon fontSize="small" />
      </IconButton>
    </Stack>
  );
}

const STATUS_OPTIONS = [
  { value: "pending", label: "در حال بررسی" },
  { value: "approved", label: "تائید شده" },
  { value: "rejected", label: "رد شده" },
];

export default function LeaveRequestsAdminListPage() {
  const { user } = useAuth();
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState("");
  const [requests, setRequests] = useState(null);
  const [types, setTypes] = useState([]);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [sortField, setSortField] = useState("request_id");
  const [sortDir, setSortDir] = useState("desc");

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

  async function handleFieldSave(requestId, payload) {
    setError("");
    try {
      await adminUpdateLeaveRequest(siteId, requestId, payload);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره تغییرات با خطا مواجه شد.");
    }
  }

  function handleSort(field) {
    if (sortField === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  }

  const visibleRequests = useMemo(() => {
    if (!requests) return [];
    const term = search.trim().toLowerCase();
    let filtered = requests;
    if (term) {
      filtered = requests.filter((item) =>
        [item.requester_name, item.type_title, item.description, String(item.emp_no)]
          .filter(Boolean)
          .some((field) => String(field).toLowerCase().includes(term))
      );
    }
    const sorted = [...filtered].sort((a, b) => {
      let av = a[sortField];
      let bv = b[sortField];
      if (sortField === "start_date") {
        av = av ? new Date(av).getTime() : 0;
        bv = bv ? new Date(bv).getTime() : 0;
      } else {
        av = (av ?? "").toString();
        bv = (bv ?? "").toString();
      }
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return sorted;
  }, [requests, search, sortField, sortDir]);

  return (
    <Box>
      <BackLink to="/access" label="بازگشت" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        درخواست‌های مرخصی/ماموریت
      </Typography>

      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
        <TextField select label="سایت" value={siteId} onChange={(e) => setSiteId(e.target.value)} sx={{ minWidth: 240 }}>
          {sites.map((site) => (
            <MenuItem key={site.id} value={site.id}>
              {site.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          label="جست‌وجو"
          placeholder="نام، نوع، توضیحات..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ minWidth: 240 }}
        />
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {requests !== null && (
        <TableContainer component={Card} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>
                  <TableSortLabel
                    active={sortField === "requester_name"}
                    direction={sortField === "requester_name" ? sortDir : "asc"}
                    onClick={() => handleSort("requester_name")}
                  >
                    نام و نام خانوادگی
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortField === "type_title"}
                    direction={sortField === "type_title" ? sortDir : "asc"}
                    onClick={() => handleSort("type_title")}
                  >
                    نوع درخواست
                  </TableSortLabel>
                </TableCell>
                <TableCell>توضیحات</TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortField === "start_date"}
                    direction={sortField === "start_date" ? sortDir : "asc"}
                    onClick={() => handleSort("start_date")}
                  >
                    بازه زمانی
                  </TableSortLabel>
                </TableCell>
                <TableCell>مدت</TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortField === "status"}
                    direction={sortField === "status" ? sortDir : "asc"}
                    onClick={() => handleSort("status")}
                  >
                    وضعیت
                  </TableSortLabel>
                </TableCell>
                <TableCell>نظر تأییدکننده</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {visibleRequests.map((item) => (
                <TableRow key={item.request_id}>
                  <TableCell>{item.requester_name || item.emp_no}</TableCell>
                  <TableCell>
                    {canEdit && types.length > 0 ? (
                      <EditableSelect
                        value={item.type_id || ""}
                        options={types.map((t) => ({ value: t.id, label: t.title }))}
                        renderValue={() => item.type_title || "—"}
                        onSave={(v) => handleFieldSave(item.request_id, { leave_type_id: v })}
                      />
                    ) : (
                      item.type_title || "—"
                    )}
                  </TableCell>
                  <TableCell>
                    {canEdit ? (
                      <EditableText
                        value={item.description}
                        multiline
                        onSave={(v) => handleFieldSave(item.request_id, { description: v })}
                      />
                    ) : (
                      item.description || "—"
                    )}
                  </TableCell>
                  <TableCell>
                    {canEdit ? (
                      <EditableTimeRange item={item} onSave={(payload) => handleFieldSave(item.request_id, payload)} />
                    ) : item.start_hour != null ? (
                      `${formatCompactTime(item.start_hour)} تا ${formatCompactTime(item.end_hour)}`
                    ) : (
                      `${item.start_date ? new Date(item.start_date).toLocaleDateString("fa-IR") : "—"} تا ${
                        item.end_date ? new Date(item.end_date).toLocaleDateString("fa-IR") : "—"
                      }`
                    )}
                  </TableCell>
                  <TableCell>{formatDuration(item)}</TableCell>
                  <TableCell>
                    {canEdit ? (
                      <EditableSelect
                        value={item.status}
                        options={STATUS_OPTIONS}
                        renderValue={(v) => <Chip size="small" color={STATUS_COLORS[v]} label={STATUS_LABELS[v]} />}
                        onSave={(v) =>
                          handleFieldSave(item.request_id, {
                            is_final_approved: v === "approved" ? true : v === "rejected" ? false : null,
                          })
                        }
                      />
                    ) : (
                      <Chip size="small" color={STATUS_COLORS[item.status]} label={STATUS_LABELS[item.status]} />
                    )}
                  </TableCell>
                  <TableCell>
                    {canEdit ? (
                      <EditableText
                        value={item.manager_idea}
                        multiline
                        onSave={(v) => handleFieldSave(item.request_id, { manager_idea: v })}
                      />
                    ) : (
                      item.manager_idea || "—"
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
