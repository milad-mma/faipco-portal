# کدهای حذف‌شده — بایگانی مرجع

این سند فهرست کامل کدهایی است که در یک پاکسازی (بعد از یک بررسی کامل
کد غیراستفاده در کل پروژه) حذف شدند — همراه با توضیح دقیق «چه کاری
می‌کردند» و «کجا بودند»، برای این‌که اگر روزی به هرکدام نیاز افتاد،
بدون گشتن در تاریخچه Git، مستقیم از همین‌جا بازسازی شوند.

⚠️ همه این موارد قبل از حذف با یک بررسی کامل (نه فقط جست‌وجوی متنی —
تحلیل واقعی کد، شامل استفاده از Callback/Dependency Injection که ممکن
بود به‌اشتباه «استفاده‌نشده» به‌نظر برسد) تأیید شدند که واقعاً هیچ‌جای
دیگری صدا زده نمی‌شدند.

---

## ۱. `get_managed_site_ids()` — Backend

**فایل**: `backend/app/repositories/user_repository.py`
**چه کاری می‌کرد**: شناسه سایت‌هایی که یک کاربر برای آن‌ها نقشی با یک
نام مشخص (`role_name`) و `site_id` غیر‌خالی دارد را برمی‌گرداند —
یعنی مستقیماً بر اساس **نام نقش** (نه Permission Code) فیلتر می‌کرد.

**چرا حذف شد**: این تابع فقط برای «گزارش اطلاعیه‌های سایت من» استفاده
می‌شد، با نام نقش Hard-code شده `"site_manager"`. در یک اصلاح قبلی
(«گزارش اطلاعیه‌های سایت» برای نقش «مدیر سایت» هارد‌کد شده — تبدیل به
مجوز `notices.site_report` قابل‌تخصیص)، این منطق با `get_sites_with_permission`
(که بر اساس Permission Code، نه نام نقش، کار می‌کند) جایگزین شد. بعد از
آن، این تابع دیگر هیچ‌جای دیگری صدا زده نمی‌شد.

```python
async def get_managed_site_ids(self, user_id: int, role_name: str) -> list[int]:
    """
    شناسه‌های Site هایی که این کاربر برایشان نقش role_name را با site_id
    مشخص دارد (مثلاً «مدیر کدام سایت‌هاست؟») — برای گزارش‌هایی که به یک
    Site خاص محدود می‌شوند (مثل «گزارش اطلاعیه‌های سایت من»)، نه یک
    Permission ساده. اگر کاربر این نقش را سراسری (بدون site_id) داشته
    باشد، نادیده گرفته می‌شود — این متد فقط انتصاب‌های Site-scoped را
    برمی‌گرداند.
    """
    stmt = (
        select(UserRole.site_id)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == user_id, Role.name == role_name, UserRole.site_id.is_not(None))
    )
    result = await self.db.execute(stmt)
    return [row[0] for row in result.all()]
```

**اگر نیاز شد**: برای «شناسه سایت‌هایی که کاربر برای یک نقش خاص (با نام)
دارد»، این کد را دوباره اضافه کنید — ولی توصیه می‌شود به‌جایش از
`get_sites_with_permission(db, user, permission_code)` در
`app/core/site_access.py` استفاده شود (که بر اساس Permission Code کار
می‌کند و با سیستم مدیریت نقش/مجوز هماهنگ‌تر است).

---

## ۲. `GET /users` + `list_users()` — Backend

**فایل‌ها**: `backend/app/api/v1/endpoints/users.py` (Endpoint) و
`backend/app/services/user_management_service.py` (`list_users`)

**چه کاری می‌کرد**: فهرست همه کاربران (جدول `users`، نه `employees`) را
برمی‌گرداند.

```python
@router.get("", response_model=list[UserManagementOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    return await UserManagementService(db).list_users()
```

```python
# در UserManagementService:
async def list_users(self) -> list[User]:
    result = await self.db.execute(select(User))
    return list(result.scalars().all())
```

با حذف این Endpoint، Schema مربوطه (`UserManagementOut` در
`app/schemas/user_management.py`) هم دیگر هیچ‌جا استفاده نمی‌شد و حذف شد:

