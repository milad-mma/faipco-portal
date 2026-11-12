"""v9.3.1 regression for the /automation/drafts/{id}/submit NameError.

Execute the actual submit() method body with an in-memory fake database so this
regression runs even when production-only asyncpg / jdatetime are unavailable.
The real PostgreSQL integration path still needs staging verification.
"""
from __future__ import annotations

import __future__
import ast
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import oa_approval_rules as arules
from app.core import oa_letter_rules as rules
from app.core.oa_version_snapshots import snapshot_approval_plan, snapshot_recipients


class FakeOaError(ValueError):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


class Field:
    def __eq__(self, value):
        return self

    def in_(self, value):
        return self

    def is_(self, value):
        return self


class Query:
    def where(self, *args):
        return self

    def with_for_update(self):
        return self

    def limit(self, *args):
        return self


class Result:
    def __init__(self, single=None, rows=None):
        self.single, self.rows = single, rows

    def scalar_one_or_none(self):
        return self.single

    def scalars(self):
        return SimpleNamespace(all=lambda: self.rows)


class FakeDB:
    def __init__(self, letter, eligible_ids):
        self.letter = letter
        self.eligible_ids = eligible_ids
        self.calls = 0
        self.delete = AsyncMock()
        self.flush = AsyncMock()
        self.add = MagicMock()

    async def execute(self, query):
        self.calls += 1
        if self.calls == 1:
            return Result(single=self.letter)
        if self.calls == 2:
            return Result(rows=self.eligible_ids)
        if self.calls == 3:
            return Result(single=999)  # already has creator access
        raise AssertionError(f"unexpected db.execute call {self.calls}")


def actual_submit():
    """Compile the *real* method from the project, not a duplicated mock algorithm."""
    path = Path(__file__).resolve().parents[1] / "app/services/oa_approval_service.py"
    source = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    service_class = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == "OaApprovalService")
    method = next(n for n in service_class.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "submit")
    env = {
        "select": lambda *args: Query(),
        "OaLetter": SimpleNamespace(id=Field()),
        "OaLetterAccess": SimpleNamespace(id=Field(), letter_id=Field(), employee_id=Field(), source=Field()),
        "Employee": SimpleNamespace(id=Field(), is_active=Field(), is_enabled=Field()),
        "OaApprovalStep": lambda **fields: SimpleNamespace(**fields),
        "OaCartableError": FakeOaError,
        "arules": arules,
        "rules": rules,
        "snapshot_recipients": snapshot_recipients,
        "snapshot_approval_plan": snapshot_approval_plan,
        "eligible_users_subquery": lambda: None,
        "_now": lambda: datetime(2026, 11, 12, tzinfo=timezone.utc),
    }
    module = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    code = compile(module, str(path), "exec", flags=__future__.annotations.compiler_flag)
    exec(code, env)
    return env["submit"]


def setup_case(*, steps=None, row_version=5, principal_id=None, status="draft"):
    author = SimpleNamespace(id=51)
    letter = SimpleNamespace(id=40, discarded_at=None, created_by=51, status=status,
                             row_version=row_version, approval_round=0, principal_employee_id=principal_id,
                             site_id=2, creator_employee_id=6)
    if steps is None:
        steps = [SimpleNamespace(approver_employee_id=77, approver_name_snapshot="تأییدکننده",
                                 approver_title_snapshot="مدیر", kind="approve", required=False,
                                 step_no=1, status="planned")]
    db = FakeDB(letter, eligible_ids={s.approver_employee_id for s in steps} | ({principal_id} if principal_id else set()))
    version = SimpleNamespace(subject="تست تأیید", body_html="<p>متن معتبر</p>",
                              paper_size="A4", template_version_id=None, status="editing",
                              content_hash=None, recipients_snapshot=None, approval_plan_snapshot=None)
    ctx = dict(v=version, recipients=[], att_files=[], me=SimpleNamespace(id=6))
    service = SimpleNamespace(
        db=db,
        _planned=AsyncMock(return_value=steps),
        _validate_for_send=AsyncMock(return_value=ctx),
        _numbering_error=AsyncMock(return_value=None),
        _round_steps=AsyncMock(return_value=steps),
        _activate=AsyncMock(),
        _commit=AsyncMock(),
        _snapshot=AsyncMock(return_value={"employee_id": principal_id, "name": "مدیر", "title": "سرپرست"}),
        files=SimpleNamespace(audit=MagicMock()),
    )
    return service, author, letter, version, steps


def test_one_approver_submit_writes_snapshots_and_commits():
    service, author, letter, version, steps = setup_case()
    assert asyncio.run(actual_submit()(service, 40, author, row_version=5)) == 40
    service._planned.assert_awaited_once_with(letter)
    service._activate.assert_awaited_once()
    service._commit.assert_awaited_once()
    assert letter.status == "in_approval" and letter.approval_round == 1 and letter.row_version == 6
    assert version.status == "submitted" and version.content_hash
    assert version.recipients_snapshot == []
    assert version.approval_plan_snapshot[0]["employee_id"] == 77
    assert steps[0].status == "pending"


def test_stale_draft_is_rejected_without_reading_approval_plan():
    service, author, letter, version, steps = setup_case()
    with pytest.raises(FakeOaError) as error:
        asyncio.run(actual_submit()(service, 40, author, row_version=4))
    assert error.value.status_code == 409
    service._planned.assert_not_awaited()
    service._commit.assert_not_awaited()
    assert letter.status == "draft"


def test_no_route_returns_user_facing_error_instead_of_nameerror():
    service, author, letter, version, steps = setup_case(steps=[])
    with pytest.raises(FakeOaError, match="مسیر تأیید خالی"):
        asyncio.run(actual_submit()(service, 40, author, row_version=5))
    service._commit.assert_not_awaited()


def test_principal_stage_deduplicated_and_snapshotted_as_final_signature():
    other = SimpleNamespace(approver_employee_id=77, approver_name_snapshot="کارمند",
                            approver_title_snapshot=None, kind="approve", required=False,
                            step_no=1, status="planned")
    manager = SimpleNamespace(approver_employee_id=91, approver_name_snapshot="مدیر",
                              approver_title_snapshot="مدیر", kind="sign", required=False,
                              step_no=2, status="planned")
    service, author, letter, version, steps = setup_case(steps=[other, manager], principal_id=91)
    assert asyncio.run(actual_submit()(service, 40, author, row_version=5)) == 40
    service.db.delete.assert_awaited_once_with(manager)
    assert other.step_no == 1 and steps == [other]
    assert len(version.approval_plan_snapshot) == 2
    assert version.approval_plan_snapshot[0]["employee_id"] == 77
    assert version.approval_plan_snapshot[1]["employee_id"] == 91
    assert version.approval_plan_snapshot[1]["kind"] == "sign"
    assert version.approval_plan_snapshot[1]["required"] is True
    service._commit.assert_awaited_once()


def test_repeat_submit_on_already_queued_approval_is_idempotent():
    service, author, letter, version, steps = setup_case(status="in_approval")
    assert asyncio.run(actual_submit()(service, 40, author, row_version=3)) == 40
    service._planned.assert_not_awaited()
    service._commit.assert_not_awaited()
