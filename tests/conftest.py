"""Fixtures for Assist Utils tests."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant import config_entries
from homeassistant.components import conversation
from homeassistant.components.conversation.chat_log import DATA_CHAT_LOGS
from homeassistant.core import Context, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import chat_session
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.assist_utils import compat
from custom_components.assist_utils.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    yield


@pytest.fixture(autouse=True)
async def setup_conversation(hass: HomeAssistant) -> None:
    """Set up the components Assist needs."""
    hass.config.language = "es"
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    await hass.async_block_till_done()


@pytest.fixture
def fake_satellites(monkeypatch: pytest.MonkeyPatch) -> dict[str, SimpleNamespace]:
    """Fake loaded satellite entities, keyed by entity ID.

    Each has the private ``_conversation_id`` that Home Assistant's
    AssistSatelliteEntity uses for the conversation it continues on next wake.
    """
    satellites: dict[str, SimpleNamespace] = {}
    monkeypatch.setattr(compat, "_satellite_entity", lambda hass, eid: satellites.get(eid))
    monkeypatch.setattr(compat, "satellite_entity_ids", lambda hass: list(satellites))
    return satellites


async def setup_integration(hass: HomeAssistant, languages: list[str] | None = None):
    """Add the integration through the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"languages": languages or ["es"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


async def say(hass: HomeAssistant, text: str, conversation_id: str | None = None, language="es"):
    """Send text to Assist like a satellite would."""
    return await conversation.async_converse(
        hass, text, conversation_id, Context(), language=language
    )


def speech(result) -> str:
    return result.response.speech.get("plain", {}).get("speech", "")


def sessions(hass: HomeAssistant) -> dict:
    return hass.data.get(chat_session.DATA_CHAT_SESSION) or {}


def logs(hass: HomeAssistant) -> dict:
    return hass.data.get(DATA_CHAT_LOGS) or {}


async def wait_deferred(hass: HomeAssistant) -> None:
    """Let deferred resets (which wait for the turn to end) run."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