```python
class UserManagementOut(BaseModel):
    id: int
    username: str
    email: str | None
    is_active: bool
    is_superuser: bool
    employee_id: int | None

    model_config = ConfigDict(from_attributes=True)
```

**چرا حذف شد**: بعد از بازطراحی صفحه «مدیریت دسترسی» (که حالا بر پایه
`GET /employees` + `GET /users/access-overview` کار می‌کند)، این
Endpoint دیگر از هیچ‌جای Frontend صدا زده نمی‌شد.

**اگر نیاز شد**: منطق `UserManagementService.list_users()` (اگر لازم
شد) به‌سادگی با یک Query مستقیم `select(User)` قابل بازسازی است.

---

## ۳. مسیر موازی و رهاشده انتصاب نقش — Frontend

**فایل**: `frontend/src/api/users.js`

سه تابع که یک مسیر **کاملاً موازی و جایگزین‌شده** با
`frontend/src/api/employees.js` بودند:

```javascript
export async function fetchUsers() {
  const { data } = await apiClient.get("/users");
  return data;
}

export async function fetchUserRoles(userId) {
  const { data } = await apiClient.get(`/users/${userId}/roles`);
  return data;
}

export async function assignRole(userId, roleId, siteId) {
  const { data } = await apiClient.post(`/users/${userId}/roles`, {
    role_id: roleId,
    site_id: siteId,
  });
  return data;
}
```

**چرا حذف شد**: صفحه «مدیریت دسترسی» (`AssignAccessDialog.jsx`) از یک
مسیر دیگر (بر پایه Employee، نه User مستقیم) استفاده می‌کند:
`fetchEmployeeRoles`/`assignRoleToEmployee` در `api/employees.js` —
که هم‌زمان یک User را خودکار می‌سازد اگر پرسنل هنوز حساب کاربری نداشته
باشد (`get_or_create_employee_user`). این سه تابع بالا، از یک نسخه
قدیمی‌تر UI باقی مانده بودند.

⚠️ **نکته**: خودِ Endpoint های Backend مرتبط (`GET /users/{id}/roles`،
`POST /users/{id}/roles`) دست‌نخورده باقی ماندند — چون
`POST /users/{id}/roles` هنوز توسط Backend به‌عنوان یک مسیر جایگزین/عمومی
معتبر است (`UserManagementService.assign_role`، همان که به‌تازگی برای
پشتیبانی از چند سایت هم‌زمان به‌روزرسانی شد) و ممکن است در آینده مستقیم
لازم شود.

**اگر نیاز شد**: توابع بالا را دقیقاً همان‌طور که نوشته شده دوباره
اضافه کنید — ولی توجه کنید `assignRole` باید با تغییر اخیر Backend
هماهنگ شود (`site_id` تکی حذف شده، حالا `site_ids` یک فهرست است).

---

## ۴. `createDepartment()` — Frontend

**فایل**: `frontend/src/api/departments.js`

```javascript
export async function createDepartment(payload) {
  const { data } = await apiClient.post("/departments", payload);
  return data;
}
```

**چرا حذف شد**: هیچ دکمه/فرم «واحد سازمانی جدید» در
`DepartmentsPage.jsx` یا هیچ صفحه دیگری وجود نداشت که این تابع را صدا
بزند — واحدهای سازمانی همیشه از طریق Sync Engine ساخته می‌شوند، نه
دستی.

**اگر نیاز شد**: خودِ Endpoint Backend (`POST /departments`) هنوز وجود
دارد و دست‌نخورده است؛ فقط کافی است این تابع Wrapper را به
`api/departments.js` برگردانید و یک فرم UI برایش بسازید.

---

## ۵. `fetchAllNotices()` — Frontend

**فایل**: `frontend/src/api/notices.js`

```javascript
export async function fetchAllNotices() {
  const { data } = await apiClient.get("/notices");
  return data;
}
```

**چرا حذف شد**: با `fetchMyNotices({...})` (که صفحه‌بندی، فیلتر نوع،
و فیلتر آرشیو را هم پشتیبانی می‌کند) جایگزین شده بود؛ دیگر هیچ‌جا صدا
زده نمی‌شد.

