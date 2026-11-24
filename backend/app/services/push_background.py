"""Queue ordinary Web Push durably without waiting for a network provider."""
from collections.abc import Iterable
import logging

from app.services.push_dispatch import enqueue_generic_push

logger = logging.getLogger(__name__)


async def schedule_push(user_ids: Iterable[int], url: str, body: str | None = None,
                        priority: str = "normal", notice_type: str = "normal") -> None:
    try:
        await enqueue_generic_push(user_ids, url, body, priority, notice_type)
    except Exception as exc:
        # These callers have already committed their domain event. The error
        # is explicit in logs but must not masquerade as a failed domain action.
        logger.error("Push durable enqueue failed: %s", type(exc).__name__)
