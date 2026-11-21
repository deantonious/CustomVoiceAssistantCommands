"""Reset conversation: clear the current conversation's history."""

from __future__ import annotations

from homeassistant.components.conversation import ConversationInput
from homeassistant.core import HomeAssistant

from ..const import SOURCE_VOICE
from ..conversation_reset import async_reset_conversation
from . import Command, CommandConfig


async def _handle(
    hass: HomeAssistant, config: CommandConfig, user_input: ConversationInput
) -> str:
    if user_input.conversation_id:
        # This runs inside the turn being reset, so wait for it to finish.
        async_reset_conversation(
            hass,
            user_input.conversation_id,
            source=SOURCE_VOICE,
            satellite_id=user_input.satellite_id,
            defer=True,
        )
    return config.response


COMMAND = Command(key="reset", handler=_handle)