---

## ۶. قابلیت «حضور GPS دوره‌ای» (`logGpsPresence`) — کامل، Backend + Frontend

یک قابلیت **کاملاً رهاشده** — نه فقط یک تابع تکی، بلکه یک مسیر کامل از
Frontend تا Backend که هیچ‌وقت به UI واقعی وصل نشد.

### Frontend

**فایل**: `frontend/src/api/attendance.js`

```javascript
export async function logGpsPresence({ latitude, longitude, accuracyMeters, siteId }) {
  const { data } = await apiClient.post("/attendance/presence", {
    latitude,
    longitude,
    accuracy_meters: accuracyMeters,
    site_id: siteId || null,
  });
  return data; // { is_within_geofence, matched_site_name, distance_meters }
}
```

### Backend — Endpoint

**فایل**: `backend/app/api/v1/endpoints/attendance.py`

```python
@router.post("/presence", response_model=GpsCheckResultOut)
async def log_presence(
    payload: GpsPositionIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee_id = _require_employee(current_user)
    log = await GpsAttendanceService(db).log_presence(
        employee_id=employee_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_meters=payload.accuracy_meters,
        site_id=payload.site_id,
    )
    matched_site_name = None
    if log.matched_site_id is not None:
        from app.models.site import Site

        site = await db.get(Site, log.matched_site_id)
        matched_site_name = site.name if site else None

    return GpsCheckResultOut(
        is_within_geofence=log.is_within_geofence,
        matched_site_name=matched_site_name,
        distance_meters=log.distance_meters,
    )
```

### Backend — سرویس

**فایل**: `backend/app/services/gps_attendance_service.py`

```python
async def log_presence(
    self, *, employee_id: int, latitude: float, longitude: float, accuracy_meters: float | None, site_id: int | None
) -> GpsActivityLog:
    """حضور دوره‌ای — همیشه لاگ می‌شود، چه داخل محدوده باشد چه نه (برای گزارش‌گیری بعدی مفید است)."""
    return await self._record(
        employee_id=employee_id,
        log_type=GpsLogType.presence,
        latitude=latitude,
        longitude=longitude,
        accuracy_meters=accuracy_meters,
        site_id=site_id,
    )
```

### Backend — Schema

**فایل**: `backend/app/schemas/gps_attendance.py`

```python
class GpsCheckResultOut(BaseModel):
    is_within_geofence: bool
    matched_site_name: str | None
    distance_meters: float | None
```

**چرا حذف شد**: هدف این قابلیت ثبت دوره‌ای موقعیت مکانی پرسنل (صرف‌نظر
از ثبت ورود/خروج) بود — احتمالاً برای گزارش‌گیری/نظارت آینده. اما
`AttendanceClockPage.jsx` (صفحه واقعی ثبت ورود/خروج) از یک مسیر کاملاً
متفاوت استفاده می‌کند: موقعیت مکانی مستقیماً همراه با خودِ درخواست
ثبت ورود/خروج (`clock_in_out`) فرستاده می‌شود، نه به‌صورت جدا و دوره‌ای.
هیچ صفحه‌ای هرگز `logGpsPresence` را صدا نزد.

⚠️ **نکته مهم**: `GpsLogType.presence` (مقدار Enum) و مدل
`GpsActivityLog`/متد `_record()` **حذف نشدند** — چون این‌ها زیرساخت
مشترکی هستند که `clock_in_out()` (قابلیت فعال ثبت ورود/خروج) هم از
همان استفاده می‌کند؛ فقط حذف مقدار `presence` از Enum سطح دیتابیس
عمداً انجام نشد (ریسک داشت اگر قبلاً هرگز رکوردی با این مقدار ثبت شده
باشد).

**اگر نیاز شد**: هر سه بخش بالا (Frontend + Endpoint + متد سرویس) را
دقیقاً همان‌طور که نوشته شده برگردانید — Schema (`GpsCheckResultOut`)
و import مربوطه (`GpsCheckResultOut` در بالای `attendance.py`) را هم
اضافه کنید.

---

