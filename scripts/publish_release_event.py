"""Announce an already *activated* frontend release to every FastAPI worker.

Run at the END of successful install.sh, not during npm build.  LISTEN/NOTIFY is
non-durable by design; websocket subscriptions replay the live version on join.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Installer invokes this file via backend/.venv/bin/python with CWD project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.release_events import CHANNEL, deployed_build, postgres_dsn


async def main() -> None:
    import asyncpg

    build = deployed_build()
    if not build:
        raise RuntimeError("No valid deployed frontend/dist/version.json: deployment event withheld")
    conn = await asyncpg.connect(dsn=postgres_dsn(), timeout=10)
    try:
        await conn.execute("SELECT pg_notify($1, $2)", CHANNEL, build)
    finally:
        await conn.close()
    print("[FAIPCO] Published committed frontend build:", build)


if __name__ == "__main__":
    asyncio.run(main())
