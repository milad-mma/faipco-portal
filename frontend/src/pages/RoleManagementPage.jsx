// صفحه‌ی مدیریت نقش‌ها و مجوزها.
// فهرست نقش‌ها را نشان می‌دهد و امکان ساخت، ویرایش و حذف نقش با انتخاب از مجوزهای موجود
// (درخت مجوزها گروه‌بندی‌شده بر اساس پیشوند) را فراهم می‌کند.
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
  Tooltip,
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
import { useAuth } from "../context/AuthContext";

const EMPTY_FORM = { name: "", description: "", permissionIds: [] };  // مقدار اولیه‌ی فرم نقش

// ورودی: کد مجوز؛ خروجی: true اگر مجوز سطح ادمین باشد (پایان با «.manage» یا شروع با «system.»،
// مثل sites.manage یا system.backup). فقط برای نمایش برچسب هشدار کنار مجوز استفاده می‌شود.
function isAdminLevelPermission(code) {
  return code.endsWith(".manage") || code.startsWith("system.");
}

// مجوزهایی که اثرشان به یک سایت محدود نمی‌شود و روی کل سیستم است، حتی اگر نقش فقط برای یک سایت
// داده شود؛ باید فقط به افراد مورد اعتماد داده شوند. مقدار = توضیح نمایش‌داده‌شده در Tooltip.
const SYSTEM_WIDE_PERMISSIONS = {
  "roles.manage": "تعریف نقش‌ها بین همه‌ی سایت‌ها مشترک است؛ تغییر آن روی دسترسی همه اثر دارد.",
  "system.settings": "تنظیمات کلی سامانه (برندینگ، ظاهر و ...) برای همه‌ی سایت‌ها یکی است.",
  "sync.manage": "فاصله‌ی همگام‌سازی خودکار برای همه‌ی سایت‌ها مشترک است.",
  "hr.birthday_messages": "متن‌ها و ساعت پیام تبریک تولد برای همه‌ی سایت‌ها یکی است.",
  "feedback.view_all": "انتقادات و پیشنهادات پرسنل همه‌ی سایت‌ها را نشان می‌دهد.",
};

/**
 * کامپوننت پنل مدیریت نقش/مجوز؛ ورودی ندارد.
 * نقش‌های جدید را از ترکیب مجوزهای موجود در سیستم می‌سازد یا نقش‌های موجود را ویرایش/حذف می‌کند.
 * ساخت مجوز جدید در این صفحه ممکن نیست، چون هر مجوز باید در Backend با همان Code بررسی شود.
 */
