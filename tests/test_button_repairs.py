"""Button, Repairs and diagnostics tests."""

from types import SimpleNamespace

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir

from custom_components.assist_utils import compat
from custom_components.assist_utils.const import DOMAIN, ISSUE_INCOMPATIBLE
from custom_components.assist_utils.diagnostics import async_get_config_entry_diagnostics

from .conftest import say, sessions, setup_integration


def _add_satellite(hass: HomeAssistant, object_id: str = "kitchen") -> tuple[er.RegistryEntry, dr.DeviceEntry]:
    """Register a satellite entity on its own device, owned by another integration."""
    other = MockConfigEntry(domain="esphome")
    other.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id, identifiers={("esphome", object_id)}, name=f"{object_id} satellite"
    )
    entity = er.async_get(hass).async_get_or_create(
        "assist_satellite", "esphome", f"{object_id}-sat",
        suggested_object_id=object_id, config_entry=other, device_id=device.id,
    )
    return entity, device


def _our_buttons(hass: HomeAssistant, entry) -> dict[str, er.RegistryEntry]:
    return {e.unique_id: e for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}


async def test_reset_all_button(hass: HomeAssistant) -> None:
    entry = await setup_integration(hass)
    buttons = _our_buttons(hass, entry)
    assert "reset_all" in buttons
    device = dr.async_get(hass).async_get(buttons["reset_all"].device_id)
    assert device.entry_type is dr.DeviceEntryType.SERVICE

    cid = (await say(hass, "hola")).conversation_id
    await hass.services.async_call("button", "press", {"entity_id": buttons["reset_all"].entity_id}, blocking=True)
    assert cid not in sessions(hass)


async def test_satellite_button_on_satellite_device(hass: HomeAssistant, fake_satellites) -> None:
    existing, existing_device = _add_satellite(hass, "kitchen")
    entry = await setup_integration(hass)

    button = _our_buttons(hass, entry)[f"reset_satellite_{existing.id}"]
    assert button.device_id == existing_device.id

    # Press resets exactly that satellite's conversation.
    a = (await say(hass, "uno")).conversation_id
    b = (await say(hass, "dos")).conversation_id
    fake_satellites[existing.entity_id] = SimpleNamespace(_conversation_id=a)
    await hass.services.async_call("button", "press", {"entity_id": button.entity_id}, blocking=True)
    assert a not in sessions(hass) and b in sessions(hass)

    # A satellite added later gets a button too; removing it removes the button.
    new, new_device = _add_satellite(hass, "bedroom")
    await hass.async_block_till_done()
    new_button = _our_buttons(hass, entry)[f"reset_satellite_{new.id}"]
    assert new_button.device_id == new_device.id

    er.async_get(hass).async_remove(new.entity_id)
    await hass.async_block_till_done()
    assert f"reset_satellite_{new.id}" not in _our_buttons(hass, entry)


async def test_satellite_buttons_can_be_turned_off(hass: HomeAssistant) -> None:
    sat, _ = _add_satellite(hass)
    entry = await setup_integration(hass)
    assert f"reset_satellite_{sat.id}" in _our_buttons(hass, entry)

    hass.config_entries.async_update_entry(entry, options={**entry.options, "satellite_buttons": False})
    await hass.async_block_till_done()
    assert set(_our_buttons(hass, entry)) == {"reset_all"}

    hass.config_entries.async_update_entry(entry, options={**entry.options, "reset_all_button": False})
    await hass.async_block_till_done()
    assert set(_our_buttons(hass, entry)) == set()


async def test_repair_issue_and_fallback(hass: HomeAssistant, monkeypatch, fake_satellites) -> None:
    monkeypatch.setattr(compat, "check", lambda: {compat.FEATURE_SATELLITES: "AssistSatelliteEntity._conversation_id"})
    sat, _ = _add_satellite(hass)
    entry = await setup_integration(hass)

    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_INCOMPATIBLE)
    assert issue is not None and issue.translation_placeholders["missing"] == "- AssistSatelliteEntity._conversation_id"

    # Satellite support missing: its button falls back to resetting everything.
    a = (await say(hass, "uno")).conversation_id
    b = (await say(hass, "dos")).conversation_id
    button = _our_buttons(hass, entry)[f"reset_satellite_{sat.id}"]
    await hass.services.async_call("button", "press", {"entity_id": button.entity_id}, blocking=True)
    assert a not in sessions(hass) and b not in sessions(hass)

    # Once compatible again, the issue disappears on reload.
    monkeypatch.setattr(compat, "check", lambda: {})
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_INCOMPATIBLE) is None


async def test_real_compat_check_passes(hass: HomeAssistant) -> None:
    assert compat.check() == {}


async def test_diagnostics(hass: HomeAssistant) -> None:
    entry = await setup_integration(hass)
    await say(hass, "hola")
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["active_conversations"] == 1
    assert diag["missing_internals"] == {}
    assert "olvida la conversación" not in str(diag["options"])  # defaults aren't stored
    assert diag["effective_commands"]["reset"]["enabled"] is True
