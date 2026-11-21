"""Tests for resetting conversations."""

from datetime import timedelta

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant import config_entries
from homeassistant.components import conversation
from homeassistant.components.conversation.chat_log import DATA_CHAT_LOGS
from homeassistant.core import Context, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import chat_session
from homeassistant.util import dt as dt_util

from custom_components.voice_assistant_commands.const import (
    CONF_RESET_RESPONSE,
    CONF_RESET_SENTENCES,
    DEFAULT_RESET_RESPONSE,
    DOMAIN,
)

pytestmark = pytest.mark.usefixtures("setup_conversation")


async def _setup(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


async def _say(hass: HomeAssistant, text: str, conversation_id: str | None = None):
    return await conversation.async_converse(
        hass, text, conversation_id, Context(), language="es"
    )


def _speech(result) -> str:
    return result.response.speech.get("plain", {}).get("speech", "")


def _sessions(hass: HomeAssistant) -> dict:
    return hass.data.get(chat_session.DATA_CHAT_SESSION) or {}


def _logs(hass: HomeAssistant) -> dict:
    return hass.data.get(DATA_CHAT_LOGS) or {}


async def _wait_for_deferred_reset(hass: HomeAssistant) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()


async def test_single_instance(hass: HomeAssistant) -> None:
    await _setup(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT


async def test_voice_reset_clears_history(hass: HomeAssistant) -> None:
    await _setup(hass)

    first = await _say(hass, "una frase que nadie entiende")
    conversation_id = first.conversation_id
    assert conversation_id in _sessions(hass)
    assert conversation_id in _logs(hass)

    # Punctuation and case are ignored.
    reset = await _say(hass, "¿Olvida la conversación?", conversation_id)
    assert _speech(reset) == DEFAULT_RESET_RESPONSE
    assert reset.conversation_id == conversation_id

    await _wait_for_deferred_reset(hass)
    assert conversation_id not in _sessions(hass)
    assert conversation_id not in _logs(hass)

    # A satellite that sends the old ID now gets a brand new, empty conversation.
    after = await _say(hass, "otra frase", conversation_id)
    assert after.conversation_id != conversation_id
    contents = _logs(hass)[after.conversation_id].content
    assert [c.content for c in contents if c.role == "user"] == ["otra frase"]


@pytest.mark.parametrize(
    "sentence",
    [
        "olvida la conversacion",
        "empieza de cero",
        "nueva conversación",
        "Start over.",
        "reset the conversation",
    ],
)
async def test_default_sentences(hass: HomeAssistant, sentence: str) -> None:
    await _setup(hass)
    first = await _say(hass, "hola que tal")
    result = await _say(hass, sentence, first.conversation_id)
    assert _speech(result) == DEFAULT_RESET_RESPONSE
    await _wait_for_deferred_reset(hass)
    assert first.conversation_id not in _sessions(hass)


async def test_other_sentences_untouched(hass: HomeAssistant) -> None:
    await _setup(hass)
    first = await _say(hass, "hola que tal")
    result = await _say(hass, "olvida la lista de la compra", first.conversation_id)
    assert _speech(result) != DEFAULT_RESET_RESPONSE
    await _wait_for_deferred_reset(hass)
    assert first.conversation_id in _sessions(hass)


async def test_action_reset_one_and_all(hass: HomeAssistant) -> None:
    await _setup(hass)
    a = (await _say(hass, "frase uno")).conversation_id
    b = (await _say(hass, "frase dos")).conversation_id

    resp = await hass.services.async_call(
        DOMAIN, "reset_conversation", {"conversation_id": a},
        blocking=True, return_response=True,
    )
    assert resp == {"reset": [a]}
    assert a not in _sessions(hass) and a not in _logs(hass)
    assert b in _sessions(hass)

    resp = await hass.services.async_call(
        DOMAIN, "reset_conversation", {"conversation_id": "unknown"},
        blocking=True, return_response=True,
    )
    assert resp == {"reset": []}

    resp = await hass.services.async_call(
        DOMAIN, "reset_conversation", {}, blocking=True, return_response=True
    )
    assert resp == {"reset": [b]}
    assert not _sessions(hass) and not _logs(hass)


async def test_busy_session_is_deferred(hass: HomeAssistant) -> None:
    await _setup(hass)
    cid = (await _say(hass, "frase")).conversation_id
    session = _sessions(hass)[cid]
    if not hasattr(session, "in_use"):
        pytest.skip("Home Assistant version without ChatSession.in_use")
    session.in_use += 1
    await hass.services.async_call(
        DOMAIN, "reset_conversation", {"conversation_id": cid}, blocking=True
    )
    assert cid in _sessions(hass)
    session.in_use -= 1
    await _wait_for_deferred_reset(hass)
    assert cid not in _sessions(hass)


async def test_options_flow(hass: HomeAssistant) -> None:
    entry = await _setup(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_RESET_SENTENCES: "borra todo.", CONF_RESET_RESPONSE: ""}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_RESET_SENTENCES: "invalid_sentence"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_RESET_SENTENCES: "borra todo\n\n(reinicia|reset) [ya]\n", CONF_RESET_RESPONSE: ""},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_RESET_SENTENCES] == ["borra todo", "(reinicia|reset) [ya]"]

    # Reloaded with the new sentences: the old default no longer matches and
    # the new one resets silently.
    cid = (await _say(hass, "hola")).conversation_id
    old = await _say(hass, "olvida la conversación", cid)
    assert _speech(old) != DEFAULT_RESET_RESPONSE
    new = await _say(hass, "reinicia ya", cid)
    assert _speech(new) == ""
    await _wait_for_deferred_reset(hass)
    assert cid not in _sessions(hass)


async def test_unload_removes_sentences(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    cid = (await _say(hass, "hola")).conversation_id
    result = await _say(hass, "olvida la conversación", cid)
    assert _speech(result) != DEFAULT_RESET_RESPONSE
