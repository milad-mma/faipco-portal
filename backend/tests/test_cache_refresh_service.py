"""Cache-refresh tests independent of a live PostgreSQL and app server."""
import importlib.util
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "app" / "services" / "cache_service.py"
spec = importlib.util.spec_from_file_location("faipco_cache_service_test", SRC)
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


def test_refresh_marker_changes_without_destroying_sw(tmp_path, monkeypatch):
    worker = tmp_path / "sw.js"
    worker.write_text("/* existing service worker */\n", encoding="utf-8")
    monkeypatch.setattr(service, "_FRONTEND_SW_PATH", worker)
    first = service.bump_app_cache_version()
    assert len(first) == 20
    assert service.deployed_cache_refresh() == first
    second = service.bump_app_cache_version()
    assert first != second
    assert service.deployed_cache_refresh() == second
    content = worker.read_text(encoding="utf-8")
    assert content.startswith("/* existing service worker */")
    assert content.count("// cache-bust:") == 1
    assert not list(tmp_path.glob("*.tmp"))


def test_read_legacy_marker_and_missing_sw(tmp_path, monkeypatch):
    worker = tmp_path / "sw.js"
    monkeypatch.setattr(service, "_FRONTEND_SW_PATH", worker)
    assert service.deployed_cache_refresh() is None
    worker.write_text("/* old */\n// cache-bust: 20261111110512\n", encoding="utf-8")
    assert service.deployed_cache_refresh() == "20261111110512"