## ۷. طراحی قدیمی («Legacy») پرتال — کامل حذف شد

⚠️ این بخش برخلاف موارد بالا، **کد غیراستفاده نبود** — یک راه برگشت
عمدی (Rollback) بود که از ابتدای بازطراحی پرتال (بر اساس فایل‌های HTML
ارسالی کارفرما) برای احتیاط نگه داشته شده بود. طبق درخواست صریح، حالا
کامل حذف شد.

### ۷.۱ تم قدیمی (`legacyLightTheme` / `legacyDarkTheme`)

**فایل**: `frontend/src/theme.js`

این‌ها دو شیء کامل `createTheme(...)` بودند (تقریباً ۹۰ خط هرکدام) —
نسخه خیلی قدیمی‌تر تم پرتال، قبل از بازطراحی بر اساس
`personnel_portal.html`. رنگ‌بندی متفاوت (بنفش/فیروزه‌ای تیره‌تر،
گردی گوشه‌های ۲۲px به‌جای ۶px فعلی)، Typography متفاوت (بدون فونت
وزیرمتن اختصاصی)، و MuiCssBaseline با پس‌زمینه گرادیانت رنگی مه‌آلود
(نه پس‌زمینه ساده فعلی).

فلگ کنترل‌کننده:
```javascript
export const NEW_DESIGN_ENABLED = true; // اگر false می‌شد، legacyLightTheme/legacyDarkTheme جایگزین می‌شدند
```

و در پایین فایل:
```javascript
export const lightTheme = NEW_DESIGN_ENABLED ? modernLightTheme : legacyLightTheme;
export const darkTheme = NEW_DESIGN_ENABLED ? modernDarkTheme : legacyDarkTheme;
```

متن کامل هر دو تِم (برای بازسازی کامل بدون نیاز به Git):

