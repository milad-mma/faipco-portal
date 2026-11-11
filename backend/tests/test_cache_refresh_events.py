"""Offline tests for the separate cache-refresh fanout channel."""
import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "app" / "services" / "release_events.py"


def load_module(monkeypatch):
    monkeypatch.syspath_prepend(str(SRC.parents[2]))
    asyncpg_stub = types.ModuleType("asyncpg")
    config_stub = types.ModuleType("app.core.config")
    config_stub.get_settings = lambda: types.SimpleNamespace(DATABASE_URL="postgresql://fake")
    monkeypatch.setitem(sys.modules, "asyncpg", asyncpg_stub)
    monkeypatch.setitem(sys.modules, "app.core.config", config_stub)
    spec = importlib.util.spec_from_file_location("faipco_test_release_bus", SRC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, asyncpg_stub


def test_cache_refresh_broadcast_is_separate_from_release(monkeypatch):
    module, _ = load_module(monkeypatch)
    monkeypatch.setattr(module, "deployed_cache_refresh", lambda: "20261111120101111111")
    monkeypatch.setattr(module, "deployed_build", lambda: "build-current")
    bus = module.ReleaseBus()
    queue = bus.subscribe()
    bus._on_notification(None, 0, module.CACHE_CHANNEL, "20261111120101111111")
    assert queue.get_nowait() == {"type": "portal.cache_refresh", "stamp": "20261111120101111111"}
    bus._on_notification(None, 0, module.CHANNEL, "build-current")
    assert queue.get_nowait() == {"type": "portal.release", "build": "build-current"}
    bus._on_notification(None, 0, module.CACHE_CHANNEL, "old-stamp")
    assert queue.empty()


def test_cache_refresh_published_only_if_live_marker_matches(monkeypatch):
    module, asyncpg_stub = load_module(monkeypatch)
    stamp = "20261111120101111111"
    monkeypatch.setattr(module, "deployed_cache_refresh", lambda: stamp)
    calls = []

    class Connection:
        async def execute(self, query, channel, payload):
            calls.append((query, channel, payload))

        async def close(self):
            calls.append("closed")

    async def connect(**_kwargs):
        calls.append("connected")
        return Connection()

    asyncpg_stub.connect = connect
    monkeypatch.setattr(module, "postgres_dsn", lambda: "postgresql://fake")
    asyncio.run(module.publish_cache_refresh(stamp))
    assert calls[1] == ("SELECT pg_notify($1, $2)", module.CACHE_CHANNEL, stamp)
    assert calls[-1] == "closed"
    with pytest.raises(RuntimeError):
        asyncio.run(module.publish_cache_refresh("stale"))
