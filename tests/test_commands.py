"""Voice command and action tests."""

from types import SimpleNamespace

import pytest
from pytest_homeassistant_custom_component.common import async_capture_events

from homeassistant.core import HomeAssistant

from custom_components.assist_utils.const import DOMAIN, EVENT_CONVERSATION_RESET

from .conftest import logs, say, sessions, setup_integration, speech, wait_deferred


async def test_voice_reset_clears_history(hass: HomeAssistant) -> None:
    await setup_integration(hass)
    events = async_capture_events(hass, EVENT_CONVERSATION_RESET)

    cid = (await say(hass, "una frase que nadie entiende")).conversation_id
    assert cid in sessions(hass) and cid in logs(hass)

    result = await say(hass, "¿Olvida la conversación?", cid)
    assert speech(result) == "Conversación reiniciada."
    await wait_deferred(hass)
    assert cid not in sessions(hass) and cid not in logs(hass)
    assert [e.data for e in events] == [
        {"conversation_id": cid, "satellite_id": None, "source": "voice"}
    ]

    after = await say(hass, "otra frase", cid)
    assert after.conversation_id != cid
    user_texts = [c.content for c in logs(hass)[after.conversation_id].content if c.role == "user"]
    assert user_texts == ["otra frase"]


@pytest.mark.parametrize(
    ("languages", "sentence", "language"),
    [
        (["es"], "olvida la conversacion", "es"),
        (["es"], "empieza de cero", "es"),
        (["es"], "nueva conversación", "es"),
        (["en"], "Start over.", "en"),
        (["en"], "reset the conversation", "en"),
        (["es", "en"], "start over", "en"),
    ],
)
async def test_default_reset_phrases(hass: HomeAssistant, languages, sentence, language) -> None:
    await setup_integration(hass, languages)
    cid = (await say(hass, "hola", language=language)).conversation_id
    result = await say(hass, sentence, cid, language=language)
    assert speech(result) in ("Conversación reiniciada.", "Conversation reset.")
    await wait_deferred(hass)
    assert cid not in sessions(hass)


@pytest.mark.parametrize("sentence", ["Para.", "cancelalo", "Cancélalo.", "no era a ti", "falsa alarma", "nada"])
async def test_cancel_is_silent_and_keeps_history(hass: HomeAssistant, sentence: str) -> None:
    await setup_integration(hass)
    cid = (await say(hass, "hola")).conversation_id
    result = await say(hass, sentence, cid)
    assert speech(result) == ""
    await wait_deferred(hass)
    assert cid in sessions(hass)


async def test_cancel_also_reset(hass: HomeAssistant) -> None:
    entry = await setup_integration(hass)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "commands": {"cancel": {"also_reset": True}}}
    )
    await hass.async_block_till_done()
    cid = (await say(hass, "hola")).conversation_id
    assert speech(await say(hass, "para", cid)) == ""
    await wait_deferred(hass)
    assert cid not in sessions(hass)


async def test_unrelated_sentences_untouched(hass: HomeAssistant) -> None:
    await setup_integration(hass)
    cid = (await say(hass, "hola")).conversation_id
    result = await say(hass, "para la música del salón", cid)
    assert speech(result) != ""
    await wait_deferred(hass)
    assert cid in sessions(hass)


async def test_action_by_id_satellite_and_all(hass: HomeAssistant, fake_satellites) -> None:
    await setup_integration(hass)
    events = async_capture_events(hass, EVENT_CONVERSATION_RESET)
    a = (await say(hass, "frase uno")).conversation_id
    b = (await say(hass, "frase dos")).conversation_id
    c = (await say(hass, "frase tres")).conversation_id
    fake_satellites["assist_satellite.kitchen"] = SimpleNamespace(_conversation_id=b)

    async def reset(data):
        return await hass.services.async_call(
            DOMAIN, "reset_conversation", data, blocking=True, return_response=True
        )

    assert await reset({"conversation_id": a}) == {"reset": [a]}
    assert a not in sessions(hass) and b in sessions(hass)
    assert await reset({"conversation_id": "unknown"}) == {"reset": []}

    assert await reset({"entity_id": "assist_satellite.kitchen"}) == {"reset": [b]}
    assert b not in sessions(hass)
    assert fake_satellites["assist_satellite.kitchen"]._conversation_id is None
    assert events[-1].data == {"conversation_id": b, "satellite_id": "assist_satellite.kitchen", "source": "action"}

    assert await reset({}) == {"reset": [c]}
    assert not sessions(hass) and not logs(hass)


async def test_busy_session_is_deferred(hass: HomeAssistant) -> None:
    await setup_integration(hass)
    cid = (await say(hass, "frase")).conversation_id
    session = sessions(hass)[cid]
    if not hasattr(session, "in_use"):
        pytest.skip("Home Assistant version without ChatSession.in_use")
    session.in_use += 1
    await hass.services.async_call(DOMAIN, "reset_conversation", {"conversation_id": cid}, blocking=True)
    assert cid in sessions(hass)
    session.in_use -= 1
    await wait_deferred(hass)
    assert cid not in sessions(hass)


async def test_unload_removes_sentences(hass: HomeAssistant) -> None:
    entry = await setup_integration(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    cid = (await say(hass, "hola")).conversation_id
    assert speech(await say(hass, "olvida la conversación", cid)) != "Conversación reiniciada."
