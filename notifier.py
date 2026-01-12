"""
Push notifications via Pushover

Sends notifications when notes are created or when errors occur.
Optional - if PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY are not set,
notifications are silently skipped.
"""
import os
from urllib.parse import quote

import httpx

from logger import get_logger

logger = get_logger(__name__)

def _get_config():
    """Get Pushover config at runtime (not module load)"""
    return {
        "token": os.getenv("PUSHOVER_APP_TOKEN"),
        "user": os.getenv("PUSHOVER_USER_KEY"),
        "vault": os.getenv("OBSIDIAN_VAULT_NAME", "Obsidian Vault")
    }


async def notify_success(title: str, note_path: str):
    """Notify when a note is successfully created"""
    config = _get_config()
    if not _is_configured(config):
        return

    # Build Obsidian deep link
    encoded_path = quote(note_path, safe="")
    encoded_vault = quote(config["vault"], safe="")
    obsidian_url = f"obsidian://open?vault={encoded_vault}&file={encoded_path}"

    await _send(
        config=config,
        title=f"📝 {title}",
        message=f"Saved to {note_path}",
        priority=0,
        url=obsidian_url
    )


async def notify_failure(error_type: str, message: str, url: str = None):
    """Notify when note creation fails"""
    config = _get_config()
    if not _is_configured(config):
        return

    await _send(
        config=config,
        title=f"⚠️ {error_type}",
        message=message[:256],  # Pushover message limit
        priority=1,  # High priority
        url=url
    )


def _is_configured(config: dict) -> bool:
    """Check if Pushover is configured"""
    if not config["token"] or not config["user"]:
        logger.debug("Pushover not configured, skipping notification")
        return False
    return True


async def _send(config: dict, title: str, message: str, priority: int = 0, url: str = None):
    """Send notification to Pushover"""
    try:
        data = {
            "token": config["token"],
            "user": config["user"],
            "title": title,
            "message": message,
            "priority": priority,
        }
        if url:
            data["url"] = url
            data["url_title"] = "Open in Obsidian"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.pushover.net/1/messages.json",
                data=data,
                timeout=10.0
            )
            response.raise_for_status()
        logger.info(f"Pushover notification sent: {title}")
    except httpx.TimeoutException:
        logger.warning(f"Pushover notification timed out: {title}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Pushover API error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"Pushover notification failed: {e}")
