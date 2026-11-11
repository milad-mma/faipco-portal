// انتخاب فردمحور گیرنده/ارجاع: جست‌وجوی نام، فیلتر واحد و عنوان سمت (فقط برای پیدا کردن افراد؛ گیرنده همیشه شخص است).
// فقط نام، سمت و واحد نمایش داده می‌شود (کد پرسنلی/ملی هرگز). onConfirm([{employee_id, name, title, department, selected_via}])
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { fetchPeople } from "../../api/automationLetters";
import { toPersianDigits } from "../../utils/searchText";

export default function PersonPicker({ open, title = "انتخاب افراد", exclude = [], onClose, onConfirm, fetcher = fetchPeople, emptyText }) {
  const [q, setQ] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [positionTitle, setPositionTitle] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 50;
  const requestIdRef = useRef(0);
  const [selected, setSelected] = useState({}); // employee_id → person

  useEffect(() => {
    const req = ++requestIdRef.current;
    if (!open) return undefined;
    setLoading(true);
    setData(null);
    const t = setTimeout(() => {
      fetcher({ q, department_id: departmentId || undefined, title: positionTitle || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
        .then((result) => { if (req === requestIdRef.current) setData(result); })
        .catch((err) => { if (req === requestIdRef.current) setData({ people: [], departments: [], error: err.response?.data?.detail || "دریافت فهرست پرسنل ناموفق بود." }); })
        .finally(() => { if (req === requestIdRef.current) setLoading(false); });
    }, 300);
    return () => { ++requestIdRef.current; clearTimeout(t); };
  }, [open, q, departmentId, positionTitle, page, fetcher]);

  useEffect(() => { setPage(0); }, [q, departmentId, positionTitle, open]);

  useEffect(() => {
    if (open) setSelected({});
  }, [open]);

  const excluded = useMemo(() => new Set(exclude), [exclude]);
  const people = (data?.people || []).filter((p) => !excluded.has(p.employee_id));
  const via = departmentId ? "department" : positionTitle ? "title" : "direct";
  const count = Object.keys(selected).length;

  function toggle(p) {
    setSelected((s) => {
      const next = { ...s };
      if (next[p.employee_id]) delete next[p.employee_id];
      else next[p.employee_id] = { ...p, selected_via: via };
      return next;
    });
  }

  function selectAllShown() {
    setSelected((s) => {
      const next = { ...s };
      for (const p of people) if (!next[p.employee_id]) next[p.employee_id] = { ...p, selected_via: via };
      return next;
    });
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          <TextField size="small" label="جست‌وجوی نام" value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
            <TextField select size="small" label="واحد" value={departmentId} onChange={(e) => setDepartmentId(e.target.value)} sx={{ flex: 1 }}>
              <MenuItem value="">همه‌ی واحدها</MenuItem>
              {(data?.departments || []).map((d) => (
                <MenuItem key={d.id} value={d.id}>
                  {d.name} {d.site ? `— ${d.site}` : ""}
                </MenuItem>
              ))}
            </TextField>
            <TextField size="small" label="عنوان سمت" value={positionTitle} onChange={(e) => setPositionTitle(e.target.value)} sx={{ flex: 1 }} />
          </Stack>
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Typography variant="caption" color="text.secondary">
              {loading ? "در حال جست‌وجو..." : `${toPersianDigits(data?.total ?? people.length)} نفر${(data?.total || 0) > PAGE_SIZE ? ` — صفحه ${toPersianDigits(page + 1)}` : ""}`}
            </Typography>
            {(departmentId || positionTitle) && people.length > 0 && (
              <Button size="small" onClick={selectAllShown}>
                انتخاب افراد این صفحه
              </Button>
            )}
          </Stack>
          <Box sx={{ maxHeight: 360, overflowY: "auto", border: 1, borderColor: "divider", borderRadius: 1 }}>
            {loading && !data ? (
              <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
                <CircularProgress size={22} />
              </Box>
            ) : people.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
                {data?.error || emptyText || "کسی پیدا نشد. فقط پرسنل فعالی که به اتوماسیون اداری دسترسی دارند نمایش داده می‌شوند."}
              </Typography>
            ) : (
              <List dense disablePadding>
                {people.map((p) => (
                  <ListItemButton key={p.employee_id} onClick={() => toggle(p)}>
                    <ListItemIcon sx={{ minWidth: 36 }}>
                      <Checkbox edge="start" size="small" checked={Boolean(selected[p.employee_id])} tabIndex={-1} disableRipple />
                    </ListItemIcon>
                    <ListItemText primary={p.name} secondary={[p.title, p.department].filter(Boolean).join(" — ")} />
                  </ListItemButton>
                ))}
              </List>
            )}
          </Box>
          {(page > 0 || data?.has_more) && (
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ minHeight: 40 }}>
              <Button size="small" disabled={loading || page === 0} onClick={() => setPage((v) => Math.max(0, v - 1))}>صفحه قبل</Button>
              <Typography variant="body2" color="text.secondary">صفحه {toPersianDigits(page + 1)}</Typography>
              <Button size="small" disabled={loading || !data?.has_more} onClick={() => setPage((v) => v + 1)}>صفحه بعد</Button>
            </Stack>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" disabled={!count} onClick={() => onConfirm(Object.values(selected))}>
          افزودن {count ? `(${toPersianDigits(count)})` : ""}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
