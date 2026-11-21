"""Voice commands handled before any conversation agent.

To add a command:
1. Create ``commands/<key>.py`` exposing ``COMMAND = Command(...)``.
2. Add it to ``COMMANDS`` below.
3. Add ``commands.<key>`` (sentences and response) to every file in
   ``sentences/``, and its option texts to ``strings.json`` / translations.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from homeassistant.components.conversation import ConversationInput
from homeassistant.core import HomeAssistant
from homeassistant.util.yaml import load_yaml_dict

from ..const import (
    CONF_COMMANDS,
    CONF_ENABLED,
    CONF_LANGUAGES,
    CONF_RESPONSE,
    CONF_SENTENCES,
    FALLBACK_LANGUAGE,
)

SENTENCES_DIR = Path(__file__).parent.parent / "sentences"


@dataclass(frozen=True)
class CommandConfig:
    """Effective settings of one command (options merged with defaults)."""

    enabled: bool
    sentences: list[str]
    response: str
    extras: Mapping[str, Any] = field(default_factory=dict)


Handler = Callable[[HomeAssistant, CommandConfig, ConversationInput], Awaitable[str]]


@dataclass(frozen=True)
class Command:
    """A voice command."""

    key: str
    handler: Handler
    default_enabled: bool = True
    # Extra boolean options shown in the command's options step: {key: default}.
    extra_options: Mapping[str, bool] = field(default_factory=dict)


def _commands() -> tuple[Command, ...]:
    from .cancel import COMMAND as CANCEL  # noqa: PLC0415
    from .reset import COMMAND as RESET  # noqa: PLC0415

    return (RESET, CANCEL)


COMMANDS: tuple[Command, ...] = _commands()
COMMANDS_BY_KEY: dict[str, Command] = {c.key: c for c in COMMANDS}


def load_defaults(languages: list[str]) -> dict[str, dict[str, Any]]:
    """Load default sentences/responses for the given languages (blocking I/O).

    Sentences of all languages are combined; the response comes from the first
    language that defines one.
    """
    result: dict[str, dict[str, Any]] = {
        c.key: {CONF_SENTENCES: [], CONF_RESPONSE: None} for c in COMMANDS
    }
    for language in languages or [FALLBACK_LANGUAGE]:
        path = SENTENCES_DIR / f"{language}.yaml"
        if not path.is_file():
            continue
        data = load_yaml_dict(str(path)).get("commands", {})
        for key, values in data.items():
            if key not in result:
                continue
            for sentence in values.get(CONF_SENTENCES, []):
                if sentence not in result[key][CONF_SENTENCES]:
                    result[key][CONF_SENTENCES].append(sentence)
            if result[key][CONF_RESPONSE] is None and CONF_RESPONSE in values:
                result[key][CONF_RESPONSE] = values[CONF_RESPONSE] or ""
    for values in result.values():
        if values[CONF_RESPONSE] is None:
            values[CONF_RESPONSE] = ""
    return result


def resolve(
    options: Mapping[str, Any], defaults: dict[str, dict[str, Any]]
) -> dict[str, CommandConfig]:
    """Merge stored options with defaults. ``None`` means "use the default"."""
    stored = options.get(CONF_COMMANDS, {})
    configs: dict[str, CommandConfig] = {}
    for command in COMMANDS:
        opts = stored.get(command.key, {})
        sentences = opts.get(CONF_SENTENCES)
        response = opts.get(CONF_RESPONSE)
        configs[command.key] = CommandConfig(
            enabled=opts.get(CONF_ENABLED, command.default_enabled),
            sentences=list(sentences) if sentences else defaults[command.key][CONF_SENTENCES],
            response=response if response is not None else defaults[command.key][CONF_RESPONSE],
            extras={k: opts.get(k, default) for k, default in command.extra_options.items()},
        )
    return configs


def languages_of(options: Mapping[str, Any]) -> list[str]:
    """Return the configured languages."""
    return list(options.get(CONF_LANGUAGES) or [FALLBACK_LANGUAGE])
