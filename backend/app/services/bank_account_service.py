"""
سرویس ماژول «اطلاعات بانکی» پرسنل (docs/bank-accounts.md).

- تعریف بانک‌های هر سایت (پنل ادمین، مجوز bank_accounts.manage): نام، اجباری بودن، حالت فیلدها، فعال/غیرفعال، ترتیب.
- پرسنل: دیدن بانک‌های فعال سایت خودش و ثبت/تغییر آزاد اطلاعات هر بانک؛ هر تغییر در سابقه ثبت می‌شود.
- «تکمیل نشده»: یکی از بانک‌های فعالِ اجباری سایت ثبت نشده یا فیلد اجباری‌اش خالی است (فقط یادآوری، بدون مسدودسازی).
- گزارش/خروجی (bank_accounts.view، محدود به سایت‌های مجاز): پرسنل فعال × بانک‌ها.
اطلاعات بانکی هر پرسنل فقط برای خودش و دارندگان مجوز همان سایت قابل مشاهده است.
"""
from __future__ import annotations

import io

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import bank_rules as rules
from app.core.text_normalize import normalize_search_text
from app.models.bank_account import (
    BankDefinition,
    EmployeeBankAccount,
    EmployeeBankAccountHistory,
)
from app.models.employee import Department, Employee
from app.models.site import Site
from app.models.user import User


class BankAccountError(Exception):
    """خطای منطقی قابل نمایش (۴۰۰)."""


def _bank_out(bank: BankDefinition) -> dict:
    return {
        "id": bank.id,
        "site_id": bank.site_id,
        "name": bank.name,
        "is_required": bank.is_required,
        "account_number_mode": bank.account_number_mode,
        "sheba_mode": bank.sheba_mode,
        "card_number_mode": bank.card_number_mode,
        "is_active": bank.is_active,
        "sort_order": bank.sort_order,
    }


def _account_values(acc: EmployeeBankAccount | None) -> dict | None:
    if acc is None:
        return None
    return {"account_number": acc.account_number, "sheba": acc.sheba, "card_number": acc.card_number}


