"""Regression tests for the production and staging TWA associations."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.android_assetlinks import (
    android_package_for_url,
    assetlinks_json,
    write_assetlinks_file,
)

FP = ":".join(["AB"] * 32)
PROD = "ir.faipco.portal"
STAGING = "ir.faipco.portal.test"


@pytest.mark.parametrize("url,package", [
    ("https://portal.faipco.ir", PROD),
    ("https://portal-test.faipco.ir", STAGING),
    ("https://PORTAL-TEST.FAIPCO.IR.:443/", STAGING),
    ("https://portal-test.faipco.ir.example.com", PROD),
    ("http://localhost:3000", PROD),
])
def test_package_mapping(url, package):
    assert android_package_for_url(url) == package
    assert json.loads(assetlinks_json(FP, url)) == [{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {"namespace": "android_app", "package_name": package,
                   "sha256_cert_fingerprints": [FP]},
    }]


def test_generation_is_idempotent_and_keeps_registered_fingerprint(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    path = dist / ".well-known" / "assetlinks.json"
    assert write_assetlinks_file(path, FP, "https://portal.faipco.ir")
    assert write_assetlinks_file(path, FP, "https://portal-test.faipco.ir")
    assert not write_assetlinks_file(path, FP, "https://portal-test.faipco.ir")
    assert json.loads(path.read_text())[0]["target"] == {
        "namespace": "android_app", "package_name": STAGING,
        "sha256_cert_fingerprints": [FP],
    }
    assert path.stat().st_mode & 0o777 == 0o644
    assert list(path.parent.iterdir()) == [path]


def test_no_fingerprint_or_no_build_does_not_create_fake_trust(tmp_path):
    path = tmp_path / "dist" / ".well-known" / "assetlinks.json"
    assert not write_assetlinks_file(path, FP, "https://portal-test.faipco.ir")
    path.parent.parent.mkdir()
    assert not write_assetlinks_file(path, "", "https://portal-test.faipco.ir")
    assert not path.exists()


@pytest.mark.parametrize("url,package", [
    ("https://portal.faipco.ir", PROD),
    ("https://portal-test.faipco.ir", STAGING),
])
def test_install_release_preserves_and_regenerates_association(tmp_path, url, package):
    # Exercise the real release activation script, including its symlink.
    script = Path(__file__).resolve().parents[2] / "scripts" / "activate_frontend_release.py"
    spec = importlib.util.spec_from_file_location("release_activation", script)
    activation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(activation)
    frontend = tmp_path / "frontend"
    live = frontend / "dist"
    live.mkdir(parents=True)
    path = live / ".well-known" / "assetlinks.json"
    # Reproduce the old backend hard-coding the production package.
    write_assetlinks_file(path, FP, "https://portal.faipco.ir")
    # Installer restarts the backend before activation, then calls the
    # branding / assetlinks sync hook again against the new live release.
    write_assetlinks_file(path, FP, url)
    for build in ("one", "two"):
        stage = frontend / "releases" / (".staging-" + build)
        (stage / "assets").mkdir(parents=True)
        (stage / "assets" / "index.js").write_text("console.log('ok')")
        (stage / "index.html").write_text('<script src="/assets/index.js"></script>')
        (stage / "sw.js").write_text("x" * 300)
        (stage / "version.json").write_text(json.dumps({"build": build}))
        (stage / ".well-known").mkdir()
        (stage / ".well-known" / "assetlinks.json").write_text("[]")
        assert activation.activate(tmp_path, stage) == build
        assert live.is_symlink()
        write_assetlinks_file(path, FP, url)
        assert json.loads(path.read_text())[0]["target"]["package_name"] == package
        assert json.loads(path.read_text())[0]["target"]["sha256_cert_fingerprints"] == [FP]


def test_mobile_service_reads_configured_url_not_process_hostname(monkeypatch, tmp_path):
    pytest.importorskip("asyncpg")
    # The models create an engine at import time; use dummy settings only.
    # No connection is made to this URL by this test.
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@127.0.0.1:1/test")
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    monkeypatch.setenv("DB_CREDENTIALS_ENCRYPTION_KEY", "6M8FuWqloQBI_11SZcX5zGXwU-L0wZesFCQ_HLX6DMY=")
    from app.services import mobile_app_service as service

    dist = tmp_path / "dist"
    dist.mkdir()
    path = dist / ".well-known" / "assetlinks.json"
    monkeypatch.setattr(service, "ASSETLINKS_PATH", path)
    settings = SimpleNamespace(FRONTEND_URL="https://portal-test.faipco.ir")
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    assert service.write_assetlinks(FP)
    assert json.loads(path.read_text())[0]["target"]["package_name"] == STAGING
    settings.FRONTEND_URL = "https://portal.faipco.ir"
    assert service.write_assetlinks(FP)
    assert json.loads(path.read_text())[0]["target"]["package_name"] == PROD


@pytest.mark.parametrize("url,package", [
    ("https://portal.faipco.ir", PROD),
    ("https://portal-test.faipco.ir", STAGING),
])
def test_environment_is_read_from_existing_dotenv(tmp_path, monkeypatch, url, package):
    from app.core.config import Settings

    monkeypatch.delenv("FRONTEND_URL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(f"FRONTEND_URL={url}\nUPDATE_CHANNEL=tag\n")
    settings = Settings(_env_file=env_file,
                        DATABASE_URL="postgresql+asyncpg://unused:unused@127.0.0.1:1/unused",
                        SECRET_KEY="x" * 40,
                        DB_CREDENTIALS_ENCRYPTION_KEY="6M8FuWqloQBI_11SZcX5zGXwU-L0wZesFCQ_HLX6DMY=")
    assert settings.FRONTEND_URL == url
    assert android_package_for_url(settings.FRONTEND_URL) == package
