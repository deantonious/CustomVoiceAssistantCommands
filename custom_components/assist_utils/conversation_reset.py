"""Reset Assist conversations (chat sessions and their LLM chat history).

Home Assistant keeps every Assist conversation in memory as a chat session.
The conversation component registers a cleanup callback on each session that
deletes its LLM chat log; normally that only runs after five minutes of
inactivity. This module runs the same cleanup on demand.

A session that is serving a turn can't be removed yet: when the turn ends,
Home Assistant writes it back. Those resets are retried until the turn is over.
After a reset, a request carrying the old conversation ID is given a new one,
so it starts with an empty history.
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from . import compat
from .const import (
    EVENT_CONVERSATION_RESET,
    RESET_MAX_ATTEMPTS,
    RESET_RETRY_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@callback
def _remove(
    hass: HomeAssistant, conversation_id: str, source: str, satellite_id: str | None
) -> None:
    try:
        removed = compat.remove_session(hass, conversation_id)
    except Exception:  # noqa: BLE001 - a cleanup callback must not break the reset
        _LOGGER.exception("Error cleaning up conversation %s", conversation_id)
        removed = True
    if removed:
        _LOGGER.debug("Reset conversation %s (%s)", conversation_id, source)
        hass.bus.async_fire(
            EVENT_CONVERSATION_RESET,
            {
                "conversation_id": conversation_id,
                "satellite_id": satellite_id,
                "source": source,
            },
        )


@callback
def async_reset_conversation(
    hass: HomeAssistant,
    conversation_id: str,
    *,
    source: str,
    satellite_id: str | None = None,
    defer: bool = False,
) -> bool:
    """Reset one conversation.

    Returns True if the conversation exists. If it is busy, or ``defer`` is set
    because the caller runs inside the conversation's current turn, the reset
    happens once that turn has finished.
    """
    session = compat.get_sessions(hass).get(conversation_id)
    if session is None:
        return False

    if not defer and not compat.is_busy(session):
        _remove(hass, conversation_id, source, satellite_id)
        return True

    attempts = 0

    @callback
    def _retry(_now: object) -> None:
        nonlocal attempts
        attempts += 1
        current = compat.get_sessions(hass).get(conversation_id)
        if current is None:
            return
        if not compat.is_busy(current):
            _remove(hass, conversation_id, source, satellite_id)
        elif attempts < RESET_MAX_ATTEMPTS:
            async_call_later(hass, RESET_RETRY_INTERVAL, _retry)
        else:
            _LOGGER.warning(
                "Conversation %s stayed busy; it will expire normally", conversation_id
            )

    async_call_later(hass, RESET_RETRY_INTERVAL, _retry)
    return True


@callback
def async_reset_all(hass: HomeAssistant, *, source: str) -> list[str]:
    """Reset every conversation. Returns the affected conversation IDs."""
    conversation_ids = list(compat.get_sessions(hass))
    for conversation_id in conversation_ids:
        async_reset_conversation(hass, conversation_id, source=source)
    for entity_id in compat.satellite_entity_ids(hass):
        compat.clear_satellite_conversation_id(hass, entity_id)
    return conversation_ids


@callback
def async_reset_satellite(
    hass: HomeAssistant, entity_id: str, *, source: str, satellites_supported: bool = True
) -> list[str]:
    """Reset the conversation a satellite would continue on its next wake.

    Falls back to resetting everything when satellite support is unavailable
    (see the Repairs issue).
    """
    if not satellites_supported:
        return async_reset_all(hass, source=source)

    conversation_id = compat.satellite_conversation_id(hass, entity_id)
    compat.clear_satellite_conversation_id(hass, entity_id)
    if conversation_id and async_reset_conversation(
        hass, conversation_id, source=source, satellite_id=entity_id
    ):
        return [conversation_id]
    return []
