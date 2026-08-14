"""
Seed اولیه Permission ها و نقش‌های سیستمی — شامل سلسله‌مراتب ارسال اطلاعیه.
این اسکریپت Idempotent است (اجرای چندباره مشکلی ایجاد نمی‌کند).

نقش‌های ساخته‌شده:
- superadmin       : دسترسی کامل به همه‌چیز — فقط باید به کاربر «admin» تعلق داشته باشد،
                      از UI مدیریت دسترسی قابل انتصاب نیست (محافظت‌شده در کد)
- site_manager     : نقش Site-scoped — هنگام انتصاب حتماً site_id بدهید. می‌تواند:
                      کل سایت / واحدهای همان سایت / پرسنل همان سایت را هدف بگیرد
- middle_manager   : نقش سراسری (بدون site_id) — می‌تواند هر واحد یا هر پرسنلی در
                      کل سازمان را هدف بگیرد (نه Broadcast کامل به همه)
- acc_manager      : مدیر حسابداری — فقط اطلاعیه فیش حقوقی (Payroll) می‌سازد؛ با
                      آپلود XML، مخاطبان به‌صورت خودکار از روی کدهای موجود در همان
                      XML تعیین می‌شوند (نه با انتخاب دستی Site/Department/Employee)
- hr-manager       : مدیر منابع انسانی — فقط اطلاعیه فیش کارکرد (Attendance Card)
                      می‌سازد؛ با آپلود اکسل، مخاطبان به‌صورت خودکار از روی کدهای
                      موجود در همان اکسل تعیین می‌شوند (دقیقاً هم‌ساختار acc_manager)

«مدیر واحد» (سرپرست) اصلاً نقش RBAC جداگانه‌ای ندارد — کافی است از طریق
PUT /departments/{id}/supervisor مستقیماً سرپرست آن واحد تعیین شود.
یک نفر می‌تواند هم‌زمان سرپرست چند واحد باشد و/یا نقش middle_manager هم داشته باشد.

اجرا:
    cd backend && source .venv/bin/activate && cd .. && python -m scripts.seed_permissions
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.user import Permission, Role, RolePermission

DEFAULT_PERMISSIONS = [
    ("employees.view", "مشاهده لیست پرسنل"),
    ("employees.create", "افزودن دستی پرسنل"),
    ("employees.update", "ویرایش اطلاعات پرسنل"),
    ("sites.view", "مشاهده سایت‌ها"),
    ("sites.manage", "مدیریت سایت‌ها و اتصال دیتابیس"),
    ("sync.view", "مشاهده وضعیت Sync"),
    ("sync.run", "اجرای دستی Sync"),
    ("sync.manage", "تغییر تنظیمات Sync (فاصله زمانی اجرای خودکار)"),
    ("notices.view", "مشاهده لیست کامل اطلاعیه‌ها (پنل Admin)"),
    ("notices.create", "ایجاد اطلاعیه (مجوز پایه — مقصد دقیق در سطح Target بررسی می‌شود)"),
    ("notices.target.all", "ارسال اطلاعیه به کل سازمان (Broadcast) — فقط superadmin"),
    ("notices.target.site", "ارسال اطلاعیه به یک سایت کامل"),
    ("notices.target.department", "ارسال اطلاعیه به یک یا چند واحد سازمانی"),
    ("notices.target.role", "ارسال اطلاعیه به یک نقش خاص"),
    ("notices.target.employee", "ارسال اطلاعیه به یک یا چند پرسنل خاص"),
    ("notices.payroll", "آپلود و ارسال اطلاعیه فیش حقوقی (Payroll Notice)"),
    ("notices.attendance_card", "آپلود و ارسال اطلاعیه فیش کارکرد (Attendance Card Notice)"),
    ("roles.manage", "مدیریت نقش‌ها و مجوزها"),
    ("users.manage", "مدیریت کاربران Portal و انتصاب نقش"),
    ("system.backup", "دانلود بکاپ کامل سیستم — فقط superadmin (به هیچ نقش دیگری داده نمی‌شود)"),
    ("system.cache_bust", "پاک‌کردن کش اپ برای همه کاربران — فقط superadmin (به هیچ نقش دیگری داده نمی‌شود)"),
    ("system.ip_allowlist", "مدیریت رنج‌های IP مجاز برای ورود — فقط superadmin (به هیچ نقش دیگری داده نمی‌شود)"),
    (
        "attendance.clock_in_out",
        "ثبت ورود/خروج آزمایشی مبتنی بر GPS — قابلیت آزمایشی، جایگزین دستگاه‌های حضور و غیاب کارخانه نیست",
    ),
]

# نقش -> فهرست کدهای Permission (به‌جز superadmin که همه را می‌گیرد)
ADDITIONAL_ROLES = {
    "site_manager": {
        "description": "مدیر سایت — حتماً هنگام انتصاب site_id بدهید تا فقط برای همان سایت معتبر باشد",
        "permissions": [
            "notices.target.site",
            "notices.target.department",
            "notices.target.employee",
        ],
    },
    "middle_manager": {
        "description": "مدیر میانی — نقش سراسری، می‌تواند هر سایت/واحد/پرسنلی را در کل سازمان هدف بگیرد",
        "permissions": [
            "notices.target.site",
            "notices.target.department",
            "notices.target.employee",
        ],
    },
    "acc_manager": {
        "description": (
            "مدیر حسابداری — فقط می‌تواند اطلاعیه فیش حقوقی (Payroll) با آپلود XML بسازد؛ "
            "مخاطبان به‌صورت خودکار از روی کدهای موجود در همان XML تعیین می‌شوند، نه با انتخاب دستی Target"
        ),
        "permissions": [
            "notices.payroll",
            "notices.view",  # برای دیدن گزارش «ارسالی من»
        ],
    },
    "hr-manager": {
        "description": (
            "مدیر منابع انسانی — فقط می‌تواند اطلاعیه فیش کارکرد (Attendance Card) با آپلود اکسل بسازد؛ "
            "مخاطبان به‌صورت خودکار از روی کدهای موجود در همان اکسل تعیین می‌شوند، نه با انتخاب دستی Target"
        ),
        "permissions": [
            "notices.attendance_card",
            "notices.view",  # برای دیدن گزارش «ارسالی من»
        ],
    },
    "attendance-pilot": {
        "description": (
            "پرسنل مجاز به استفاده از «ثبت ورود/خروج آزمایشی» مبتنی بر GPS — قابلیتی آزمایشی؛ "
            "ثبت ورود/خروج رسمی همچنان باید از طریق دستگاه‌های تعبیه‌شده در کارخانه انجام شود. "
            "این نقش را فقط به پرسنلی که می‌خواهید در آزمایش این قابلیت شرکت کنند اختصاص دهید "
            "(از همان صفحه «مدیریت دسترسی»، دقیقاً مثل هر نقش دیگر)."
        ),
        "permissions": [
            "attendance.clock_in_out",
        ],
    },
}


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        # 1. Permission ها
        code_to_permission: dict[str, Permission] = {}
        for code, description in DEFAULT_PERMISSIONS:
            result = await db.execute(select(Permission).where(Permission.code == code))
            perm = result.scalar_one_or_none()
            if perm is None:
                perm = Permission(code=code, description=description)
                db.add(perm)
                await db.flush()
            code_to_permission[code] = perm

        # 2. نقش سیستمی superadmin با همه Permission ها (فقط کاربر admin این نقش را دارد)
        result = await db.execute(select(Role).where(Role.name == "superadmin"))
        superadmin_role = result.scalar_one_or_none()
        if superadmin_role is None:
            superadmin_role = Role(
                name="superadmin", description="دسترسی کامل — غیرقابل انتصاب از UI", is_system=True
            )
            db.add(superadmin_role)
            await db.flush()

        for perm in code_to_permission.values():
            result = await db.execute(
                select(RolePermission).where(
                    RolePermission.role_id == superadmin_role.id,
                    RolePermission.permission_id == perm.id,
                )
            )
            if result.scalar_one_or_none() is None:
                db.add(RolePermission(role_id=superadmin_role.id, permission_id=perm.id))

        # 3. نقش‌های سازمانی سلسله‌مراتب اطلاعیه (site_manager / middle_manager)
        for role_name, config in ADDITIONAL_ROLES.items():
            result = await db.execute(select(Role).where(Role.name == role_name))
            role = result.scalar_one_or_none()
            if role is None:
                role = Role(name=role_name, description=config["description"], is_system=True)
                db.add(role)
                await db.flush()

            for code in config["permissions"]:
                perm = code_to_permission[code]
                result = await db.execute(
                    select(RolePermission).where(
                        RolePermission.role_id == role.id,
                        RolePermission.permission_id == perm.id,
                    )
                )
                if result.scalar_one_or_none() is None:
                    db.add(RolePermission(role_id=role.id, permission_id=perm.id))

        # 4. حذف نقش‌های قدیمی که دیگر استفاده نمی‌شوند (ceo / hr_manager)، اگر از قبل ساخته شده بودند
        for old_role_name in ("ceo", "hr_manager"):
            result = await db.execute(select(Role).where(Role.name == old_role_name))
            old_role = result.scalar_one_or_none()
            if old_role is not None:
                await db.execute(
                    RolePermission.__table__.delete().where(RolePermission.role_id == old_role.id)
                )
                await db.delete(old_role)

        await db.commit()
        print(
            f"Seed کامل شد: {len(code_to_permission)} Permission، "
            f"نقش‌های superadmin/site_manager/middle_manager آماده‌اند."
        )


if __name__ == "__main__":
    asyncio.run(seed())
