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
        imported = session.get(EvaluationForm, response.json()["id"]).categories[0].questions
        assert [q.question_type.value for q in imported] == list(TYPES.values())
        assert sum(q.weight for q in imported) == 100
        assert [(o.label, o.score) for o in imported[3].options] == [("بله", 5), ("خیر", 0)]
        for kind in TYPES.values():
            contents = (SAMPLE.parent / f"evaluation-{kind}.xlsx").read_bytes()
            question = combine_form_files([read_form_excel(contents)])[0]["questions"][0]
            assert question.weight == 100 and question.question_type == kind
        book = load_workbook(BytesIO(parts[0][1][1]))
        book.active["C3"] = None
        out = BytesIO()
        book.save(out)
        broken = [parts[-1], ("file", ("broken.xlsx", out.getvalue()))]
        response = client.post("/forms/import-excel", data={"title": "نمونه"}, files=broken)
        assert response.status_code == 400 and "broken.xlsx" in response.text and "ردیف 3" in response.text
        monkeypatch.setattr("app.core.site_permission_deps.get_sites_with_permission", AsyncMock(return_value={1}))
        assert upload(specimen).status_code == 403
        assert session.scalar(select(func.count(EvaluationForm.id))) == 2
