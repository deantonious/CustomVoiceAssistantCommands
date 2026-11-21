"""Constants for Custom Voice Assistant Commands."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "voice_assistant_commands"

CONF_RESET_SENTENCES: Final = "reset_sentences"
CONF_RESET_RESPONSE: Final = "reset_response"

ATTR_CONVERSATION_ID: Final = "conversation_id"

SERVICE_RESET_CONVERSATION: Final = "reset_conversation"

# Sentences use Home Assistant's sentence trigger syntax:
#   [word]      optional word
#   (a|b)       alternatives
# Matching ignores case and punctuation, but NOT accents, so both spellings
# are listed where speech-to-text engines are inconsistent.
DEFAULT_RESET_SENTENCES: Final[list[str]] = [
    # Spanish
    "(olvida|borra|reinicia|resetea) [toda] la (conversación|conversacion)",
    "olvida [todo] lo que hemos hablado",
    "[empieza|empecemos] [una] nueva (conversación|conversacion)",
    "(empieza|empecemos|empezamos) de cero",
    # English
    "(forget|reset|clear) [the|this] conversation",
    "[start a] new conversation",
    "start over",
]

DEFAULT_RESET_RESPONSE: Final = "Conversación reiniciada."

# How long to wait for an in-progress turn to finish before giving up.
RESET_RETRY_INTERVAL: Final = 0.5
RESET_MAX_ATTEMPTS: Final = 40
