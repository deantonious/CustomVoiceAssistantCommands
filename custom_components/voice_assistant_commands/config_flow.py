"""Config flow for Custom Voice Assistant Commands."""

from __future__ import annotations

from typing import Any

from hassil.parse_expression import parse_sentence
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

from .const import (
    CONF_RESET_RESPONSE,
    CONF_RESET_SENTENCES,
    DEFAULT_RESET_RESPONSE,
    DEFAULT_RESET_SENTENCES,
    DOMAIN,
)

_PUNCTUATION = set(".,;:!?¿¡\"")


def _parse_sentences(text: str) -> list[str]:
    """Split one-sentence-per-line text and validate the syntax."""
    sentences = [line.strip() for line in text.splitlines() if line.strip()]
    for sentence in sentences:
        if _PUNCTUATION & set(sentence):
            raise ValueError(sentence)
        try:
            parse_sentence(sentence)
        except Exception as err:  # noqa: BLE001 - hassil raises several types
            raise ValueError(sentence) from err
    return sentences


def _options_schema(sentences: list[str], response: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_RESET_SENTENCES, description={"suggested_value": "\n".join(sentences)}
            ): TextSelector(TextSelectorConfig(multiline=True)),
            vol.Optional(
                CONF_RESET_RESPONSE, description={"suggested_value": response}
            ): TextSelector(),
        }
    )


class VoiceAssistantCommandsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up the integration (single instance)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is None:
            return self.async_show_form(step_id="user")
        return self.async_create_entry(
            title="Custom Voice Assistant Commands",
            data={},
            options={
                CONF_RESET_SENTENCES: DEFAULT_RESET_SENTENCES,
                CONF_RESET_RESPONSE: DEFAULT_RESET_RESPONSE,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return VoiceAssistantCommandsOptionsFlow()


class VoiceAssistantCommandsOptionsFlow(OptionsFlow):
    """Edit the voice command sentences and response."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        options = self.config_entry.options
        sentences = options.get(CONF_RESET_SENTENCES, DEFAULT_RESET_SENTENCES)
        response = options.get(CONF_RESET_RESPONSE, DEFAULT_RESET_RESPONSE)

        if user_input is not None:
            response = user_input.get(CONF_RESET_RESPONSE, "") or ""
            try:
                sentences = _parse_sentences(user_input.get(CONF_RESET_SENTENCES, "") or "")
            except ValueError as err:
                errors[CONF_RESET_SENTENCES] = "invalid_sentence"
                placeholders["sentence"] = str(err)
            else:
                return self.async_create_entry(
                    data={CONF_RESET_SENTENCES: sentences, CONF_RESET_RESPONSE: response}
                )

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(sentences, response),
            errors=errors,
            description_placeholders=placeholders or {"sentence": ""},
        )
