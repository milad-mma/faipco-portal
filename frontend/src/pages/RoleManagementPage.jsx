import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Checkbox,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  FormGroup,
  IconButton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import ExpandMoreOutlinedIcon from "@mui/icons-material/ExpandMoreOutlined";
import ChevronLeftOutlinedIcon from "@mui/icons-material/ChevronLeftOutlined";
import {
  createRole,
  deleteRole,
  fetchPermissions,
  fetchRoleDetail,
  fetchRoles,
  updateRole,
} from "../api/users";

const EMPTY_FORM = { name: "", description: "", permissionIds: [] };

// طبق قرارداد نام‌گذاری استفاده‌شده در کدِ Backend، مجوزهایی که با
// «.manage» تمام می‌شوند یا با «system.» شروع می‌شوند، همیشه سطح
// دسترسی گسترده/ادمینی دارند (مثل sites.manage، vehicles.manage،
// system.backup) — این فقط برای نمایش یک برچسب هشدار است، تصمیم واقعی
// (آیا این مجوز به این نقش داده شود یا نه) کاملاً دست خودِ Admin است.
function isAdminLevelPermission(code) {
  return code.endsWith(".manage") || code.startsWith("system.");
}

/**
 * پنل مدیریت نقش/مجوز — ساخت نقش‌های جدید از ترکیب مجوزهای *موجود*
 * (بدون نیاز به هیچ تغییر کد یا Migration، برای ترکیب‌های تازه از همان
 * مجوزهایی که از قبل در سیستم وجود دارند).
 *
 * ⚠️ هر مجوز جدید (که هنوز در سیستم وجود ندارد) همچنان فقط با یک تغییر
 * کد ممکن است — چون یک مجوز فقط وقتی معنا دارد که جایی از Backend واقعاً
 * همان Code را چک کند. این صفحه فقط اجازه می‌دهد از مجوزهای موجود، نقش‌های
 * تازه بسازید یا نقش‌های موجود را ویرایش کنید — نه ساخت مجوز کاملاً جدید.
 */
