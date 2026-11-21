"""Every access to Home Assistant internals lives here.

Assist Utils relies on a few things that are not a public API. Keeping them in
one module means a Home Assistant change only needs fixing in one place, and
``check()`` lets the integration raise a Repairs issue instead of failing
silently.

Internals used:
- ``homeassistant.helpers.chat_session``: the in-memory session dict and the
  session cleanup callbacks (which delete the LLM chat log).
- ``conversation.agent_manager.get_agent_manager().register_trigger``: the
  mechanism behind automation sentence triggers.
- ``AssistSatelliteEntity._conversation_id``: the conversation a satellite
  continues on its next wake.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import chat_session

# Features that depend on each internal; used to disable only what's broken.
FEATURE_RESET = "reset"
FEATURE_SENTENCES = "sentences"
FEATURE_SATELLITES = "satellites"

TriggerCallback = Callable[[Any, Any], Awaitable[str | None]]


def check() -> dict[str, str]:
    """Return ``{feature: missing internal}`` for everything that's unavailable."""
    missing: dict[str, str] = {}

    if not hasattr(chat_session, "DATA_CHAT_SESSION") or not hasattr(
        getattr(chat_session, "ChatSession", None), "async_cleanup"
    ):
        missing[FEATURE_RESET] = "helpers.chat_session (DATA_CHAT_SESSION / ChatSession.async_cleanup)"

    try:
        from homeassistant.components.conversation.agent_manager import (  # noqa: PLC0415
            AgentManager,
        )
    except ImportError:
        missing[FEATURE_SENTENCES] = "conversation.agent_manager"
    else:
        if not hasattr(AgentManager, "register_trigger"):
            missing[FEATURE_SENTENCES] = "conversation AgentManager.register_trigger"

    try:
        from homeassistant.components.assist_satellite import (  # noqa: PLC0415
            DATA_COMPONENT,  # noqa: F401
        )
        from homeassistant.components.assist_satellite.entity import (  # noqa: PLC0415
            AssistSatelliteEntity,
        )
    except ImportError:
        missing[FEATURE_SATELLITES] = "assist_satellite DATA_COMPONENT"
    else:
        if "_conversation_id" not in getattr(AssistSatelliteEntity, "__annotations__", {}) and not hasattr(
            AssistSatelliteEntity, "_conversation_id"
        ):
            missing[FEATURE_SATELLITES] = "AssistSatelliteEntity._conversation_id"

    return missing


# --- chat sessions -----------------------------------------------------------


def get_sessions(hass: HomeAssistant) -> dict[str, Any]:
    """Return the live session dict (mutable), or an empty dict."""
    return hass.data.get(chat_session.DATA_CHAT_SESSION) or {}


def is_busy(session: Any) -> bool:
    """Whether a session is serving a turn.

    ``in_use`` exists since Home Assistant 2026.11. Older versions can't tell,
    so callers that run inside a turn defer the reset instead.
    """
    return getattr(session, "in_use", 0) > 0


@callback
def remove_session(hass: HomeAssistant, conversation_id: str) -> bool:
    """Remove a session and run its cleanup callbacks."""
    session = get_sessions(hass).pop(conversation_id, None)
    if session is None:
        return False
    session.async_cleanup()
    return True


# --- sentence triggers ---------------------------------------------------------


@callback
def register_sentence_trigger(
    hass: HomeAssistant, sentences: list[str], trigger_callback: TriggerCallback
) -> CALLBACK_TYPE:
    """Register sentences handled before any conversation agent."""
    from homeassistant.components.conversation.agent_manager import (  # noqa: PLC0415
        get_agent_manager,
    )

    return get_agent_manager(hass).register_trigger(
        sentences=sentences, trigger_callback=trigger_callback
    )


# --- satellites ----------------------------------------------------------------


def _satellite_entity(hass: HomeAssistant, entity_id: str) -> Any | None:
    try:
        from homeassistant.components.assist_satellite import DATA_COMPONENT  # noqa: PLC0415
    except ImportError:
        return None
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        return None
    return component.get_entity(entity_id)


def satellite_conversation_id(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return the conversation a satellite will continue on its next wake."""
    entity = _satellite_entity(hass, entity_id)
    return getattr(entity, "_conversation_id", None) if entity else None


@callback
def clear_satellite_conversation_id(hass: HomeAssistant, entity_id: str) -> None:
    """Make a satellite start a new conversation on its next wake."""
    entity = _satellite_entity(hass, entity_id)
    if entity is not None and hasattr(entity, "_conversation_id"):
        entity._conversation_id = None  # noqa: SLF001


def satellite_entity_ids(hass: HomeAssistant) -> list[str]:
    """Return the entity IDs of all loaded Assist satellites."""
    try:
        from homeassistant.components.assist_satellite import DATA_COMPONENT  # noqa: PLC0415
    except ImportError:
        return []
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        return []
    return [entity.entity_id for entity in component.entities]
