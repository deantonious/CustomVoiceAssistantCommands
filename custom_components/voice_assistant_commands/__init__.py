"""Custom Voice Assistant Commands.

Adds voice commands to Assist that are handled before any conversation agent
(including LLM agents), plus matching actions for automations and scripts.

Commands:
- Reset conversation: "olvida la conversación", "start over", ... clears the
  current conversation's history so the next request starts fresh.
"""

from __future__ import annotations

import logging

from hassil.recognize import RecognizeResult
import voluptuous as vol

from homeassistant.components.conversation import ConversationInput
from homeassistant.components.conversation.agent_manager import get_agent_manager
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CONVERSATION_ID,
    CONF_RESET_RESPONSE,
    CONF_RESET_SENTENCES,
    DEFAULT_RESET_RESPONSE,
    DEFAULT_RESET_SENTENCES,
    DOMAIN,
    SERVICE_RESET_CONVERSATION,
)
from .conversation_reset import async_reset_all_conversations, async_reset_conversation

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

RESET_SCHEMA = vol.Schema({vol.Optional(ATTR_CONVERSATION_ID): cv.string})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions."""

    async def _handle_reset(call: ServiceCall) -> ServiceResponse:
        if conversation_id := call.data.get(ATTR_CONVERSATION_ID):
            found = async_reset_conversation(hass, conversation_id)
            reset = [conversation_id] if found else []
        else:
            reset = async_reset_all_conversations(hass)
        return {"reset": reset}

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_CONVERSATION,
        _handle_reset,
        schema=RESET_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Register the voice commands."""
    sentences: list[str] = entry.options.get(CONF_RESET_SENTENCES, DEFAULT_RESET_SENTENCES)
    response: str = entry.options.get(CONF_RESET_RESPONSE, DEFAULT_RESET_RESPONSE)

    async def _on_reset_sentence(
        user_input: ConversationInput, result: RecognizeResult
    ) -> str | None:
        # The turn that matched is still running, so the reset is deferred
        # until Home Assistant has finished it.
        if user_input.conversation_id:
            async_reset_conversation(hass, user_input.conversation_id, defer=True)
        return response

    if sentences:
        entry.async_on_unload(
            get_agent_manager(hass).register_trigger(
                sentences=sentences, trigger_callback=_on_reset_sentence
            )
        )

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unregister the voice commands."""
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
