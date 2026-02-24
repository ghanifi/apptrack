import logging
import time
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

_build_attempts: dict[str, list[float]] = defaultdict(list)
_sync_attempts: dict[str, list[float]] = defaultdict(list)
_webhook_attempts: dict[str, list[float]] = defaultdict(list)

BUILD_SPAM_WINDOW = 300
BUILD_SPAM_LIMIT = 15
SYNC_SPAM_WINDOW = 60
SYNC_SPAM_LIMIT = 10
WEBHOOK_SPAM_WINDOW = 60
WEBHOOK_SPAM_LIMIT = 100


def _clean_window(attempts: list[float], window: int) -> list[float]:
    cutoff = time.time() - window
    return [t for t in attempts if t > cutoff]


def check_build_spam(user_id: str) -> Optional[str]:
    _build_attempts[user_id] = _clean_window(_build_attempts[user_id], BUILD_SPAM_WINDOW)
    if len(_build_attempts[user_id]) >= BUILD_SPAM_LIMIT:
        logger.warning("Build spam detected for user %s (%d attempts in %ds)", user_id, len(_build_attempts[user_id]), BUILD_SPAM_WINDOW)
        return f"Too many build requests ({BUILD_SPAM_LIMIT} in {BUILD_SPAM_WINDOW}s). Please wait."
    _build_attempts[user_id].append(time.time())
    return None


def check_sync_spam(user_id: str) -> Optional[str]:
    _sync_attempts[user_id] = _clean_window(_sync_attempts[user_id], SYNC_SPAM_WINDOW)
    if len(_sync_attempts[user_id]) >= SYNC_SPAM_LIMIT:
        logger.warning("Repo sync spam detected for user %s", user_id)
        return f"Too many sync requests ({SYNC_SPAM_LIMIT} in {SYNC_SPAM_WINDOW}s). Please wait."
    _sync_attempts[user_id].append(time.time())
    return None


def check_webhook_spam(source: str) -> Optional[str]:
    _webhook_attempts[source] = _clean_window(_webhook_attempts[source], WEBHOOK_SPAM_WINDOW)
    if len(_webhook_attempts[source]) >= WEBHOOK_SPAM_LIMIT:
        logger.warning("Webhook spam detected from source %s", source)
        return f"Too many webhook requests from {source}."
    _webhook_attempts[source].append(time.time())
    return None
