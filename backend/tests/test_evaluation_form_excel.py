"""بارگذاری نمونهٔ واقعی، کنترل دسترسی و جلوگیری از ساخت فرم ناقص."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import evaluation_forms as routes
from app.core.evaluation_rules import validate_form_weights
from app.models.evaluation_content import EvaluationCategory, EvaluationForm, EvaluationQuestion, EvaluationQuestionOption
from app.services.evaluation_form_excel import TYPES, combine_form_files, read_form_excel

SAMPLE = Path(__file__).resolve().parents[2] / "frontend/public/templates/evaluation-form-sample.xlsx"


def test_upload_sample_and_reject_invalid_row_or_scope(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    for model in (EvaluationForm, EvaluationCategory, EvaluationQuestion, EvaluationQuestionOption):
        model.__table__.create(engine)
    specimen = SAMPLE.read_bytes()
    with Session(engine, expire_on_commit=False) as session:
        app = FastAPI()
        app.include_router(routes.router, prefix="/forms")
        app.dependency_overrides[routes.get_db] = lambda: SimpleNamespace(
            add=session.add, commit=AsyncMock(side_effect=session.commit))
        app.dependency_overrides[routes.get_current_user] = lambda: SimpleNamespace(is_superuser=False, id=21)
        monkeypatch.setattr("app.core.site_permission_deps.get_sites_with_permission", AsyncMock(return_value=None))
        client = TestClient(app)

        def upload(content):
            return client.post("/forms/import-excel", data={"title": "فرم نمونه"},
                               files={"file": ("sample.xlsx", content)})

        response = upload(specimen)
        assert response.status_code == 200, response.text
        form = session.get(EvaluationForm, response.json()["id"])
        assert form.status.value == "draft" and form.created_by_user_id == 21
        assert len(form.categories) == 2
        assert [len(c.questions) for c in form.categories] == [3, 4]
        assert form.categories[0].questions[0].options[-1].score == 5
        assert not validate_form_weights([dict(title=c.title, weight=float(c.weight), is_active=c.is_active,
            questions=[dict(text=q.text, weight=float(q.weight), is_active=q.is_active) for q in c.questions])
            for c in form.categories])

        book = load_workbook(BytesIO(specimen))
        book["سؤال‌ها"]["D8"] = "امتیازی"
        out = BytesIO()
        book.save(out)
        response = upload(out.getvalue())
        assert response.status_code == 400 and "ردیف 8" in response.json()["detail"]
        # Upload all seven delivered workbooks to the same draft using the actual HTTP endpoint.
        parts = [("file", (kind + ".xlsx", (SAMPLE.parent / f"evaluation-{kind}.xlsx").read_bytes()))
                 for kind in TYPES.values()]
        response = client.post("/forms/import-excel", data={"title": "ارزیابی ترکیبی"}, files=parts)
        assert response.status_code == 200, response.text
        session.expire_all()
        groups = session.get(EvaluationForm, response.json()["id"]).categories
        assert [(g.title, g.weight, len(g.questions)) for g in groups] == [
            ("کیفیت کار", 50, 14), ("همکاری", 30, 7), ("انضباط کاری", 20, 7)]
        assert [q.question_type.value for q in groups[1].questions] == list(TYPES.values())
        assert all(sum(q.weight for q in g.questions) == 100 for g in groups)
        assert [(o.label, o.score) for o in groups[0].questions[7].options] == [("بله", 0), ("خیر", 5)]
        for kind in TYPES.values():
            contents = (SAMPLE.parent / f"evaluation-{kind}.xlsx").read_bytes()
            categories = combine_form_files([read_form_excel(contents)])
            assert [len(c["questions"]) for c in categories] == [2, 1, 1]
            assert all(q.question_type == kind for c in categories for q in c["questions"])
        book = load_workbook(BytesIO(parts[0][1][1]))
        book.active["E3"] = None
        out = BytesIO()
        book.save(out)
        broken = [parts[-1], ("file", ("broken.xlsx", out.getvalue()))]
        response = client.post("/forms/import-excel", data={"title": "نمونه"}, files=broken)
        assert response.status_code == 400 and "broken.xlsx" in response.text and "ردیف 3" in response.text
        def with_groups(part, rows):
            workbook = load_workbook(BytesIO(part[1][1]))
            sheet = workbook.active
            example = [cell.value for cell in sheet[2]]
            sheet.delete_rows(2, sheet.max_row)
            for title, weight in rows:
                sheet.append([title, weight, *example[2:]])
            stream = BytesIO()
            workbook.save(stream)
            return ("file", (part[1][0], stream.getvalue()))

        first = with_groups(parts[0], [("کیفیت", 60), ("همکاری", 40)])
        second = with_groups(parts[-1], [("کیفیت", 60)])
        response = client.post("/forms/import-excel", data={"title": "دو دسته"}, files=[first, second])
        assert response.status_code == 200, response.text
        session.expire_all()
        groups = session.get(EvaluationForm, response.json()["id"]).categories
        assert [(c.title, c.weight, len(c.questions)) for c in groups] == [("کیفیت", 60, 2), ("همکاری", 40, 1)]
        assert [q.weight for q in groups[0].questions] == [50, 50]
        assert groups[1].questions[0].weight == 100
        conflict = with_groups(parts[-1], [("کیفیت", 50)])
        response = client.post("/forms/import-excel", data={"title": "تعارض"}, files=[first, conflict])
        assert response.status_code == 400 and "date.xlsx" in response.text and "ردیف 2" in response.text
        monkeypatch.setattr("app.core.site_permission_deps.get_sites_with_permission", AsyncMock(return_value={1}))
        assert upload(specimen).status_code == 403
        assert session.scalar(select(func.count(EvaluationForm.id))) == 3
