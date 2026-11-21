"""Constants for Assist Utils."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "assist_utils"
NAME: Final = "Assist Utils"

# Options
CONF_LANGUAGES: Final = "languages"
CONF_SATELLITE_BUTTONS: Final = "satellite_buttons"
CONF_RESET_ALL_BUTTON: Final = "reset_all_button"
CONF_COMMANDS: Final = "commands"
# Form field (not stored): the list of enabled features.
CONF_FEATURES: Final = "features"
# Features that aren't voice commands; voice commands are features too, keyed
# by their command key (see commands.COMMANDS).
ENTITY_FEATURES: Final = (CONF_SATELLITE_BUTTONS, CONF_RESET_ALL_BUTTON)
CONF_ENABLED: Final = "enabled"
CONF_SENTENCES: Final = "sentences"
CONF_RESPONSE: Final = "response"
CONF_ALSO_RESET: Final = "also_reset"

# Languages that ship default sentences (one YAML file each in sentences/).
SUPPORTED_LANGUAGES: Final = ("en", "es")
FALLBACK_LANGUAGE: Final = "en"

# Actions
SERVICE_RESET_CONVERSATION: Final = "reset_conversation"
ATTR_CONVERSATION_ID: Final = "conversation_id"

# Events
EVENT_CONVERSATION_RESET: Final = f"{DOMAIN}_conversation_reset"
SOURCE_VOICE: Final = "voice"
SOURCE_BUTTON: Final = "button"
SOURCE_ACTION: Final = "action"

# Repairs
ISSUE_INCOMPATIBLE: Final = "incompatible_ha"

# Waiting for an in-progress turn to finish before resetting it.
RESET_RETRY_INTERVAL: Final = 0.5
RESET_MAX_ATTEMPTS: Final = 40
