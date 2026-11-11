"""Offline tests for fail-closed, complete frontend publication (no DB needed)."""
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "activate_frontend_release.py"
spec = importlib.util.spec_from_file_location("faipco_release_activation", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def make_release(path: Path, build: str, valid: bool = True):
    path.mkdir(parents=True)
    (path / "assets").mkdir()
    (path / "assets" / "index.js").write_text("console.log('ok')")
    (path / "index.html").write_text('<html><script src="/assets/index.js"></script></html>')
    (path / "version.json").write_text(json.dumps({"build": build}))
    if valid:
        (path / "sw.js").write_text("/* compiled Workbox */" + "x" * 300)


def test_incomplete_build_cannot_replace_live_site(tmp_path):
    frontend = tmp_path / "frontend"
    releases = frontend / "releases"
    old = frontend / "dist"
    make_release(old, "old-build")
    stage = releases / ".staging-new"
    make_release(stage, "new-build", valid=False)
    with pytest.raises(RuntimeError, match="Missing staged build artifact"):
        module.activate(tmp_path, stage)
    assert old.is_dir() and not old.is_symlink()
    assert json.loads((old / "version.json").read_text())["build"] == "old-build"


def test_activate_keeps_previous_assets_and_android_links(tmp_path):
    frontend = tmp_path / "frontend"
    releases = frontend / "releases"
    old = frontend / "dist"
    make_release(old, "old-build")
    (old / "assets" / "old-chunk.js").write_text("old")
    (old / ".well-known").mkdir()
    (old / ".well-known" / "assetlinks.json").write_text('real-assetlinks')
    stage = releases / ".staging-new"
    make_release(stage, "new-build")
    assert module.activate(tmp_path, stage) == "new-build"
    assert old.is_symlink()
    assert (old / "assets" / "old-chunk.js").read_text() == "old"
    assert (old / ".well-known" / "assetlinks.json").read_text() == "real-assetlinks"
    assert any(p.name.startswith("legacy-") for p in releases.iterdir())


def test_followup_deploy_is_atomic_symlink_replacement(tmp_path):
    frontend = tmp_path / "frontend"
    releases = frontend / "releases"
    stage = releases / ".staging-1"
    make_release(stage, "b1")
    module.activate(tmp_path, stage)
    old_symlink = (frontend / "dist").readlink()
    stage2 = releases / ".staging-2"
    make_release(stage2, "b2")
    module.activate(tmp_path, stage2)
    assert (frontend / "dist").is_symlink()
    assert (frontend / "dist").readlink() != old_symlink
    assert (releases / "build-b1").is_dir()
    assert (frontend / ".dist-next").exists() is False
