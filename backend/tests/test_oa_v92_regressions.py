"""Focused no-database regression checks for office automation v9.2."""
import asyncio
import os

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.core.oa_html import plain_text, sanitize_html
# Full service imports need production dependencies. On stripped-down test
# hosts run the plain HTML regression separately (existing tests) and skip
# this integration-style test instead of changing application imports.
import pytest
pytest.importorskip("asyncpg")
pytest.importorskip("jdatetime")
if not all(os.getenv(key) for key in ("DATABASE_URL", "SECRET_KEY", "DB_CREDENTIALS_ENCRYPTION_KEY")):
    pytest.skip("Database settings not configured for service-model regression tests", allow_module_level=True)
from app.models.office_automation import OaAttachment, OaLetter, OaLetterVersion
from app.services.oa_approval_service import OaApprovalService


def test_empty_html_is_not_real_letter_content():
    assert not plain_text(sanitize_html('<p></p><p><br></p>')).strip()
    assert plain_text(sanitize_html('<p>متن معتبر</p>')).strip() == 'متن معتبر'


def test_approval_return_creates_editable_successor_without_overwriting_signed_version():
    previous = OaLetterVersion(
        id=7, letter_id=11, version_no=3, subject='موضوع اصلی',
        body_html='<p>متن بررسی‌شده</p>', paper_size='A4',
        template_version_id=4, content_hash='ab' * 32,
        status='submitted', created_by=19,
    )
    old_attachment = OaAttachment(
        id=30, letter_version_id=7, file_id=44,
        sort_order=2, description='ضمیمه', added_by=19,
    )
    letter = OaLetter(id=11, created_by=19, current_version_id=7, status='in_approval', row_version=8)
    additions = []

    async def flush():
        for record in additions:
            if isinstance(record, OaLetterVersion) and record.id is None:
                record.id = 8

    class FakeDB:
        def add(self, obj):
            additions.append(obj)

        flush = staticmethod(flush)

        async def get(self, model, pk):
            assert model is OaLetterVersion and pk == 7
            return previous

        async def execute(self, stmt):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [old_attachment]))

    service = OaApprovalService(FakeDB())
    service._copy_plan_to_next_round = AsyncMock()
    asyncio.run(service._back_to_draft(letter, []))

    successors = [r for r in additions if isinstance(r, OaLetterVersion)]
    attachments = [r for r in additions if isinstance(r, OaAttachment)]
    assert len(successors) == 1 and len(attachments) == 1
    assert previous.status == 'submitted' and previous.content_hash == 'ab' * 32
    assert successors[0].version_no == 4 and successors[0].status == 'editing'
    assert successors[0].body_html == previous.body_html and successors[0].id == 8
    assert attachments[0].file_id == old_attachment.file_id
    assert attachments[0].letter_version_id == 8
    assert letter.current_version_id == 8 and letter.row_version == 9 and letter.status == 'draft'
    service._copy_plan_to_next_round.assert_awaited_once()
