"""Config and options flow tests."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.assist_utils.const import DOMAIN

from .conftest import say, setup_integration, speech, wait_deferred


async def test_user_flow_defaults_to_ha_language(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    schema = result["data_schema"].schema
    default = next(k for k in schema if k == "languages").default()
    assert default == ["es"]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"languages": []})
    assert result["errors"] == {"languages": "no_language"}


async def test_unsupported_ha_language_falls_back_to_english(hass: HomeAssistant) -> None:
    hass.config.language = "de"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    default = next(k for k in result["data_schema"].schema if k == "languages").default()
    assert default == ["en"]


async def test_single_instance(hass: HomeAssistant) -> None:
    await setup_integration(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT


async def _options(hass, entry, step, data):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert set(result["menu_options"]) == {"features", "languages", "reset", "cancel"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": step}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(result["flow_id"], data)
    await hass.async_block_till_done()
    return result


async def test_changing_languages_changes_default_phrases(hass: HomeAssistant) -> None:
    entry = await setup_integration(hass, ["es"])
    cid = (await say(hass, "hola")).conversation_id
    assert speech(await say(hass, "olvida la conversación", cid)) == "Conversación reiniciada."
    await wait_deferred(hass)

    result = await _options(hass, entry, "languages", {"languages": ["en"]})
    assert result["type"] is FlowResultType.CREATE_ENTRY

    cid = (await say(hass, "hola")).conversation_id
    assert speech(await say(hass, "olvida la conversación", cid)) != "Conversación reiniciada."
    result = await say(hass, "start over", cid, language="en")
    assert speech(result) == "Conversation reset."
    await wait_deferred(hass)


async def test_custom_phrases_invalid_and_back_to_defaults(hass: HomeAssistant) -> None:
    entry = await setup_integration(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "reset"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"sentences": "borra todo.", "response": ""}
    )
    assert result["errors"] == {"sentences": "invalid_sentence"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"sentences": "borra todo\n\n(reinicia|reset) [ya]\n", "response": ""},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    stored = entry.options["commands"]["reset"]
    assert stored["sentences"] == ["borra todo", "(reinicia|reset) [ya]"]
    assert stored["response"] == ""

    cid = (await say(hass, "hola")).conversation_id
    assert speech(await say(hass, "olvida la conversación", cid)) != "Conversación reiniciada."
    assert speech(await say(hass, "reinicia ya", cid)) == ""  # custom, silent
    await wait_deferred(hass)

    # Clearing the field stores None, i.e. "follow the language defaults".
    await _options(hass, entry, "reset", {"sentences": "", "response": "Conversación reiniciada."})
    stored = entry.options["commands"]["reset"]
    assert stored["sentences"] is None and stored["response"] is None
    cid = (await say(hass, "hola")).conversation_id
    assert speech(await say(hass, "olvida la conversación", cid)) == "Conversación reiniciada."
    await wait_deferred(hass)


async def test_features_page_turns_features_off_and_on(hass: HomeAssistant) -> None:
    entry = await setup_integration(hass)
    result = await _options(hass, entry, "features", {"features": ["reset", "satellite_buttons"]})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["commands"]["cancel"]["enabled"] is False
    assert entry.options["commands"]["reset"]["enabled"] is True
    assert entry.options["reset_all_button"] is False

    cid = (await say(hass, "hola")).conversation_id
    # Silent cancel is off: the default agent answers instead.
    assert speech(await say(hass, "falsa alarma", cid)) != ""
    assert speech(await say(hass, "olvida la conversación", cid)) == "Conversación reiniciada."
    await wait_deferred(hass)

    # The page shows the current state, and features come back on.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "features"})
    default = next(k for k in result["data_schema"].schema if k == "features").default()
    assert sorted(default) == ["reset", "satellite_buttons"]
    await hass.config_entries.options.async_configure(
        result["flow_id"], {"features": ["reset", "cancel", "satellite_buttons", "reset_all_button"]}
    )
    await hass.async_block_till_done()
    cid = (await say(hass, "hola")).conversation_id
    assert speech(await say(hass, "falsa alarma", cid)) == ""


async def test_phrase_pages_keep_on_off_state(hass: HomeAssistant) -> None:
    entry = await setup_integration(hass)
    await _options(hass, entry, "features", {"features": ["reset"]})
    await _options(hass, entry, "cancel", {"sentences": "", "response": "", "also_reset": True})
    assert entry.options["commands"]["cancel"]["enabled"] is False
    assert entry.options["commands"]["cancel"]["also_reset"] is True


async def test_choose_features_at_setup(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    default = next(k for k in result["data_schema"].schema if k == "features").default()
    assert sorted(default) == ["cancel", "reset", "reset_all_button", "satellite_buttons"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"languages": ["es"], "features": ["cancel"]}
    )
    entry = result["result"]
    await hass.async_block_till_done()
    assert entry.options["commands"]["reset"]["enabled"] is False
    assert entry.options["satellite_buttons"] is False and entry.options["reset_all_button"] is False
    cid = (await say(hass, "hola")).conversation_id
    assert speech(await say(hass, "olvida la conversación", cid)) != "Conversación reiniciada."