export default function RoleManagementPage() {
  const [roles, setRoles] = useState(null);
  const [permissions, setPermissions] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRoleId, setEditingRoleId] = useState(null); // null = ساخت نقش جدید
  const [form, setForm] = useState(EMPTY_FORM);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [roleToDelete, setRoleToDelete] = useState(null);
  const [expandedGroups, setExpandedGroups] = useState({});
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  function loadRoles() {
    fetchRoles().then(setRoles);
  }

  useEffect(() => {
    loadRoles();
    fetchPermissions().then(setPermissions);
  }, []);

  // گروه‌بندی مجوزها بر اساس پیشوند قبل از نقطه (مثلاً "notices.view" →
  // گروه "notices") — فقط برای خواناتر شدن چک‌باکس‌لیست طولانی، هیچ اثر
  // دیگری روی داده ندارد.
  const groupedPermissions = useMemo(() => {
    if (!permissions) return [];
    const groups = {};
    for (const p of permissions) {
      const prefix = p.code.split(".")[0];
      if (!groups[prefix]) groups[prefix] = [];
      groups[prefix].push(p);
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [permissions]);

  async function openCreateDialog() {
    setEditingRoleId(null);
    setForm(EMPTY_FORM);
    setError("");
    setDialogOpen(true);
  }

  async function openEditDialog(role) {
    setEditingRoleId(role.id);
    setError("");
    setDialogOpen(true);
    // فرم را با یک وضعیت موقت خالی/در‌حال‌بارگذاری باز می‌کنیم، بعد جزئیات
    // واقعی (شامل فهرست دقیق مجوزهای همین نقش) را می‌گیریم — چون لیست
    // خلاصه نقش‌ها (fetchRoles) خودِ مجوزها را ندارد.
    setForm({ name: role.name, description: role.description || "", permissionIds: [] });
    const detail = await fetchRoleDetail(role.id);
    setForm({
      name: detail.name,
      description: detail.description || "",
      permissionIds: detail.permissions.map((p) => p.id),
    });
  }

  function togglePermission(permissionId) {
    setForm((prev) => ({
      ...prev,
      permissionIds: prev.permissionIds.includes(permissionId)
        ? prev.permissionIds.filter((id) => id !== permissionId)
        : [...prev.permissionIds, permissionId],
    }));
  }

  // انتخاب/لغوِ‌انتخاب یک‌جای کل یک گروه (شاخه درخت) — اگر همه فرزندان
  // انتخاب‌شده باشند، همه را لغو می‌کند؛ وگرنه همه را انتخاب می‌کند.
  function toggleGroup(items) {
    const ids = items.map((p) => p.id);
    const allSelected = ids.every((id) => form.permissionIds.includes(id));
    setForm((prev) => ({
      ...prev,
      permissionIds: allSelected
        ? prev.permissionIds.filter((id) => !ids.includes(id))
        : [...new Set([...prev.permissionIds, ...ids])],
    }));
  }

  function toggleGroupExpanded(group) {
    setExpandedGroups((prev) => ({ ...prev, [group]: !prev[group] }));
  }

  const canSave = form.name.trim().length > 0 && !isSaving;

  async function handleSave() {
    if (!canSave) return;
    setError("");
    setIsSaving(true);
    const payload = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      permission_ids: form.permissionIds,
    };
    try {
      if (editingRoleId) {
        await updateRole(editingRoleId, payload);
      } else {
        await createRole(payload);
      }
      setDialogOpen(false);
      loadRoles();
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره نقش ناموفق بود.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleConfirmDelete() {
    if (!roleToDelete) return;
    setDeleteError("");
    setIsDeleting(true);
    try {
      await deleteRole(roleToDelete.id);
      setRoles((prev) => prev.filter((r) => r.id !== roleToDelete.id));
      setRoleToDelete(null);
    } catch (err) {
      setDeleteError(err.response?.data?.detail || "حذف نقش ناموفق بود.");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Typography variant="h5" fontWeight={700}>
          مدیریت نقش/مجوز
        </Typography>
        <Button variant="contained" startIcon={<AddOutlinedIcon />} onClick={openCreateDialog}>
          نقش جدید
        </Button>
      </Stack>

      {roles === null ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : (
        <Stack spacing={1.5}>
          {roles.map((role) => (
            <Card key={role.id} variant="outlined" sx={{ borderRadius: 2, p: 2 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Box sx={{ minWidth: 0 }}>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Typography variant="body1" fontWeight={700}>
                      {role.name}
                    </Typography>
                    {/* ⚠️ طبق درخواست صریح، is_system دیگر مانع ویرایش نیست —
                        فقط مانع حذف. فقط خودِ «superadmin» کاملاً غیرقابل‌تغییر
                        است (چون جای دیگری از کد دقیقاً همین نام را چک می‌کند). */}
                    {role.name === "superadmin" ? (
                      <Chip
                        size="small"
                        icon={<LockOutlinedIcon fontSize="small" />}
                        label="سیستمی — کاملاً غیرقابل‌تغییر"
                        variant="outlined"
                      />
                    ) : (
                      role.is_system && (
                        <Chip size="small" label="سیستمی — غیرقابل‌حذف" variant="outlined" />
                      )
                    )}
                  </Stack>
                  {role.description && (
                    <Typography variant="body2" color="text.secondary">
                      {role.description}
                    </Typography>
                  )}
                </Box>
                <Stack direction="row" sx={{ flexShrink: 0 }}>
                  {role.name !== "superadmin" && (
                    <IconButton size="small" onClick={() => openEditDialog(role)} aria-label="ویرایش">
                      <EditOutlinedIcon fontSize="small" />
                    </IconButton>
                  )}
                  {!role.is_system && (
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => {
                        setDeleteError("");
                        setRoleToDelete(role);
                      }}
                      aria-label="حذف"
                    >
                      <DeleteOutlineOutlinedIcon fontSize="small" />
                    </IconButton>
                  )}
                </Stack>
              </Stack>
            </Card>
          ))}
        </Stack>
      )}

      {/* Dialog ساخت/ویرایش نقش */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingRoleId ? "ویرایش نقش" : "نقش جدید"}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="نام نقش"
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
              fullWidth
              autoFocus
            />
            <TextField
              label="توضیح (اختیاری)"
              value={form.description}
              onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
              fullWidth
              multiline
              minRows={2}
            />
            <Box>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
                مجوزهای این نقش
              </Typography>
              {permissions === null ? (
                <CircularProgress size={20} />
              ) : (
                <Stack spacing={0.5} sx={{ maxHeight: 380, overflowY: "auto", pr: 1 }}>
                  {groupedPermissions.map(([group, items]) => {
                    const selectedCount = items.filter((p) => form.permissionIds.includes(p.id)).length;
                    const allSelected = selectedCount === items.length;
                    const isExpanded = expandedGroups[group] !== false;
                    return (
                      <Box key={group} sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1.5 }}>
                        {/* گره والد — یک شاخه از درخت مجوزها (مثلاً «vehicles») */}
                        <Stack
                          direction="row"
                          alignItems="center"
                          spacing={0.5}
                          sx={{ px: 1, py: 0.5, cursor: "pointer" }}
                          onClick={() => toggleGroupExpanded(group)}
                        >
                          <IconButton size="small" sx={{ p: 0.25 }}>
                            {isExpanded ? <ExpandMoreOutlinedIcon fontSize="small" /> : <ChevronLeftOutlinedIcon fontSize="small" />}
                          </IconButton>
                          <Checkbox
                            size="small"
                            checked={allSelected}
                            indeterminate={selectedCount > 0 && !allSelected}
                            onClick={(e) => e.stopPropagation()}
                            onChange={() => toggleGroup(items)}
                          />
                          <Typography variant="body2" fontWeight={700} sx={{ flex: 1 }}>
                            {group}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {selectedCount}/{items.length}
                          </Typography>
                        </Stack>
                        {/* گره‌های فرزند — تک‌تک مجوزهای همین شاخه */}
                        <Collapse in={isExpanded}>
                          <FormGroup sx={{ pb: 0.5 }}>
                            {items.map((p) => (
                              <FormControlLabel
                                key={p.id}
                                sx={{ mr: 0, pr: 4.5 }}
                                control={
                                  <Checkbox
                                    size="small"
                                    checked={form.permissionIds.includes(p.id)}
                                    onChange={() => togglePermission(p.id)}
                                  />
                                }
                                label={
                                  <Box>
                                    <Stack direction="row" spacing={0.75} alignItems="center">
                                      <Typography variant="body2">{p.code}</Typography>
                                      {isAdminLevelPermission(p.code) && (
                                        <Chip
                                          size="small"
                                          color="warning"
                                          variant="outlined"
                                          label="دسترسی ادمین"
                                          sx={{ height: 18, fontSize: 10 }}
                                        />
                                      )}
                                    </Stack>
                                    {p.description && (
                                      <Typography variant="caption" color="text.secondary">
                                        {p.description}
                                      </Typography>
                                    )}
                                  </Box>
                                }
                              />
                            ))}
                          </FormGroup>
                        </Collapse>
                      </Box>
                    );
                  })}
                </Stack>
              )}
            </Box>
            {error && <Alert severity="error">{error}</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setDialogOpen(false)}>انصراف</Button>
          <Button variant="contained" disabled={!canSave} onClick={handleSave}>
            {isSaving ? "در حال ذخیره..." : "ذخیره"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog تأیید حذف */}
      <Dialog open={Boolean(roleToDelete)} onClose={() => setRoleToDelete(null)} maxWidth="xs" fullWidth>
        <DialogTitle>حذف نقش</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: deleteError ? 2 : 0 }}>
            آیا از حذف نقش «{roleToDelete?.name}» مطمئن هستید؟ این عمل قابل‌بازگشت نیست.
          </Typography>
          {deleteError && <Alert severity="error">{deleteError}</Alert>}
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setRoleToDelete(null)}>انصراف</Button>
          <Button variant="contained" color="error" disabled={isDeleting} onClick={handleConfirmDelete}>
            حذف
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
