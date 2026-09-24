"""
سرویس «فرم‌های ارزیابی عملکرد»: مدیریت فرم، دسته‌بندی، سوال و گزینه، فعال‌سازی فرم
(با اعتبارسنجی وزن‌ها) و ساخت نسخه جدید از فرم.

فرم در وضعیت draft آزادانه قابل ویرایش/حذف است. پس از فعال‌شدن Hard-Delete مجاز نیست،
چون ممکن است ارزیابی واقعی به آن وصل باشد؛ به‌جای آن نسخه جدید ساخته یا فرم archived می‌شود.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.evaluation_rules import validate_form_weights
from app.models.evaluation_content import (
    EvaluationCategory,
    EvaluationForm,
    EvaluationFormStatus,
    EvaluationQuestion,
    EvaluationQuestionOption,
)


class EvaluationFormError(Exception):
    """خطای قابل نمایش به کاربر در عملیات فرم‌ساز."""
    pass


def _full_form_query():
    """کوئری select فرم همراه با بارگذاری کامل دسته‌بندی‌ها، سوالات و گزینه‌ها (selectinload) را برمی‌گرداند."""
    return select(EvaluationForm).options(
        selectinload(EvaluationForm.categories)
        .selectinload(EvaluationCategory.questions)
        .selectinload(EvaluationQuestion.options)
    )


class EvaluationFormService:
    """سرویس CRUD فرم‌ها، دسته‌بندی‌ها و سوالات ارزیابی."""

    def __init__(self, db: AsyncSession):
        """ورودی: نشست async دیتابیس."""
        self.db = db

    # ---------- فرم ----------

    async def list_forms(
        self, site_id: int | None = None, allowed_site_ids: set[int] | None = None
    ) -> list[EvaluationForm]:
        """
        فهرست فرم‌ها (جدیدترین اول)؛ با site_id، فرم‌های آن سایت به‌علاوه فرم‌های سراسری.
        allowed_site_ids: فقط فرم‌های این سایت‌ها به‌علاوه‌ی فرم‌های سراسری (None = بدون محدودیت).
        """
        query = select(EvaluationForm).order_by(EvaluationForm.created_at.desc())
        if site_id is not None:
            query = query.where((EvaluationForm.site_id == site_id) | (EvaluationForm.site_id.is_(None)))
        if allowed_site_ids is not None:
            query = query.where(EvaluationForm.site_id.in_(allowed_site_ids) | EvaluationForm.site_id.is_(None))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_full_form(self, form_id: int) -> EvaluationForm:
        """فرم را با همه دسته‌بندی‌ها/سوالات/گزینه‌ها برمی‌گرداند؛ اگر نباشد EvaluationFormError."""
        result = await self.db.execute(_full_form_query().where(EvaluationForm.id == form_id))
        form = result.scalar_one_or_none()
        if form is None:
            raise EvaluationFormError("فرم ارزیابی موردنظر یافت نشد")
        return form

    async def create_form(self, data: dict, created_by_user_id: int | None) -> EvaluationForm:
        """ورودی: فیلدهای فرم و شناسه سازنده. فرم جدید (draft) را ذخیره و برمی‌گرداند."""
        form = EvaluationForm(**data, created_by_user_id=created_by_user_id)
        self.db.add(form)
        await self.db.commit()
        await self.db.refresh(form)
        return form

    async def update_form(self, form_id: int, data: dict) -> EvaluationForm:
        """فیلدهای فرم را به‌روز می‌کند؛ فقط برای فرم draft، در غیر این صورت EvaluationFormError."""
        form = await self.db.get(EvaluationForm, form_id)
        if form is None:
            raise EvaluationFormError("فرم ارزیابی موردنظر یافت نشد")
        if form.status != EvaluationFormStatus.draft:
            raise EvaluationFormError("فقط فرم‌های در وضعیت پیش‌نویس قابل‌ویرایش هستند")
        for key, value in data.items():
            setattr(form, key, value)
        await self.db.commit()
        await self.db.refresh(form)
        return form

    async def update_title(self, form_id: int, title: str) -> EvaluationForm:
        """
        عنوان فرم را در هر وضعیتی تغییر می‌دهد (برخلاف update_form که فقط برای draft است).
        ارزیابی‌های قبلی از form_title_snapshot استفاده می‌کنند، پس گزارش‌های تاریخی تغییر نمی‌کنند.
        """
        form = await self.db.get(EvaluationForm, form_id)
        if form is None:
            raise EvaluationFormError("فرم ارزیابی موردنظر یافت نشد")
        form.title = title
        await self.db.commit()
        await self.db.refresh(form)
        return form

    async def activate_form(self, form_id: int) -> EvaluationForm:
        """
        فرم را active می‌کند، به شرط معتبر بودن وزن‌ها (validate_form_weights)؛ در غیر این صورت
        EvaluationFormError با فهرست خطاها. وزن‌ها فقط در همین لحظه اعتبارسنجی می‌شوند.
        """
        form = await self.get_full_form(form_id)
        # تبدیل ساختار فرم به dict ساده برای تابع اعتبارسنجی وزن‌ها
        categories_data = [
            {
                "title": c.title,
                "weight": float(c.weight),
                "is_active": c.is_active,
                "questions": [
                    {"text": q.text, "weight": float(q.weight), "is_active": q.is_active} for q in c.questions
                ],
            }
            for c in form.categories
        ]
        errors = validate_form_weights(categories_data)
        if errors:
            raise EvaluationFormError(" — ".join(errors))
        form.status = EvaluationFormStatus.active
        await self.db.commit()
        await self.db.refresh(form)
        return form

    async def update_form_status(self, form_id: int, status: str) -> EvaluationForm:
        """وضعیت فرم را تغییر می‌دهد؛ active از مسیر activate_form می‌رود. وضعیت نامعتبر: EvaluationFormError."""
        if status == EvaluationFormStatus.active.value:
            return await self.activate_form(form_id)
        form = await self.db.get(EvaluationForm, form_id)
        if form is None:
            raise EvaluationFormError("فرم ارزیابی موردنظر یافت نشد")
        try:
            form.status = EvaluationFormStatus(status)
        except ValueError:
            raise EvaluationFormError(f"وضعیت «{status}» معتبر نیست")
        await self.db.commit()
        await self.db.refresh(form)
        return form

    async def delete_form(self, form_id: int) -> None:
        """فرم draft را حذف می‌کند؛ برای فرم غیر draft EvaluationFormError (باید بایگانی شود)."""
        form = await self.db.get(EvaluationForm, form_id)
        if form is None:
            return
        if form.status != EvaluationFormStatus.draft:
            raise EvaluationFormError(
                "این فرم در وضعیت پیش‌نویس نیست - برای حفظ تاریخچه، به‌جای حذف، وضعیت آن را «بایگانی» کنید"
            )
        await self.db.delete(form)
        await self.db.commit()

    async def duplicate_as_new_version(self, form_id: int) -> EvaluationForm:
        """
        از فرم داده‌شده یک نسخه جدید draft (version+1، parent_form_id=فرم اصلی) با کپی کامل
        دسته‌بندی‌ها، سوالات و گزینه‌ها می‌سازد؛ فرم اصلی دست‌نخورده می‌ماند. خروجی: فرم کامل جدید.
        """
        original = await self.get_full_form(form_id)
        new_form = EvaluationForm(
            site_id=original.site_id,
            title=original.title,
            description=original.description,
            version=original.version + 1,
            parent_form_id=original.id,
            status=EvaluationFormStatus.draft,
            created_by_user_id=original.created_by_user_id,
        )
        self.db.add(new_form)
        await self.db.flush()  # برای گرفتن new_form.id

        # کپی دسته‌بندی‌ها، و درون هر کدام سوالات و گزینه‌ها
        for category in original.categories:
            new_category = EvaluationCategory(
                form_id=new_form.id,
                title=category.title,
                weight=category.weight,
                sort_order=category.sort_order,
                is_active=category.is_active,
            )
            self.db.add(new_category)
            await self.db.flush()  # برای گرفتن new_category.id

            for question in category.questions:
                new_question = EvaluationQuestion(
                    category_id=new_category.id,
                    text=question.text,
                    description=question.description,
                    question_type=question.question_type,
                    weight=question.weight,
                    required=question.required,
                    sort_order=question.sort_order,
                    is_active=question.is_active,
                )
                self.db.add(new_question)
                await self.db.flush()  # برای گرفتن new_question.id

                for option in question.options:
                    self.db.add(
                        EvaluationQuestionOption(
                            question_id=new_question.id,
                            label=option.label,
                            score=option.score,
                            sort_order=option.sort_order,
                        )
                    )

        await self.db.commit()
        return await self.get_full_form(new_form.id)

    # ---------- دسته‌بندی ----------

    async def add_category(self, form_id: int, data: dict) -> EvaluationCategory:
        """دسته‌بندی جدید به فرم draft اضافه می‌کند و آن را همراه سوالات برمی‌گرداند؛ فرم غیر draft: EvaluationFormError."""
        form = await self.db.get(EvaluationForm, form_id)
        if form is None:
            raise EvaluationFormError("فرم ارزیابی موردنظر یافت نشد")
        if form.status != EvaluationFormStatus.draft:
            raise EvaluationFormError("فقط فرم‌های در وضعیت پیش‌نویس قابل‌ویرایش هستند")
        category = EvaluationCategory(form_id=form_id, **data)
        self.db.add(category)
        await self.db.flush()  # برای پرشدن category.id بدون Expire شدن (برخلاف commit)
        category_id = category.id
        await self.db.commit()
        return await self._get_category_with_questions(category_id)

    async def update_category(self, category_id: int, data: dict) -> EvaluationCategory:
        """فیلدهای دسته‌بندی را به‌روز می‌کند و آن را همراه سوالات برمی‌گرداند؛ اگر نباشد EvaluationFormError."""
        category = await self.db.get(EvaluationCategory, category_id)
        if category is None:
            raise EvaluationFormError("دسته‌بندی موردنظر یافت نشد")
        for key, value in data.items():
            setattr(category, key, value)
        await self.db.commit()
        return await self._get_category_with_questions(category_id)

    async def _get_category_with_questions(self, category_id: int) -> EvaluationCategory:
        """
        دسته‌بندی را همراه سوالات و گزینه‌ها با selectinload صریح می‌خواند؛ EvaluationCategoryOut
        شامل questions تودرتو است و بارگذاری تنبل در Session ناهمگام خطای MissingGreenlet می‌دهد.
        """
        result = await self.db.execute(
            select(EvaluationCategory)
            .options(selectinload(EvaluationCategory.questions).selectinload(EvaluationQuestion.options))
            .where(EvaluationCategory.id == category_id)
        )
        return result.scalar_one()

    async def delete_category(self, category_id: int) -> None:
        """دسته‌بندی (همراه سوالاتش) را حذف می‌کند؛ فقط اگر فرم draft باشد، وگرنه EvaluationFormError."""
        category = await self.db.get(EvaluationCategory, category_id)
        if category is None:
            return
        form = await self.db.get(EvaluationForm, category.form_id)
        if form is not None and form.status != EvaluationFormStatus.draft:
            raise EvaluationFormError("فقط دسته‌بندی‌های فرم‌های در وضعیت پیش‌نویس قابل‌حذف هستند")
        await self.db.delete(category)
        await self.db.commit()

    # ---------- سوال ----------

    async def add_question(self, category_id: int, data: dict, options: list[dict]) -> EvaluationQuestion:
        """ورودی: دسته‌بندی، فیلدهای سوال و فهرست گزینه‌ها. سوال و گزینه‌ها را ذخیره و سوال را همراه گزینه‌ها برمی‌گرداند."""
        category = await self.db.get(EvaluationCategory, category_id)
        if category is None:
            raise EvaluationFormError("دسته‌بندی موردنظر یافت نشد")
        question = EvaluationQuestion(category_id=category_id, **data)
        self.db.add(question)
        await self.db.flush()  # برای گرفتن question.id
        for option_data in options:
            self.db.add(EvaluationQuestionOption(question_id=question.id, **option_data))
        await self.db.commit()
        # بارگذاری مجدد سوال همراه گزینه‌ها برای خروجی
        result = await self.db.execute(
            select(EvaluationQuestion)
            .options(selectinload(EvaluationQuestion.options))
            .where(EvaluationQuestion.id == question.id)
        )
        return result.scalar_one()

    async def update_question(self, question_id: int, data: dict, options: list[dict] | None) -> EvaluationQuestion:
        """
        فیلدهای سوال را به‌روز می‌کند؛ اگر options داده شود، همه گزینه‌های قبلی حذف و گزینه‌های جدید جایگزین می‌شوند.
        خروجی: سوال همراه گزینه‌ها؛ اگر سوال نباشد EvaluationFormError.
        """
        question = await self.db.get(EvaluationQuestion, question_id)
        if question is None:
            raise EvaluationFormError("سوال موردنظر یافت نشد")
        for key, value in data.items():
            setattr(question, key, value)
        # جایگزینی کامل گزینه‌ها: حذف قبلی‌ها، flush (برای رهایی از UniqueConstraint روی sort_order)، سپس درج جدیدها
        if options is not None:
            existing_result = await self.db.execute(
                select(EvaluationQuestionOption).where(EvaluationQuestionOption.question_id == question_id)
            )
            for existing_option in existing_result.scalars().all():
                await self.db.delete(existing_option)
            await self.db.flush()
            for option_data in options:
                self.db.add(EvaluationQuestionOption(question_id=question_id, **option_data))
        await self.db.commit()
        # بارگذاری مجدد سوال همراه گزینه‌ها برای خروجی
        result = await self.db.execute(
            select(EvaluationQuestion)
            .options(selectinload(EvaluationQuestion.options))
            .where(EvaluationQuestion.id == question_id)
        )
        return result.scalar_one()

    async def delete_question(self, question_id: int) -> None:
        """سوال را (همراه گزینه‌ها) حذف می‌کند؛ سوال ناموجود بی‌اثر است."""
        question = await self.db.get(EvaluationQuestion, question_id)
        if question is None:
            return
        await self.db.delete(question)
        await self.db.commit()
