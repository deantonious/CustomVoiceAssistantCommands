"""Config and options flow for Assist Utils."""

from __future__ import annotations

from typing import Any

from hassil.parse_expression import parse_sentence
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .commands import COMMANDS_BY_KEY, languages_of, load_defaults
from .const import (
    CONF_COMMANDS,
    CONF_ENABLED,
    CONF_FEATURES,
    CONF_LANGUAGES,
    CONF_RESPONSE,
    CONF_SENTENCES,
    DOMAIN,
    ENTITY_FEATURES,
    FALLBACK_LANGUAGE,
    NAME,
    SUPPORTED_LANGUAGES,
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


def _languages_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=list(SUPPORTED_LANGUAGES),
            multiple=True,
            mode=SelectSelectorMode.LIST,
            translation_key=CONF_LANGUAGES,
        )
    )


def _default_language(hass_language: str) -> str:
    base = hass_language.split("-")[0].lower()
    return base if base in SUPPORTED_LANGUAGES else FALLBACK_LANGUAGE


# --- features ------------------------------------------------------------------
# Every voice command and every optional entity is a feature that can be
# switched on or off from one list.


def _all_features() -> list[str]:
    return [*COMMANDS_BY_KEY, *ENTITY_FEATURES]


def _features_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=_all_features(),
            multiple=True,
            mode=SelectSelectorMode.LIST,
            translation_key=CONF_FEATURES,
        )
    )


def _enabled_features(options: dict[str, Any]) -> list[str]:
    commands = options.get(CONF_COMMANDS, {})
    enabled = [
        key
        for key, command in COMMANDS_BY_KEY.items()
        if commands.get(key, {}).get(CONF_ENABLED, command.default_enabled)
    ]
    enabled += [feature for feature in ENTITY_FEATURES if options.get(feature, True)]
    return enabled


def _apply_features(options: dict[str, Any], selected: list[str]) -> dict[str, Any]:
    commands = {key: dict(value) for key, value in options.get(CONF_COMMANDS, {}).items()}
    for key in COMMANDS_BY_KEY:
        commands.setdefault(key, {})[CONF_ENABLED] = key in selected
    return {
        **options,
        CONF_COMMANDS: commands,
        **{feature: feature in selected for feature in ENTITY_FEATURES},
    }


class AssistUtilsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up Assist Utils (single instance)."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        if user_input is not None:
            languages = user_input.get(CONF_LANGUAGES) or []
            if not languages:
                errors[CONF_LANGUAGES] = "no_language"
            else:
                return self.async_create_entry(
                    title=NAME,
                    data={},
                    options=_apply_features(
                        {CONF_LANGUAGES: languages, CONF_COMMANDS: {}},
                        user_input.get(CONF_FEATURES) or [],
                    ),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LANGUAGES,
                        default=[_default_language(self.hass.config.language)],
                    ): _languages_selector(),
                    vol.Optional(CONF_FEATURES, default=_all_features()): _features_selector(),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AssistUtilsOptionsFlow()


class AssistUtilsOptionsFlow(OptionsFlow):
    """Options: general settings plus one step per voice command."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init", menu_options=["features", "languages", *COMMANDS_BY_KEY]
        )

    def _save(self, **changes: Any) -> ConfigFlowResult:
        return self.async_create_entry(data={**self.config_entry.options, **changes})

    async def async_step_features(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = dict(self.config_entry.options)
        if user_input is not None:
            return self.async_create_entry(
                data=_apply_features(options, user_input.get(CONF_FEATURES) or [])
            )
        return self.async_show_form(
            step_id="features",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_FEATURES, default=_enabled_features(options)
                    ): _features_selector()
                }
            ),
        )

    async def async_step_languages(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = self.config_entry.options
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_LANGUAGES):
                errors[CONF_LANGUAGES] = "no_language"
            else:
                return self._save(**{CONF_LANGUAGES: user_input[CONF_LANGUAGES]})
        return self.async_show_form(
            step_id="languages",
            data_schema=vol.Schema(
                {vol.Required(CONF_LANGUAGES, default=languages_of(options)): _languages_selector()}
            ),
            errors=errors,
        )

    async def async_step_reset(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._async_command_step("reset", user_input)

    async def async_step_cancel(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._async_command_step("cancel", user_input)

    async def _async_command_step(
        self, key: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        command = COMMANDS_BY_KEY[key]
        options = self.config_entry.options
        stored: dict[str, Any] = dict(options.get(CONF_COMMANDS, {}).get(key, {}))
        defaults = (
            await self.hass.async_add_executor_job(load_defaults, languages_of(options))
        )[key]
        errors: dict[str, str] = {}
        placeholders = {"sentence": ""}

        if user_input is not None:
            response = user_input.get(CONF_RESPONSE) or ""
            try:
                sentences = _parse_sentences(user_input.get(CONF_SENTENCES) or "")
            except ValueError as err:
                errors[CONF_SENTENCES] = "invalid_sentence"
                placeholders["sentence"] = str(err)
            else:
                new = {
                    # On/off is set on the Features page.
                    CONF_ENABLED: stored.get(CONF_ENABLED, command.default_enabled),
                    # Store None when equal to the defaults, so they keep
                    # following the selected languages.
                    CONF_SENTENCES: None
                    if not sentences or sentences == defaults[CONF_SENTENCES]
                    else sentences,
                    CONF_RESPONSE: None if response == defaults[CONF_RESPONSE] else response,
                    **{k: user_input.get(k, d) for k, d in command.extra_options.items()},
                }
                return self._save(
                    **{CONF_COMMANDS: {**options.get(CONF_COMMANDS, {}), key: new}}
                )

        sentences = stored.get(CONF_SENTENCES) or defaults[CONF_SENTENCES]
        response = stored.get(CONF_RESPONSE)
        if response is None:
            response = defaults[CONF_RESPONSE]
        schema: dict[Any, Any] = {
            vol.Optional(
                CONF_SENTENCES, description={"suggested_value": "\n".join(sentences)}
            ): TextSelector(TextSelectorConfig(multiline=True)),
            vol.Optional(CONF_RESPONSE, description={"suggested_value": response}): TextSelector(),
        }
        for extra, default in command.extra_options.items():
            schema[vol.Required(extra, default=stored.get(extra, default))] = BooleanSelector()

        return self.async_show_form(
            step_id=key,
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders=placeholders,
        )
