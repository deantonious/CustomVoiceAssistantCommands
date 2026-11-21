"""Buttons to reset Assist conversations.

- "Reset all conversations" on the integration's own service device.
- "Reset conversation" on every Assist satellite's device, kept in sync as
  satellites are added and removed.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device as device_helper, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AssistUtilsConfigEntry
from .const import CONF_RESET_ALL_BUTTON, CONF_SATELLITE_BUTTONS, DOMAIN, NAME, SOURCE_BUTTON
from .conversation_reset import async_reset_all, async_reset_satellite

SATELLITE_DOMAIN = "assist_satellite"
UNIQUE_ID_RESET_ALL = "reset_all"
UNIQUE_ID_SATELLITE_PREFIX = "reset_satellite_"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AssistUtilsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons."""
    ent_reg = er.async_get(hass)

    if entry.options.get(CONF_RESET_ALL_BUTTON, True):
        async_add_entities([ResetAllButton(entry)])
    elif entity_id := ent_reg.async_get_entity_id("button", DOMAIN, UNIQUE_ID_RESET_ALL):
        ent_reg.async_remove(entity_id)

    satellite_buttons = entry.options.get(CONF_SATELLITE_BUTTONS, True)
    added: dict[str, SatelliteResetButton] = {}

    def _is_satellite(reg_entry: er.RegistryEntry | None) -> bool:
        return (
            reg_entry is not None
            and reg_entry.domain == SATELLITE_DOMAIN
            and reg_entry.device_id is not None
        )

    @callback
    def _add(reg_entries: list[er.RegistryEntry]) -> None:
        new = [
            SatelliteResetButton(hass, entry, reg_entry)
            for reg_entry in reg_entries
            if reg_entry.id not in added
        ]
        for button in new:
            added[button.satellite_registry_id] = button
        if new:
            async_add_entities(new)

    @callback
    def _remove_button(satellite_registry_id: str) -> None:
        added.pop(satellite_registry_id, None)
        if entity_id := ent_reg.async_get_entity_id(
            "button", DOMAIN, f"{UNIQUE_ID_SATELLITE_PREFIX}{satellite_registry_id}"
        ):
            ent_reg.async_remove(entity_id)

    satellites = {
        reg_entry.id: reg_entry
        for reg_entry in ent_reg.entities.values()
        if _is_satellite(reg_entry)
    }

    # Remove buttons whose satellite is gone, or all of them if turned off.
    for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if reg_entry.unique_id.startswith(UNIQUE_ID_SATELLITE_PREFIX):
            satellite_id = reg_entry.unique_id.removeprefix(UNIQUE_ID_SATELLITE_PREFIX)
            if not satellite_buttons or satellite_id not in satellites:
                ent_reg.async_remove(reg_entry.entity_id)

    if not satellite_buttons:
        return

    _add(list(satellites.values()))

    @callback
    def _registry_updated(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        data = event.data
        if data["action"] == "remove":
            if data["entity_id"].startswith(f"{SATELLITE_DOMAIN}."):
                # The registry entry is gone; find our button by entity ID.
                for satellite_id, button in list(added.items()):
                    if button.satellite_entity_id == data["entity_id"]:
                        _remove_button(satellite_id)
            return
        reg_entry = ent_reg.async_get(data["entity_id"])
        if not _is_satellite(reg_entry):
            return
        if data["action"] == "create":
            _add([reg_entry])
        elif data["action"] == "update" and "device_id" in data.get("changes", {}):
            # Re-create the button on the satellite's new device.
            _remove_button(reg_entry.id)
            _add([reg_entry])

    entry.async_on_unload(
        hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _registry_updated)
    )


class ResetAllButton(ButtonEntity):
    """Reset every Assist conversation."""

    _attr_has_entity_name = True
    _attr_translation_key = "reset_all"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: AssistUtilsConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = UNIQUE_ID_RESET_ALL
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="deantonious",
        )

    @property
    def available(self) -> bool:
        return self._entry.runtime_data.reset_supported

    async def async_press(self) -> None:
        async_reset_all(self.hass, source=SOURCE_BUTTON)


class SatelliteResetButton(ButtonEntity):
    """Reset the conversation of one Assist satellite, shown on its device."""

    _attr_has_entity_name = True
    _attr_translation_key = "reset_satellite"

    def __init__(
        self, hass: HomeAssistant, entry: AssistUtilsConfigEntry, satellite: er.RegistryEntry
    ) -> None:
        self._entry = entry
        self.satellite_registry_id = satellite.id
        self.satellite_entity_id = satellite.entity_id
        self._attr_unique_id = f"{UNIQUE_ID_SATELLITE_PREFIX}{satellite.id}"
        # No device_info: Home Assistant attaches the entity to this device
        # (linking through device_info identifiers is deprecated).
        self.device_entry = device_helper.async_entity_id_to_device(hass, satellite.entity_id)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _satellite_renamed(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
            if event.data["action"] == "update" and (
                event.data.get("old_entity_id") == self.satellite_entity_id
            ):
                self.satellite_entity_id = event.data["entity_id"]

        self.async_on_remove(
            self.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _satellite_renamed)
        )

    @property
    def available(self) -> bool:
        return self._entry.runtime_data.reset_supported

    async def async_press(self) -> None:
        async_reset_satellite(
            self.hass,
            self.satellite_entity_id,
            source=SOURCE_BUTTON,
            satellites_supported=self._entry.runtime_data.satellites_supported,
        )