```javascript
export const legacyLightTheme = createTheme({
  direction: "rtl",
  palette: {
    mode: "light",
    primary: {
      main: "#16324F",
      light: "#1F4B75",
      dark: "#0E2138",
      contrastText: "#FFFFFF",
    },
    secondary: {
      main: "#E0A458",
      light: "#EBBD82",
      dark: "#C68B3F",
      contrastText: "#16324F",
    },
    background: {
      default: "#F5F7FA",
      paper: "#FFFFFF",
    },
    text: {
      primary: "#1A1F29",
      secondary: "#5B6675",
    },
    success: { main: "#2E7D5B" },
    warning: { main: "#C97A2B" },
    error: { main: "#C0392B" },
    divider: "#E3E6EB",
  },
  typography: sharedTypography,
  shape: {
    borderRadius: 10,
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: "#FFFFFF",
          backgroundImage: "none",
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: "#FFFFFF",
          backgroundImage: "none",
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontWeight: 700,
          backgroundColor: "#F5F7FA",
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
        },
      },
    },
  },
});

// ============================================================
// ۲) مدرن شیشه‌ای (Dark/Glass)
// ============================================================
const GLASS_SURFACE = "rgba(42, 53, 82, 0.55)";
const GLASS_SURFACE_STRONG = "rgba(30, 39, 62, 0.7)";
const GLASS_BORDER = "1px solid rgba(255, 255, 255, 0.09)";
const GLASS_BLUR = "blur(20px)";
const GRADIENT_ACCENT = "linear-gradient(135deg, #2DD4BF 0%, #A78BFA 100%)";

export const legacyDarkTheme = createTheme({
  direction: "rtl",
  palette: {
    mode: "dark",
    primary: {
      main: "#2DD4BF",
      light: "#5EEAD4",
      dark: "#14B8A6",
      contrastText: "#07110E",
    },
    secondary: {
      main: "#A78BFA",
      light: "#C4B5FD",
      dark: "#8B5CF6",
      contrastText: "#150F26",
    },
    background: {
      default: "#161F33",
      paper: GLASS_SURFACE,
    },
    text: {
      primary: "#EEF2F7",
      secondary: "#A0ABC0",
    },
    success: { main: "#34D399" },
    warning: { main: "#FBBF24" },
    error: { main: "#F87171" },
    divider: "rgba(255, 255, 255, 0.10)",
  },
  typography: sharedTypography,
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          minHeight: "100vh",
          background:
            "radial-gradient(circle at 15% 10%, rgba(45, 212, 191, 0.18), transparent 45%)," +
            "radial-gradient(circle at 85% 0%, rgba(167, 139, 250, 0.20), transparent 48%)," +
            "radial-gradient(circle at 50% 100%, rgba(45, 212, 191, 0.10), transparent 55%)," +
            "#161F33",
          backgroundAttachment: "fixed",
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
        },
        outlined: {
          backgroundColor: GLASS_SURFACE,
          backdropFilter: GLASS_BLUR,
          WebkitBackdropFilter: GLASS_BLUR,
          border: GLASS_BORDER,
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.32)",
        },
        elevation1: {
          backgroundColor: GLASS_SURFACE,
          backdropFilter: GLASS_BLUR,
          WebkitBackdropFilter: GLASS_BLUR,
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.32)",
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: GLASS_SURFACE_STRONG,
          backgroundImage: "none",
          backdropFilter: GLASS_BLUR,
          WebkitBackdropFilter: GLASS_BLUR,
          boxShadow: "none",
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: GLASS_SURFACE_STRONG,
          backgroundImage: "none",
          backdropFilter: GLASS_BLUR,
          WebkitBackdropFilter: GLASS_BLUR,
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundColor: "rgba(24, 32, 52, 0.97)",
          backgroundImage: "none",
          backdropFilter: GLASS_BLUR,
          WebkitBackdropFilter: GLASS_BLUR,
          border: GLASS_BORDER,
          boxShadow: "0 20px 60px rgba(0, 0, 0, 0.5)",
        },
      },
    },
    MuiPopover: {
      styleOverrides: {
        paper: {
          backgroundColor: "rgba(24, 32, 52, 0.97)",
          backgroundImage: "none",
          backdropFilter: GLASS_BLUR,
          WebkitBackdropFilter: GLASS_BLUR,
          border: GLASS_BORDER,
          boxShadow: "0 12px 40px rgba(0, 0, 0, 0.45)",
        },
      },
    },
    MuiAutocomplete: {
      styleOverrides: {
        paper: {
          backgroundColor: "rgba(24, 32, 52, 0.97)",
          backgroundImage: "none",
          backdropFilter: GLASS_BLUR,
          WebkitBackdropFilter: GLASS_BLUR,
          border: GLASS_BORDER,
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 999,
          paddingInline: "20px",
        },
        contained: {
          backgroundImage: GRADIENT_ACCENT,
          color: "#07110E",
          boxShadow: "0 6px 20px rgba(45, 212, 191, 0.28)",
          "&:hover": {
            backgroundImage: "linear-gradient(135deg, #5EEAD4 0%, #C4B5FD 100%)",
            boxShadow: "0 8px 26px rgba(45, 212, 191, 0.4)",
          },
        },
        outlined: {
          borderColor: "rgba(255, 255, 255, 0.18)",
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontWeight: 700,
          backgroundColor: "rgba(255, 255, 255, 0.04)",
          borderBottom: "1px solid rgba(255, 255, 255, 0.09)",
        },
        root: {
          borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
          borderRadius: 999,
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        variant: "filled",
      },
    },
    MuiFilledInput: {
      styleOverrides: {
        root: {
          borderRadius: 14,
          backgroundColor: "rgba(255, 255, 255, 0.05)",
          "&:before, &:after": { display: "none" },
          "&:hover": { backgroundColor: "rgba(255, 255, 255, 0.07)" },
          "&.Mui-focused": { backgroundColor: "rgba(255, 255, 255, 0.08)" },
        },
      },
    },
  },
});
```

**اگر نیاز شد**: کد بالا را دقیقاً همان‌طور که هست به انتهای
`frontend/src/theme.js` برگردانید، `NEW_DESIGN_ENABLED` را دوباره
تعریف کنید و منطق شرطی `lightTheme`/`darkTheme` را برگردانید.

### ۷.۲ طراحی قدیمی صفحه ورود (`NEW_LOGIN_DESIGN_ENABLED`)

