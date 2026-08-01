"""
Seed اولیه Permission ها و نقش‌های سیستمی پایه — شامل سلسله‌مراتب ارسال اطلاعیه.
این اسکریپت Idempotent است (اجرای چندباره مشکلی ایجاد نمی‌کند).

نقش‌های ساخته‌شده:
- superadmin      : دسترسی کامل به همه‌چیز
- ceo              : نقش سراسری — می‌تواند به «همه» (notices.target.all) اطلاعیه بفرستد
- hr_manager       : نقش سراسری — می‌تواند به تفکیک سایت/واحد/نقش/پرسنل بفرستد (نه Broadcast کامل)
- site_manager     : نقش Site-scoped — هنگام انتصاب به کاربر، حتماً site_id مشخص کنید
                     (از طریق /users/{id}/roles) تا فقط برای همان سایت معتبر باشد

سرپرست واحد (Department Supervisor) نیازی به نقش جداگانه ندارد — کافی است
از طریق PUT /departments/{id}/supervisor مستقیماً به آن واحد متصل شود.

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
    ("notices.view", "مشاهده لیست کامل اطلاعیه‌ها (پنل Admin)"),
    ("notices.create", "ایجاد اطلاعیه (مجوز پایه — مقصد دقیق در سطح Target بررسی می‌شود)"),
    ("notices.target.all", "ارسال اطلاعیه به کل سازمان (Broadcast)"),
    ("notices.target.site", "ارسال اطلاعیه به یک سایت"),
    ("notices.target.department", "ارسال اطلاعیه به یک واحد سازمانی"),
    ("notices.target.role", "ارسال اطلاعیه به یک نقش خاص"),
    ("notices.target.employee", "ارسال اطلاعیه به یک پرسنل خاص"),
    ("roles.manage", "مدیریت نقش‌ها و مجوزها"),
    ("users.manage", "مدیریت کاربران Portal و انتصاب نقش"),
]

# نقش -> فهرست کدهای Permission (به‌جز superadmin که همه را می‌گیرد)
ADDITIONAL_ROLES = {
    "ceo": {
        "description": "مدیرعامل / مدیر ارشد سازمان — نقش سراسری",
        "permissions": [
            "notices.target.all",
            "notices.target.site",
            "notices.target.department",
            "notices.target.role",
            "notices.target.employee",
            "notices.view",
            "employees.view",
            "sites.view",
        ],
    },
    "hr_manager": {
        "description": "مدیر منابع انسانی — نقش سراسری، بدون اجازه Broadcast کامل",
        "permissions": [
            "notices.target.site",
            "notices.target.department",
            "notices.target.role",
            "notices.target.employee",
            "notices.view",
            "employees.view",
        ],
    },
    "site_manager": {
        "description": "مدیر سایت — هنگام انتصاب به کاربر حتماً site_id بدهید تا فقط برای همان سایت باشد",
        "permissions": [
            "notices.target.site",
            "notices.target.department",
            "notices.target.employee",
            "notices.view",
            "employees.view",
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

        # 2. نقش سیستمی superadmin با همه Permission ها
        result = await db.execute(select(Role).where(Role.name == "superadmin"))
        superadmin_role = result.scalar_one_or_none()
        if superadmin_role is None:
            superadmin_role = Role(
                name="superadmin", description="دسترسی کامل به تمام بخش‌های سیستم", is_system=True
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

        # 3. نقش‌های سازمانی سلسله‌مراتب اطلاعیه (ceo / hr_manager / site_manager)
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

        await db.commit()
        print(
            f"Seed کامل شد: {len(code_to_permission)} Permission، "
            f"نقش‌های superadmin/ceo/hr_manager/site_manager آماده‌اند."
        )


if __name__ == "__main__":
    asyncio.run(seed())
