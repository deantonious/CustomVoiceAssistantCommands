"""Diagnostics for Assist Utils (no conversation content is included)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant

from . import AssistUtilsConfigEntry, compat


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AssistUtilsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics."""
    sessions = compat.get_sessions(hass)
    satellites = compat.satellite_entity_ids(hass)
    return {
        "home_assistant": HA_VERSION,
        "missing_internals": entry.runtime_data.missing,
        "options": dict(entry.options),
        "effective_commands": {
            key: asdict(config) for key, config in entry.runtime_data.commands.items()
        },
        "active_conversations": len(sessions),
        "busy_conversations": sum(1 for s in sessions.values() if compat.is_busy(s)),
        "satellites": {
            entity_id: {"has_conversation": compat.satellite_conversation_id(hass, entity_id) is not None}
            for entity_id in satellites
        },
    }