**فایل**: `frontend/src/pages/LoginPage.jsx`

یک شاخه کامل `if (!NEW_LOGIN_DESIGN_ENABLED) { return (...) }` — طرح
تک‌کارت وسط‌چین قدیمی صفحه ورود (لوگو در وسط، بدون پنل معرفی، بدون
پس‌زمینه گرادیانت، فرم ساده‌تر) — قبل از بازطراحی دوپانلی بر اساس
`personnel_login__1_.html`.

فلگ کنترل‌کننده:
```javascript
const NEW_LOGIN_DESIGN_ENABLED = true; // اگر false می‌شد، طرح قدیمی جایگزین می‌شد
```

متن کامل شاخه طرح قدیمی (برای بازسازی کامل بدون نیاز به Git):

```javascript
  if (!NEW_LOGIN_DESIGN_ENABLED) {
    // =====================================================================
    // طرح قدیمی — کاملاً دست‌نخورده، فقط برای راه برگشت
    // =====================================================================
    return (
      <Box
        sx={(theme) => ({
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: `linear-gradient(160deg, ${theme.palette.primary.dark} 0%, ${theme.palette.primary.main} 55%, ${theme.palette.primary.light} 100%)`,
          px: 2,
        })}
      >
        <Paper elevation={0} sx={{ width: "100%", maxWidth: 400, p: 4, borderRadius: 3 }}>
          <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", mb: 3 }}>
            <Box
              component="img"
              src="/faipco-logo.png"
              alt="FAIPCO"
              sx={{ width: 128, height: 128, objectFit: "contain", mb: 1.5 }}
            />
            <Typography variant="h6" fontWeight={700}>
              پرتال سازمانی پرسنل
            </Typography>
            <Typography variant="body2" color="text.secondary">
              شرکت تولیدی صنعتی فوادالیاف
            </Typography>
          </Box>

          {isOnline ? (
            <>
              {installPrompt}
              {error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  {error}
                </Alert>
              )}
              <Box component="form" onSubmit={handleSubmit} sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <TextField
                  label="نام کاربری"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  autoFocus
                  fullWidth
                />
                <TextField
                  label="رمز عبور"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  fullWidth
                />
                <Button type="submit" variant="contained" size="large" disabled={isSubmitting} sx={{ mt: 1 }}>
                  {isSubmitting ? "در حال ورود..." : "ورود"}
                </Button>
              </Box>
            </>
          ) : (
            offlineState
          )}
        </Paper>

        {appVersion && (
          <Typography variant="caption" color="text.secondary" sx={{ mt: 2, opacity: 0.6, direction: "ltr" }}>
            {appVersion}
          </Typography>
        )}

        {vpnDialog}
      </Box>
    );
  }
```

این طرح از `installPrompt`، `offlineState`، `vpnDialog`، `isOnline`،
`handleSubmit` و بقیه State/Logic **مشترک** با طرح جدید استفاده می‌کرد
(همان چیزهایی که هنوز در بالای کامپوننت `LoginPage` تعریف شده‌اند) —
پس برای بازسازی این طرح، فقط همین JSX کافی است، نیازی به بازگرداندن
منطق دیگری نیست.

**اگر نیاز شد**: کد بالا را دقیقاً همان‌طور که هست به داخل تابع
`LoginPage()` (بعد از تعریف `vpnDialog` و قبل از `return` طرح جدید)
برگردانید، و متغیر `NEW_LOGIN_DESIGN_ENABLED` را دوباره در بالای فایل
تعریف کنید.

---

## خلاصه — چرا این سند مهم است

هیچ‌کدام از موارد بالا برای عملکرد فعلی پرتال لازم نبودند (همه، قبل از
حذف، با یک بررسی دقیق تأیید شدند که واقعاً هیچ‌جا صدا زده نمی‌شوند) —
ولی اگر روزی یکی از این قابلیت‌ها (خصوصاً حضور GPS دوره‌ای، یا نیاز به
راه برگشت به طراحی قدیمی) دوباره لازم شد، این سند دقیقاً نشان می‌دهد
چه چیزی، کجا، و با چه منطقی باید بازسازی شود.
