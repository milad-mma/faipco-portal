"""Small, process-safe deployment event bus for the portal's PWA.

Only deployment version IDs are broadcast, never private HR data.  Each uvicorn
worker keeps ONE PostgreSQL LISTEN connection, not one database connection per
browser.  A reconnecting browser immediately receives the latest published
version from the live dist/version.json (recovering missed notifications).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

import asyncpg
from sqlalchemy.engine import make_url

from app.core.config import get_settings

log = logging.getLogger("faipco.releases")
CHANNEL = "faipco_frontend_published"
BUILD_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,96}$")
LIVE_VERSION_FILE = Path(__file__).resolve().parents[3] / "frontend" / "dist" / "version.json"


def deployed_build(version_file: Path = LIVE_VERSION_FILE) -> str | None:
    """Never announce a staging build: read only the actively served release."""
    try:
        data = json.loads(version_file.read_text(encoding="utf-8"))
        build = data.get("build")
        if isinstance(build, str) and BUILD_PATTERN.fullmatch(build):
            return build
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return None


def postgres_dsn() -> str:
    return make_url(get_settings().DATABASE_URL).set(drivername="postgresql").render_as_string(hide_password=False)


class ReleaseBus:
    def __init__(self):
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        self._subscribers.discard(queue)

    def broadcast(self, build: str) -> None:
        if not BUILD_PATTERN.fullmatch(build):
            return
        # Ensure no event from an uncommitted/aborted staging build escapes.
        if deployed_build() != build:
            return
        for queue in tuple(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(build)

    def _on_notification(self, _connection, _pid, _channel, payload: str) -> None:
        self.broadcast(payload)

    async def _listen(self) -> None:
        retry = 2
        while not self._stop.is_set():
            connection = None
            terminated = asyncio.Event()
            try:
                connection = await asyncpg.connect(dsn=postgres_dsn(), timeout=10)
                connection.add_termination_listener(lambda _conn: terminated.set())
                await connection.add_listener(CHANNEL, self._on_notification)
                # Replay the live deployment to clients who connected while
                # this worker's LISTEN connection was temporarily down.
                latest = deployed_build()
                if latest:
                    self.broadcast(latest)
                retry = 2
                stop_wait = asyncio.create_task(self._stop.wait())
                term_wait = asyncio.create_task(terminated.wait())
                try:
                    await asyncio.wait({stop_wait, term_wait}, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    for pending in (stop_wait, term_wait):
                        pending.cancel()
                    await asyncio.gather(stop_wait, term_wait, return_exceptions=True)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # Network/database outage must not stop the application.
                log.warning("Release notification listener unavailable: %s", type(exc).__name__)
            finally:
                if connection and not connection.is_closed():
                    try:
                        await connection.close(timeout=2)
                    except Exception:
                        pass
            if not self._stop.is_set():
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=retry)
                except asyncio.TimeoutError:
                    pass
                retry = min(retry * 2, 30)

    def start(self) -> None:
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(self._listen(), name="release-event-listener")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            task, self._task = self._task, None
            try:
                await asyncio.wait_for(task, timeout=4)
            except asyncio.TimeoutError:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


release_bus = ReleaseBus()
