"""Run against SQLite with the real mapped FAIPCO models and real service queries.

Only a lightweight local DB is used. This explicitly does NOT replace a
PostgreSQL concurrency or end-to-end browser test.
"""
import asyncio
import sys
import types
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine, insert, update
from sqlalchemy.orm import DeclarativeBase, Session

session_mod = types.ModuleType('app.db.session')
class Base(DeclarativeBase):
    pass
session_mod.Base = Base
sys.modules['app.db.session'] = session_mod
sys.modules['jdatetime'] = types.ModuleType('jdatetime')

from app.models.office_automation import (
    OaLetter, OaApprovalStep, OaTask, OaAttachment, OaLetterVersion,
    OaLetterAccess,
)
from app.models.site import Site
from app.services.oa_cartable_service import OaCartableService
from app.services.oa_letter_service import OaLetterService

engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(
    engine,
    tables=[Site.__table__, OaLetter.__table__, OaLetterVersion.__table__,
            OaApprovalStep.__table__, OaTask.__table__, OaAttachment.__table__,
            OaLetterAccess.__table__],
)
now = datetime(2026, 11, 12, tzinfo=timezone.utc)
with engine.connect() as connection:
    connection.execute(insert(Site).values(id=1, name='Site', code='S'))
    for lid, status, created_by, creator_eid, approval_round, subject in [
        (1, 'draft', 11, 101, 1, 'Returned'),
        (2, 'draft', 11, 101, 0, 'Ordinary'),
        (3, 'draft', 11, 101, 1, 'Withdrawn'),
        (4, 'in_approval', 11, 101, 1, 'Submitted'),
        (5, 'draft', 22, 102, 1, 'Other'),
        (6, 'dispatched', 11, 101, 0, 'Active task'),
    ]:
        connection.execute(insert(OaLetter).values(
            id=lid, site_id=1, status=status, created_by=created_by,
            creator_employee_id=creator_eid, approval_round=approval_round,
            current_version_id=100+lid, subject=subject,
        ))
        connection.execute(insert(OaLetterVersion).values(
            id=100+lid, letter_id=lid, version_no=1, subject=subject,
        ))
    connection.execute(insert(OaApprovalStep).values([
        {'letter_id':1, 'round':1, 'step_no':1, 'kind':'approve',
         'approver_name_snapshot':'Reviewer', 'status':'returned', 'acted_at':now,
         'note':'Please correct'},
        {'letter_id':3, 'round':1, 'step_no':1, 'kind':'approve',
         'approver_name_snapshot':'Reviewer', 'status':'cancelled', 'acted_at':now, 'note':None},
        {'letter_id':5, 'round':1, 'step_no':1, 'kind':'approve',
         'approver_name_snapshot':'Reviewer', 'status':'returned', 'acted_at':now, 'note':None},
    ]))
    connection.execute(insert(OaTask).values(
        letter_id=6, kind='action', origin='delivery', status='open',
        assignee_employee_id=101, assignee_name_snapshot='Author',
    ))

    orm_session = Session(bind=connection)
    class FakeDB:
        async def execute(self, stmt):
            return orm_session.execute(stmt)

    async def me(_):
        return SimpleNamespace(id=101)
    s=OaCartableService.__new__(OaCartableService)
    s.db=FakeDB()
    s._me=me
    user=SimpleNamespace(id=11, employee_id=101)
    pending=asyncio.run(s.cartable(user,box='pending'))
    assert pending['total']==2, pending
    assert {it['subject'] for it in pending['items']} == {'Returned','Active task'},pending
    revision=next(x for x in pending['items'] if x['subject']=='Returned')
    assert revision['kind']=='revision' and revision['origin']=='revision',revision
    assert revision['instruction']=='Please correct',revision
    assert asyncio.run(s.counters(101))['pending']==2
    dashboard=asyncio.run(s.dashboard_items(user,limit=3))
    assert dashboard[0]['origin']=='revision' and dashboard[0]['letter_id']==1,dashboard
    letter_svc=OaLetterService.__new__(OaLetterService)
    letter_svc.db=FakeDB()
    drafts=asyncio.run(letter_svc.my_drafts(user))
    assert {x['subject'] for x in drafts}=={'Ordinary','Withdrawn','Submitted'},drafts
    assert asyncio.run(s.cartable(user,box='pending',q='Returned'))['total']==1
    assert asyncio.run(s.cartable(user,box='pending',q='Reviewer'))['total']==1

    # A second user's return never appears in this author's pending actions.
    assert 5 not in {it['letter_id'] for it in pending['items']}
    async def other_me(_):
        return SimpleNamespace(id=102)
    s._me=other_me
    other_pending=asyncio.run(s.cartable(SimpleNamespace(id=22, employee_id=102), box='pending'))
    assert other_pending['total']==1 and other_pending['items'][0]['letter_id']==5
    s._me=me

    # After submit, the return is no longer actionable, without creating new tasks.
    connection.execute(update(OaLetter).where(OaLetter.id==1).values(status='in_approval', approval_round=2))
    assert asyncio.run(s.cartable(user,box='pending'))['total']==1
    assert asyncio.run(s.counters(101))['pending']==1
    assert 'Returned' in {x['subject'] for x in asyncio.run(letter_svc.my_drafts(user))}
    print('OA return SQL integration: all assertions passed')
