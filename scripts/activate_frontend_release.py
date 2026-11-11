"""Validate a fully-built Vite release, then switch frontend/dist atomically.

First upgrade of a legacy plain dist directory involves a one-time directory
migration; subsequent upgrades are atomic symlink replacements.  No deletion of
the old release or its static assets occurs during the switch.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

BUILD_RE = re.compile(r"^[A-Za-z0-9._-]{1,96}$")
REF_RE = re.compile(r'''(?:src|href)=["'](/?assets/[^"']+)["']''')


def validate(staged: Path) -> str:
    for filename in ("index.html", "sw.js", "version.json"):
        if not (staged / filename).is_file():
            raise RuntimeError(f"Missing staged build artifact: {filename}")
    data = json.loads((staged / "version.json").read_text(encoding="utf-8"))
    build = data.get("build")
    if not isinstance(build, str) or not BUILD_RE.fullmatch(build):
        raise RuntimeError("Missing/invalid staging build ID")
    sw = (staged / "sw.js").read_text(encoding="utf-8")
    if "__WB_MANIFEST" in sw or len(sw) < 250:
        raise RuntimeError("Service Worker was not compiled/precached")
    html = (staged / "index.html").read_text(encoding="utf-8")
    for ref in REF_RE.findall(html):
        path = staged / ref.lstrip("/")
        if not path.is_file():
            raise RuntimeError(f"Built index.html points to a missing file: {ref}")
    if not list((staged / "assets").glob("*.js")):
        raise RuntimeError("Staging assets have no JS chunks")
    return build


def activate(project_root: Path, staged_path: Path) -> str:
    frontend = project_root / "frontend"
    releases = frontend / "releases"
    live = frontend / "dist"
    releases.mkdir(parents=True, exist_ok=True)
    staged = staged_path.resolve(strict=True)
    if not staged.is_dir() or staged.parent != releases:
        raise RuntimeError("Staging path must be directly under frontend/releases")
    build = validate(staged)

    # Preserve TWA digital asset links and legacy chunks that may still be used
    # by an open tab from an older release.  Never discard during activation.
    if live.exists():
        old_well_known = live / ".well-known"
        if old_well_known.is_dir():
            shutil.copytree(old_well_known, staged / ".well-known", dirs_exist_ok=True)
        old_assets = live / "assets"
        if old_assets.is_dir():
            new_assets = staged / "assets"
            new_assets.mkdir(exist_ok=True)
            for old_file in old_assets.iterdir():
                if old_file.is_file() and not (new_assets / old_file.name).exists():
                    # preserve metadata + don't replace Vite's new hashed chunks
                    shutil.copy2(old_file, new_assets / old_file.name)

    # Validate again after carryover and then publish to a permanent release.
    validate(staged)
    final = releases / f"build-{build}"
    if final.exists():
        raise RuntimeError(f"Duplicate release directory: {final}")
    staged.rename(final)
    next_link = frontend / ".dist-next"
    if next_link.exists() or next_link.is_symlink():
        next_link.unlink()
    next_link.symlink_to(final.relative_to(frontend), target_is_directory=True)
    old_directory = None
    try:
        if live.is_dir() and not live.is_symlink():
            # One-time migration from pre-v7 deployments. The original build is
            # kept intact and can be restored if this first switch fails.
            old_directory = releases / f"legacy-{int(time.time())}"
            live.rename(old_directory)
        os.replace(next_link, live)
    except Exception:
        if next_link.is_symlink():
            next_link.unlink()
        if old_directory and not live.exists() and old_directory.exists():
            old_directory.rename(live)
        raise
    return build


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: activate_frontend_release.py PROJECT_ROOT STAGING_DIR")
    build = activate(Path(sys.argv[1]).resolve(), Path(sys.argv[2]))
    print("[FAIPCO] Active frontend build:", build)
