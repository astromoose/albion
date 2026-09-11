"""Notification integration via ntfy.sh."""

import logging

import httpx

from albion.config import NTFY_SERVER, NTFY_TOPIC

log = logging.getLogger(__name__)


async def notify_new_post(title: str, url: str, source_name: str) -> bool:
    """Send push notification for a new post via ntfy.sh.

    Returns True if notification was sent successfully.
    Requires ntfy app on iOS with subscription to the configured topic.
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{NTFY_SERVER}/{NTFY_TOPIC}",
                headers={
                    "Title": f"New post from {source_name}",
                    "Click": url,
                    "Tags": "newspaper,warhammer",
                    "Priority": "default",
                },
                content=title,
            )
            resp.raise_for_status()
            log.info("Notification sent: %s", title)
            return True
    except Exception as exc:
        log.warning("Failed to send notification: %s", exc)
        return False