export default function RoleManagementPage() {
  const { refetchUser } = useAuth();
  const [roles, setRoles] = useState(null);  // null = در حال بارگذاری
  const [permissions, setPermissions] = useState(null);  // همه‌ی مجوزهای موجود؛ null = در حال بارگذاری
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRoleId, setEditingRoleId] = useState(null); // null = ساخت نقش جدید
  const [form, setForm] = useState(EMPTY_FORM);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [roleToDelete, setRoleToDelete] = useState(null);  // نقشی که دیالوگ تأیید حذفش باز است
  const [expandedGroups, setExpandedGroups] = useState({});  // وضعیت باز/بسته‌ی هر گروه مجوز؛ پیش‌فرض باز
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  // فهرست نقش‌ها را از سرور می‌گیرد
  function loadRoles() {
    fetchRoles().then(setRoles);
  }

  // بارگذاری اولیه‌ی نقش‌ها و مجوزها
  useEffect(() => {
    loadRoles();
    fetchPermissions().then(setPermissions);
  }, []);

  // گروه‌بندی مجوزها بر اساس پیشوند قبل از نقطه (مثلاً "notices.view" → گروه "notices")؛
  // خروجی: آرایه‌ی [نام گروه، مجوزها] مرتب‌شده بر اساس نام گروه
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

  // دیالوگ را برای ساخت نقش جدید با فرم خالی باز می‌کند
  async function openCreateDialog() {
    setEditingRoleId(null);
    setForm(EMPTY_FORM);
    setError("");
    setDialogOpen(true);
  }

  // دیالوگ ویرایش نقش را باز می‌کند و جزئیات نقش (شامل مجوزها) را از سرور در فرم می‌گذارد
  async function openEditDialog(role) {
    setEditingRoleId(role.id);
    setError("");
    setDialogOpen(true);
    // ابتدا فرم با نام/توضیح و بدون مجوز پر می‌شود، سپس جزئیات کامل گرفته می‌شود
    // چون فهرست خلاصه‌ی نقش‌ها (fetchRoles) مجوزها را ندارد
    setForm({ name: role.name, description: role.description || "", permissionIds: [] });
    const detail = await fetchRoleDetail(role.id);
    setForm({
      name: detail.name,
      description: detail.description || "",
      permissionIds: detail.permissions.map((p) => p.id),
    });
  }

  // یک مجوز را در فرم انتخاب یا لغو انتخاب می‌کند
  function togglePermission(permissionId) {
    setForm((prev) => ({
      ...prev,
      permissionIds: prev.permissionIds.includes(permissionId)
        ? prev.permissionIds.filter((id) => id !== permissionId)
        : [...prev.permissionIds, permissionId],
    }));
  }

  // انتخاب/لغو انتخاب یک‌جای کل یک گروه؛ اگر همه‌ی مجوزهای گروه انتخاب‌شده باشند همه را لغو، وگرنه همه را انتخاب می‌کند
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

  // باز/بسته‌کردن یک گروه در درخت مجوزها
  function toggleGroupExpanded(group) {
    setExpandedGroups((prev) => ({ ...prev, [group]: !prev[group] }));
  }

  const canSave = form.name.trim().length > 0 && !isSaving;

  // نقش را (ساخت یا ویرایش) ذخیره می‌کند، فهرست را بازخوانی و اطلاعات کاربر جاری را تازه می‌کند
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
      // فلگ‌های can_* کاربر جاری دوباره خوانده می‌شوند تا اگر نقش خودش تغییر کرده، منوها بی‌درنگ به‌روز شوند
      refetchUser().catch(() => {});
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره نقش با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  // نقش انتخاب‌شده را حذف و از فهرست برمی‌دارد؛ خطای سرور در دیالوگ نمایش داده می‌شود
  async function handleConfirmDelete() {
    if (!roleToDelete) return;
    setDeleteError("");
    setIsDeleting(true);
    try {
      await deleteRole(roleToDelete.id);
      setRoles((prev) => prev.filter((r) => r.id !== roleToDelete.id));
      setRoleToDelete(null);
    } catch (err) {
      setDeleteError(err.response?.data?.detail || "حذف نقش با خطا مواجه شد.");
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

      {/* فهرست کارت‌های نقش (یا نشانگر بارگذاری) */}
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
                    {/* برچسب نقش: superadmin کاملاً غیرقابل‌تغییر است (نامش در کد بررسی می‌شود)؛
                        is_system فقط نشان می‌دهد نقش پیش‌فرضِ نصب است و مانع ویرایش/حذف نیست */}
                    {role.name === "superadmin" ? (
                      <Chip
                        size="small"
                        icon={<LockOutlinedIcon fontSize="small" />}
                        label="سیستمی — کاملاً غیرقابل‌تغییر"
                        variant="outlined"
                      />
                    ) : (
                      role.is_system && <Chip size="small" label="پیش‌فرض" variant="outlined" />
                    )}
                  </Stack>
                  {role.description && (
                    <Typography variant="body2" color="text.secondary">
                      {role.description}
                    </Typography>
                  )}
                </Box>
                {/* دکمه‌های ویرایش و حذف (برای superadmin نمایش داده نمی‌شوند) */}
                <Stack direction="row" sx={{ flexShrink: 0 }}>
                  {role.name !== "superadmin" && (
                    <IconButton size="small" onClick={() => openEditDialog(role)} aria-label="ویرایش">
                      <EditOutlinedIcon fontSize="small" />
                    </IconButton>
                  )}
                  {role.name !== "superadmin" && (
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
              {/* درخت مجوزها: هر گروه یک گره والد با چک‌باکس کل گروه و فرزندان قابل باز/بسته‌شدن */}
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
                مجوزهای این نقش
              </Typography>
              {/* راهنمای برچسب مجوزهای حساس */}
              <Alert severity="warning" sx={{ mb: 1 }}>
                مجوزهای «کل سیستم» حتی اگر نقش فقط برای یک سایت داده شود روی همه‌ی سایت‌ها اثر دارند؛ آن‌ها را فقط به
                افراد مورد اعتماد بدهید.
              </Alert>
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
                                      {SYSTEM_WIDE_PERMISSIONS[p.code] && (
                                        <Tooltip title={SYSTEM_WIDE_PERMISSIONS[p.code]} arrow>
                                          <Chip
                                            size="small"
                                            color="error"
                                            label="کل سیستم — فقط افراد مورد اعتماد"
                                            sx={{ height: 18, fontSize: 10 }}
                                          />
                                        </Tooltip>
                                      )}
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
