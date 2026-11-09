"""Regression tests: fast pending-count and coalesced monthly attendance source reads.

No Kara/SQL Server connection is required; dependency boundaries are mocked.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.core.leave_request_rules import can_act_on, managers_of_substitute
from app.services import leave_request_service as leave_mod
from app.services import monthly_attendance_service as attendance


def test_pending_count_uses_same_substitute_rule_as_cartable(monkeypatch):
    """Count must not expose/overcount requests the current approver cannot act on."""
    codes = {12: 20}
    rows = [
        {"CurEmpNo": 20, "EmpNo": 31},  # directly assigned
        {"CurEmpNo": 12, "EmpNo": 45},  # delegated to 20
        {"CurEmpNo": 12, "EmpNo": 20},  # own request via delegation: forbidden
    ]
    async def check():
        svc = leave_mod.LeaveRequestService(None)
        mapping = object()
        conn = object()
        svc._get_mapping_and_connection = AsyncMock(return_value=(mapping, conn))
        monkeypatch.setattr(leave_mod, '_to_personnel_code_int', lambda _: 20)
        monkeypatch.setattr(leave_mod, 'active_substitute_codes', AsyncMock(return_value=codes))
        received = []
        def read(conn_arg, mapping_arg, selected_codes):
            assert (conn_arg, mapping_arg) == (conn, mapping)
            received.extend(selected_codes)
            return rows
        monkeypatch.setattr(leave_mod, '_select_pending_assignments_sync', read)
        result = await svc.get_pending_count_for_approver(SimpleNamespace(site_id=1))
        assert result == sum(1 for r in rows if can_act_on(20, r['CurEmpNo'], r['EmpNo'], codes))
        assert sorted(received) == sorted([20, *managers_of_substitute(20, codes)])
    asyncio.run(check())


def test_pending_count_missing_module_returns_zero():
    async def check():
        svc = leave_mod.LeaveRequestService(None)
        svc._get_mapping_and_connection = AsyncMock(side_effect=leave_mod.LeaveRequestError('not configured'))
        assert await svc.get_pending_count_for_approver(SimpleNamespace(site_id=1)) == 0
    asyncio.run(check())


def test_monthly_source_reads_coalesce_and_cache():
    async def check():
        attendance._cache.clear()
        attendance._inflight_sources.clear()
        calls = 0
        ready = asyncio.Event()
        release = asyncio.Event()
        async def load():
            nonlocal calls
            calls += 1
            ready.set()
            await release.wait()
            return ([{'AttendanceDate': 14050801}], set(), {})
        key = ('unit-test',)
        first = asyncio.create_task(attendance._get_month_sources_cached(key, load))
        second = asyncio.create_task(attendance._get_month_sources_cached(key, load))
        await ready.wait()
        assert calls == 1
        first.cancel()
        try:
            await first
        except asyncio.CancelledError:
            pass
        release.set()
        expected = await second
        assert await attendance._get_month_sources_cached(key, load) == expected
        assert calls == 1
        assert not attendance._inflight_sources
        attendance._cache.clear()
    asyncio.run(check())


def test_monthly_source_read_error_is_not_cached():
    async def check():
        attendance._cache.clear()
        attendance._inflight_sources.clear()
        key = ('failed-unit-test',)
        calls = 0
        async def load():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ValueError('transient source failure')
            return ('raw', 'holidays', 'overlay')
        try:
            await attendance._get_month_sources_cached(key, load)
            assert False, 'expected failure'
        except ValueError:
            pass
        assert await attendance._get_month_sources_cached(key, load) == ('raw', 'holidays', 'overlay')
        assert calls == 2
        assert not attendance._inflight_sources
        attendance._cache.clear()
    asyncio.run(check())
