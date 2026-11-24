"""Environment-specific Android Digital Asset Links (no DB dependencies)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

PRODUCTION_PACKAGE = "ir.faipco.portal"
STAGING_PACKAGE = "ir.faipco.portal.test"
STAGING_HOST = "portal-test.faipco.ir"


def android_package_for_url(frontend_url: str) -> str:
    """Use the configured public URL, never the incoming Host header.

    Keep the historical production package for other deployments; only the
    exact staging hostname selects the test APK.
    """
    host = (urlsplit(frontend_url).hostname or "").lower().rstrip(".")
    return STAGING_PACKAGE if host == STAGING_HOST else PRODUCTION_PACKAGE


def assetlinks_json(fingerprint: str, frontend_url: str) -> str:
    return json.dumps(
        [{
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": android_package_for_url(frontend_url),
                "sha256_cert_fingerprints": [fingerprint] if fingerprint else [],
            },
        }],
        indent=2,
    )


def write_assetlinks_file(path: Path, fingerprint: str, frontend_url: str) -> bool:
    """Publish a complete JSON file atomically, including through dist symlinks."""
    if not fingerprint or not path.parent.parent.is_dir():
        return False
    content = assetlinks_json(fingerprint, frontend_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    fd, temporary = tempfile.mkstemp(prefix=".assetlinks-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            # mkstemp defaults to 0600; Nginx must be able to read the result.
            os.fchmod(stream.fileno(), 0o644)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True
