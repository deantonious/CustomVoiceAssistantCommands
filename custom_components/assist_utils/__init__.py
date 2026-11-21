"""Assist Utils: utilities for Home Assistant voice assistants.

- Voice commands handled before any conversation agent (including LLM agents):
  reset the conversation, silently cancel a false wake word.
- Buttons and an action to reset conversations, per satellite or all at once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

from hassil.recognize import RecognizeResult
import voluptuous as vol

from homeassistant.components.conversation import ConversationInput
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HA_VERSION, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers import (
    config_validation as cv,
    issue_registry as ir,
    service as service_helper,
)
from homeassistant.helpers.typing import ConfigType

from . import compat
from .commands import COMMANDS, CommandConfig, languages_of, load_defaults, resolve
from .const import (
    ATTR_CONVERSATION_ID,
    DOMAIN,
    ISSUE_INCOMPATIBLE,
    SERVICE_RESET_CONVERSATION,
    SOURCE_ACTION,
)
from .conversation_reset import (
    async_reset_all,
    async_reset_conversation,
    async_reset_satellite,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

RESET_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONVERSATION_ID): cv.string,
        **cv.ENTITY_SERVICE_FIELDS,
    }
)


@dataclass
class AssistUtilsData:
    """Runtime data of the config entry."""

    missing: dict[str, str]
    commands: dict[str, CommandConfig] = field(default_factory=dict)

    @property
    def satellites_supported(self) -> bool:
        return compat.FEATURE_SATELLITES not in self.missing

    @property
    def reset_supported(self) -> bool:
        return compat.FEATURE_RESET not in self.missing


type AssistUtilsConfigEntry = ConfigEntry[AssistUtilsData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions."""

    async def _handle_reset(call: ServiceCall) -> ServiceResponse:
        missing = compat.check()
        if compat.FEATURE_RESET in missing:
            return {"reset": []}

        reset: list[str] = []
        targeted = any(
            call.data.get(key) for key in ("entity_id", "device_id", "area_id", "floor_id", "label_id")
        )
        if conversation_id := call.data.get(ATTR_CONVERSATION_ID):
            if async_reset_conversation(hass, conversation_id, source=SOURCE_ACTION):
                reset.append(conversation_id)
        if targeted:
            entity_ids = await service_helper.async_extract_entity_ids(call)
            for entity_id in sorted(e for e in entity_ids if e.startswith("assist_satellite.")):
                reset += async_reset_satellite(
                    hass,
                    entity_id,
                    source=SOURCE_ACTION,
                    satellites_supported=compat.FEATURE_SATELLITES not in missing,
                )
        if not conversation_id and not targeted:
            reset = async_reset_all(hass, source=SOURCE_ACTION)
        return {"reset": sorted(set(reset))}

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_CONVERSATION,
        _handle_reset,
        schema=RESET_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


def _update_repair_issue(hass: HomeAssistant, missing: dict[str, str]) -> None:
    if not missing:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_INCOMPATIBLE)
        return
    _LOGGER.warning(
        "Home Assistant %s changed internals Assist Utils relies on: %s",
        HA_VERSION,
        ", ".join(missing.values()),
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_INCOMPATIBLE,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_INCOMPATIBLE,
        translation_placeholders={
            "ha_version": HA_VERSION,
            "missing": "\n".join(f"- {name}" for name in missing.values()),
        },
        learn_more_url="https://github.com/deantonious/CustomVoiceAssistantCommands/issues",
    )


async def async_setup_entry(hass: HomeAssistant, entry: AssistUtilsConfigEntry) -> bool:
    """Set up voice commands and buttons."""
    missing = compat.check()
    _update_repair_issue(hass, missing)

    defaults = await hass.async_add_executor_job(load_defaults, languages_of(entry.options))
    data = AssistUtilsData(missing=missing, commands=resolve(entry.options, defaults))
    entry.runtime_data = data

    if compat.FEATURE_SENTENCES not in missing:
        for command in COMMANDS:
            config = data.commands[command.key]
            if not config.enabled or not config.sentences:
                continue
            entry.async_on_unload(
                compat.register_sentence_trigger(
                    hass, config.sentences, _make_trigger(hass, command.handler, config)
                )
            )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


def _make_trigger(hass: HomeAssistant, handler, config: CommandConfig):
    async def _on_sentence(user_input: ConversationInput, result: RecognizeResult) -> str | None:
        return await handler(hass, config, user_input)

    return _on_sentence


async def async_unload_entry(hass: HomeAssistant, entry: AssistUtilsConfigEntry) -> bool:
    """Unload buttons; voice commands are removed by async_on_unload."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: AssistUtilsConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