class BankAccountService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- تعریف بانک‌ها ----------

    async def list_banks(self, site_id: int, active_only: bool = False) -> list[BankDefinition]:
        q = select(BankDefinition).where(BankDefinition.site_id == site_id)
        if active_only:
            q = q.where(BankDefinition.is_active.is_(True))
        res = await self.db.execute(q.order_by(BankDefinition.sort_order, BankDefinition.id))
        return list(res.scalars().all())

    @staticmethod
    def _apply_bank_fields(bank: BankDefinition, data: dict) -> None:
        if "name" in data:
            name = (data["name"] or "").strip()
            if not name:
                raise BankAccountError("نام بانک الزامی است")
            bank.name = name[:100]
        for field in ("account_number_mode", "sheba_mode", "card_number_mode"):
            if field in data and data[field] is not None:
                try:
                    setattr(bank, field, rules.validate_mode(data[field]))
                except rules.BankRulesError as e:
                    raise BankAccountError(str(e)) from e
        for field in ("is_required", "is_active"):
            if field in data and data[field] is not None:
                setattr(bank, field, bool(data[field]))
        if data.get("sort_order") is not None:
            bank.sort_order = int(data["sort_order"])
        if all(mode == "hidden" for mode in bank.modes.values()):
            raise BankAccountError("حداقل یکی از فیلدهای شماره حساب، شبا یا شماره کارت باید نمایش داده شود")

    async def _ensure_unique_name(self, site_id: int, name: str, exclude_id: int | None = None) -> None:
        q = select(BankDefinition.id).where(
            BankDefinition.site_id == site_id, func.lower(BankDefinition.name) == name.strip().lower()
        )
        if exclude_id is not None:
            q = q.where(BankDefinition.id != exclude_id)
        if (await self.db.execute(q)).first():
            raise BankAccountError("بانکی با همین نام برای این سایت تعریف شده است")

    async def add_bank(self, site_id: int, data: dict) -> dict:
        await self._ensure_unique_name(site_id, data.get("name") or "")
        if data.get("sort_order") is None:
            last = await self.db.scalar(
                select(func.max(BankDefinition.sort_order)).where(BankDefinition.site_id == site_id)
            )
            data = {**data, "sort_order": (last or 0) + 1}
        bank = BankDefinition(site_id=site_id)
        self._apply_bank_fields(bank, {"is_required": True, "is_active": True, **data})
        self.db.add(bank)
        await self.db.commit()
        await self.db.refresh(bank)
        return _bank_out(bank)

    async def get_bank(self, bank_id: int) -> BankDefinition:
        bank = await self.db.get(BankDefinition, bank_id)
        if bank is None:
            raise BankAccountError("بانک موردنظر یافت نشد")
        return bank

    async def update_bank(self, bank_id: int, data: dict) -> dict:
        bank = await self.get_bank(bank_id)
        if data.get("name"):
            await self._ensure_unique_name(bank.site_id, data["name"], exclude_id=bank.id)
        self._apply_bank_fields(bank, data)
        await self.db.commit()
        await self.db.refresh(bank)
        return _bank_out(bank)

    async def delete_bank(self, bank_id: int) -> None:
        """فقط بانکی که هیچ پرسنلی برایش اطلاعات ثبت نکرده حذف می‌شود؛ وگرنه باید غیرفعال شود (اطلاعات حفظ شود)."""
        bank = await self.get_bank(bank_id)
        used = await self.db.scalar(
            select(func.count()).select_from(EmployeeBankAccount).where(EmployeeBankAccount.bank_id == bank_id)
        )
        if used:
            raise BankAccountError(
                f"برای این بانک {used} پرسنل اطلاعات ثبت کرده‌اند و حذف نمی‌شود؛ به‌جای حذف، آن را غیرفعال کنید"
            )
        await self.db.delete(bank)
        await self.db.commit()

    # ---------- پرسنل ----------

    async def _accounts_of(self, employee_id: int) -> dict[int, EmployeeBankAccount]:
        res = await self.db.execute(select(EmployeeBankAccount).where(EmployeeBankAccount.employee_id == employee_id))
        return {a.bank_id: a for a in res.scalars().all()}

    async def employee_info(self, employee: Employee) -> dict:
        """بانک‌های فعال سایت پرسنل با اطلاعات ثبت‌شده‌ی او؛ missing_required اگر یکی از بانک‌های اجباری کامل نیست."""
        banks = await self.list_banks(employee.site_id, active_only=True)
        accounts = await self._accounts_of(employee.id)
        items = []
        for bank in banks:
            acc = accounts.get(bank.id)
            values = _account_values(acc)
            items.append({
                **_bank_out(bank),
                "account": values,
                "updated_at": acc.updated_at if acc else None,
                "complete": rules.is_complete(bank.modes, values),
            })  # fmt: skip
        missing = [i["name"] for i in items if i["is_required"] and not i["complete"]]
        return {"banks": items, "missing_required": bool(missing), "missing_banks": missing}

    async def is_missing_required(self, employee_id: int, site_id: int) -> bool:
        banks = [b for b in await self.list_banks(site_id, active_only=True) if b.is_required]
        if not banks:
            return False
        accounts = await self._accounts_of(employee_id)
        return any(not rules.is_complete(b.modes, _account_values(accounts.get(b.id))) for b in banks)

    async def save_account(
        self, employee: Employee, bank_id: int, data: dict, actor: User, by_admin: bool = False
    ) -> dict:
        """ثبت/تغییر اطلاعات یک بانک برای یک پرسنل؛ تغییرات در سابقه ثبت می‌شود. خروجی: employee_info به‌روز."""
        bank = await self.get_bank(bank_id)
        if bank.site_id != employee.site_id:
            raise BankAccountError("این بانک برای سایت این پرسنل تعریف نشده است")
        if not bank.is_active and not by_admin:
            raise BankAccountError("این بانک غیرفعال است")
        try:
            values = rules.clean_account_data(bank.modes, data)
        except rules.BankRulesError as e:
            raise BankAccountError(str(e)) from e
        accounts = await self._accounts_of(employee.id)
        acc = accounts.get(bank.id)
        old = _account_values(acc)
        # فیلدهای مخفیِ این بانک که قبلاً پر شده‌اند دست نمی‌خورند (مثلاً بعد از تغییر حالت فیلد در پنل ادمین)
        for field, mode in bank.modes.items():
            if mode == "hidden" and old:
                values[field] = old.get(field)
        changes = rules.changed_fields(old, values)
        if acc is None:
            acc = EmployeeBankAccount(employee_id=employee.id, bank_id=bank.id)
            self.db.add(acc)
        elif not changes:
            return await self.employee_info(employee)
        acc.account_number = values["account_number"]
        acc.sheba = values["sheba"]
        acc.card_number = values["card_number"]
        acc.updated_by_user_id = actor.id
        actor_name = await self._actor_name(actor)
        self.db.add(
            EmployeeBankAccountHistory(
                employee_id=employee.id,
                bank_id=bank.id,
                bank_name=bank.name,
                changes=changes,
                changed_by_user_id=actor.id,
                changed_by_name=actor_name,
                by_admin=by_admin,
            )
        )
        await self.db.commit()
        return await self.employee_info(employee)

    async def _actor_name(self, actor: User) -> str:
        if actor.employee_id:
            emp = await self.db.get(Employee, actor.employee_id)
            if emp:
                return f"{emp.first_name} {emp.last_name}"
        return getattr(actor, "username", "") or ""

    async def history(self, employee_id: int, masked: bool) -> list[dict]:
        """سابقه‌ی تغییرات (جدیدترین اول). masked: فقط چهار رقم آخر نمایش داده شود."""
        res = await self.db.execute(
            select(EmployeeBankAccountHistory)
            .where(EmployeeBankAccountHistory.employee_id == employee_id)
            .order_by(EmployeeBankAccountHistory.created_at.desc(), EmployeeBankAccountHistory.id.desc())
        )
        out = []
        for h in res.scalars().all():
            changes = []
            for field, pair in (h.changes or {}).items():
                old, new = (pair + [None, None])[:2] if isinstance(pair, list) else (None, None)
                changes.append({
                    "field": field,
                    "label": rules.FIELDS.get(field, field),
                    "old": rules.mask(old) if masked else (old or "—"),
                    "new": rules.mask(new) if masked else (new or "—"),
                })  # fmt: skip
            out.append({
                "id": h.id,
                "bank_name": h.bank_name,
                "changes": changes,
                "changed_by_name": h.changed_by_name,
                "by_admin": h.by_admin,
                "created_at": h.created_at,
            })  # fmt: skip
        return out

    # ---------- گزارش ----------

    async def report(
        self,
        site_ids: set[int] | None,
        site_id: int | None = None,
        search: str | None = None,
        status: str | None = None,
    ) -> dict:
        """
        پرسنل فعال سایت‌های مجاز با اطلاعات هر بانک. site_id: یک سایت (برای ستون‌های بانک لازم است؛ اگر نیاید اولین سایت).
        status: complete / missing. خروجی: {banks, items, counts}.
        """
        q = (
            select(Employee, Department.name, Site.name)
            .outerjoin(Department, Department.id == Employee.department_id)
            .join(Site, Site.id == Employee.site_id)
            .where(Employee.is_active.is_(True))
        )
        if site_id is not None:
            q = q.where(Employee.site_id == site_id)
        if site_ids is not None:
            q = q.where(Employee.site_id.in_(site_ids or {-1}))
        rows = (await self.db.execute(q.order_by(Employee.last_name, Employee.first_name))).all()

        site_of = {emp.site_id for emp, _, _ in rows}
        banks_by_site: dict[int, list[BankDefinition]] = {}
        for sid in site_of:
            banks_by_site[sid] = await self.list_banks(sid, active_only=True)
        emp_ids = [emp.id for emp, _, _ in rows]
        accounts: dict[int, dict[int, EmployeeBankAccount]] = {}
        if emp_ids:
            res = await self.db.execute(select(EmployeeBankAccount).where(EmployeeBankAccount.employee_id.in_(emp_ids)))
            for a in res.scalars().all():
                accounts.setdefault(a.employee_id, {})[a.bank_id] = a

        key = normalize_search_text(search or "").strip()
        items, counts = [], {"total": 0, "complete": 0, "missing": 0}
        for emp, dept_name, site_name in rows:
            banks = banks_by_site.get(emp.site_id, [])
            per_bank = []
            missing = False
            for bank in banks:
                values = _account_values(accounts.get(emp.id, {}).get(bank.id))
                complete = rules.is_complete(bank.modes, values)
                if bank.is_required and not complete:
                    missing = True
                per_bank.append({"bank_id": bank.id, "account": values, "complete": complete})
            item = {
                "employee_id": emp.id,
                "personnel_code": emp.personnel_code,
                "first_name": emp.first_name,
                "last_name": emp.last_name,
                "department_name": dept_name,
                "site_id": emp.site_id,
                "site_name": site_name,
                "accounts": per_bank,
                "missing_required": missing,
            }
            if key:
                haystack = " ".join(
                    str(x or "")
                    for x in (emp.personnel_code, emp.first_name, emp.last_name, dept_name)
                )
                haystack += " " + " ".join(
                    " ".join(v or "" for v in (b["account"] or {}).values()) for b in per_bank
                )
                if key not in normalize_search_text(haystack):
                    continue
            counts["total"] += 1
            counts["missing" if missing else "complete"] += 1
            if status == "missing" and not missing:
                continue
            if status == "complete" and missing:
                continue
            items.append(item)
        bank_columns = []
        seen = set()
        for sid in sorted(banks_by_site):
            for b in banks_by_site[sid]:
                if b.id not in seen:
                    seen.add(b.id)
                    bank_columns.append(_bank_out(b))
        return {"banks": bank_columns, "items": items, "counts": counts}

    async def export_xlsx(self, site_ids: set[int] | None, site_id: int | None, status: str | None) -> bytes:
        """یک برگه: هر پرسنل یک سطر؛ برای هر بانک ستون‌های شماره حساب/شبا/کارت (فیلدهای مخفی حذف)."""
        from openpyxl import Workbook

        data = await self.report(site_ids, site_id, None, status)
        wb = Workbook()
        ws = wb.active
        ws.title = "اطلاعات بانکی"
        ws.sheet_view.rightToLeft = True
        header = ["کد پرسنلی", "نام", "نام خانوادگی", "سایت", "واحد", "وضعیت"]
        cols: list[tuple[int, str]] = []
        for bank in data["banks"]:
            for field, label in rules.FIELDS.items():
                if bank[f"{field}_mode"] != "hidden":
                    header.append(f"{bank['name']} - {label}")
                    cols.append((bank["id"], field))
        ws.append(header)
        for item in data["items"]:
            by_bank = {b["bank_id"]: b["account"] or {} for b in item["accounts"]}
            row = [
                item["personnel_code"], item["first_name"], item["last_name"], item["site_name"] or "",
                item["department_name"] or "", "تکمیل نشده" if item["missing_required"] else "تکمیل",
            ]  # fmt: skip
            row += [by_bank.get(bank_id, {}).get(field) or "" for bank_id, field in cols]
            ws.append(row)
        # شماره‌ها متن بمانند (صفرهای ابتدای شماره حساب و نمایش علمی اکسل)
        for column in ws.iter_cols(min_row=2, min_col=7):
            for cell in column:
                cell.number_format = "@"
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()
