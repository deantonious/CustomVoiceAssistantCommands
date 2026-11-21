"""Reset Assist conversations (chat sessions and their LLM chat history).

Home Assistant keeps every Assist conversation in memory as a ``ChatSession``
in ``hass.data[DATA_CHAT_SESSION]``. Conversation agents register cleanup
callbacks on the session (the conversation component uses one to delete the
LLM chat log). Normally a session is only cleaned up after five minutes of
inactivity; this module runs that same cleanup on demand.

A session that is still serving a turn (``in_use > 0``) cannot be removed yet:
when the turn ends, Home Assistant writes it back into the session dict. Such
resets are retried until the turn has finished.

After a reset, the next request that carries the old conversation ID (for
example from a voice satellite) is given a fresh conversation ID by
``async_get_chat_session``, so it starts with an empty history.
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import chat_session
from homeassistant.helpers.event import async_call_later

from .const import RESET_MAX_ATTEMPTS, RESET_RETRY_INTERVAL

_LOGGER = logging.getLogger(__name__)


def _all_sessions(hass: HomeAssistant) -> dict[str, chat_session.ChatSession]:
    return hass.data.get(chat_session.DATA_CHAT_SESSION) or {}


@callback
def _remove_session(hass: HomeAssistant, conversation_id: str) -> None:
    """Remove an idle session and run its cleanup callbacks."""
    session = _all_sessions(hass).pop(conversation_id, None)
    if session is None:
        return
    try:
        session.async_cleanup()
    except Exception:  # noqa: BLE001 - never let a cleanup callback break the reset
        _LOGGER.exception("Error cleaning up conversation %s", conversation_id)
    _LOGGER.debug("Reset conversation %s", conversation_id)


def _is_busy(session: chat_session.ChatSession) -> bool:
    # ``in_use`` was added in Home Assistant 2026.11; older versions have no
    # way to tell, so callers that run inside a turn must pass ``defer=True``.
    return getattr(session, "in_use", 0) > 0


@callback
def async_reset_conversation(
    hass: HomeAssistant, conversation_id: str, *, defer: bool = False
) -> bool:
    """Reset one conversation.

    Returns True if the conversation exists. If it is busy (or ``defer`` is
    set because the caller runs inside the conversation's current turn), the
    reset happens once that turn has finished.
    """
    session = _all_sessions(hass).get(conversation_id)
    if session is None:
        return False

    if not defer and not _is_busy(session):
        _remove_session(hass, conversation_id)
        return True

    attempts = 0

    @callback
    def _retry(_now: object) -> None:
        nonlocal attempts
        attempts += 1
        current = _all_sessions(hass).get(conversation_id)
        if current is None:
            return
        if not _is_busy(current):
            _remove_session(hass, conversation_id)
        elif attempts < RESET_MAX_ATTEMPTS:
            async_call_later(hass, RESET_RETRY_INTERVAL, _retry)
        else:
            _LOGGER.warning(
                "Conversation %s stayed busy; it will expire normally", conversation_id
            )

    async_call_later(hass, RESET_RETRY_INTERVAL, _retry)
    return True


@callback
def async_reset_all_conversations(hass: HomeAssistant) -> list[str]:
    """Reset every conversation. Returns the affected conversation IDs."""
    conversation_ids = list(_all_sessions(hass))
    for conversation_id in conversation_ids:
        async_reset_conversation(hass, conversation_id)
    return conversation_ids
