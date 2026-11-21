"""Silent cancel: end a false wake word without calling the conversation agent."""

from __future__ import annotations

from homeassistant.components.conversation import ConversationInput
from homeassistant.core import HomeAssistant

from ..const import CONF_ALSO_RESET, SOURCE_VOICE
from ..conversation_reset import async_reset_conversation
from . import Command, CommandConfig


async def _handle(
    hass: HomeAssistant, config: CommandConfig, user_input: ConversationInput
) -> str:
    if config.extras.get(CONF_ALSO_RESET) and user_input.conversation_id:
        async_reset_conversation(
            hass,
            user_input.conversation_id,
            source=SOURCE_VOICE,
            satellite_id=user_input.satellite_id,
            defer=True,
        )
    # An empty response means nothing is spoken.
    return config.response


COMMAND = Command(key="cancel", handler=_handle, extra_options={CONF_ALSO_RESET: False})
