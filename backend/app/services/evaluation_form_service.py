"""
سرویس «فرم‌های ارزیابی عملکرد» - مدیریت فرم، دسته‌بندی، سوال و گزینه.

⚠️ Historical Integrity: تا وقتی فرمی هنوز در وضعیت draft است، آزادانه
قابل‌ویرایش/حذف است. بعد از فعال‌شدن (active)، دیگر Hard-Delete مجاز
نیست - چون ممکن است ارزیابی واقعی به آن مرتبط شده باشد (آن بخش در
مرحله بعدی این ماژول ساخته می‌شود)؛ به‌جای حذف، باید نسخه جدید
(Versioning) ساخته شود یا به archived تغییر وضعیت دهد.
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
    pass


def _full_form_query():
    return select(EvaluationForm).options(
        selectinload(EvaluationForm.categories)
        .selectinload(EvaluationCategory.questions)
        .selectinload(EvaluationQuestion.options)
    )


class EvaluationFormService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- فرم ----------

    async def list_forms(self, site_id: int | None = None) -> list[EvaluationForm]:
        query = select(EvaluationForm).order_by(EvaluationForm.created_at.desc())
        if site_id is not None:
            query = query.where((EvaluationForm.site_id == site_id) | (EvaluationForm.site_id.is_(None)))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_full_form(self, form_id: int) -> EvaluationForm:
        result = await self.db.execute(_full_form_query().where(EvaluationForm.id == form_id))
        form = result.scalar_one_or_none()
        if form is None:
            raise EvaluationFormError("فرم ارزیابی موردنظر یافت نشد")
        return form

    async def create_form(self, data: dict, created_by_user_id: int | None) -> EvaluationForm:
        form = EvaluationForm(**data, created_by_user_id=created_by_user_id)
        self.db.add(form)
        await self.db.commit()
        await self.db.refresh(form)
        return form

    async def update_form(self, form_id: int, data: dict) -> EvaluationForm:
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

    async def activate_form(self, form_id: int) -> EvaluationForm:
        """
        فرم را از draft به active می‌برد - فقط اگر مجموع وزن‌ها معتبر
        باشد (validate_form_weights). این تنها لحظه‌ای است که وزن‌ها
        اعتبارسنجی می‌شوند - نه هنگام ذخیره تک‌تک سوالات (که هنوز ممکن
        است فرم ناقص باشد).
        """
        form = await self.get_full_form(form_id)
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
        Form Versioning: از یک فرم فعال/بایگانی، یک نسخه جدید (Draft، با
        version افزایش‌یافته و parent_form_id به این فرم) می‌سازد - فرم
        اصلی دست‌نخورده باقی می‌ماند (تاریخچه ارزیابی‌های قبلی‌اش سالم
        می‌ماند)، ویرایش‌های بعدی روی نسخه جدید انجام می‌شود.
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
        await self.db.flush()

        for category in original.categories:
            new_category = EvaluationCategory(
                form_id=new_form.id,
                title=category.title,
                weight=category.weight,
                sort_order=category.sort_order,
                is_active=category.is_active,
            )
            self.db.add(new_category)
            await self.db.flush()

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
                await self.db.flush()

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
        form = await self.db.get(EvaluationForm, form_id)
        if form is None:
            raise EvaluationFormError("فرم ارزیابی موردنظر یافت نشد")
        if form.status != EvaluationFormStatus.draft:
            raise EvaluationFormError("فقط فرم‌های در وضعیت پیش‌نویس قابل‌ویرایش هستند")
        category = EvaluationCategory(form_id=form_id, **data)
        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)
        return category

    async def update_category(self, category_id: int, data: dict) -> EvaluationCategory:
        category = await self.db.get(EvaluationCategory, category_id)
        if category is None:
            raise EvaluationFormError("دسته‌بندی موردنظر یافت نشد")
        for key, value in data.items():
            setattr(category, key, value)
        await self.db.commit()
        await self.db.refresh(category)
        return category

    async def delete_category(self, category_id: int) -> None:
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
        category = await self.db.get(EvaluationCategory, category_id)
        if category is None:
            raise EvaluationFormError("دسته‌بندی موردنظر یافت نشد")
        question = EvaluationQuestion(category_id=category_id, **data)
        self.db.add(question)
        await self.db.flush()
        for option_data in options:
            self.db.add(EvaluationQuestionOption(question_id=question.id, **option_data))
        await self.db.commit()
        result = await self.db.execute(
            select(EvaluationQuestion)
            .options(selectinload(EvaluationQuestion.options))
            .where(EvaluationQuestion.id == question.id)
        )
        return result.scalar_one()

    async def update_question(self, question_id: int, data: dict, options: list[dict] | None) -> EvaluationQuestion:
        question = await self.db.get(EvaluationQuestion, question_id)
        if question is None:
            raise EvaluationFormError("سوال موردنظر یافت نشد")
        for key, value in data.items():
            setattr(question, key, value)
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
        result = await self.db.execute(
            select(EvaluationQuestion)
            .options(selectinload(EvaluationQuestion.options))
            .where(EvaluationQuestion.id == question_id)
        )
        return result.scalar_one()

    async def delete_question(self, question_id: int) -> None:
        question = await self.db.get(EvaluationQuestion, question_id)
        if question is None:
            return
        await self.db.delete(question)
        await self.db.commit()
