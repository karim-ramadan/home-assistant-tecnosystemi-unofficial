"""Tests for fan and sensor entities."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tecnosystemi.const import (
    CONF_IP,
    CONF_PIN,
    CONF_SERIAL,
    DOMAIN,
)

MOCK_IP = "192.168.1.100"
MOCK_PIN = "1234"
MOCK_SERIAL = "PICO12345"
MOCK_INFO = {"ser": MOCK_SERIAL, "name": "Test Pico", "fw_ver": "1.0.0"}
MOCK_STATE = {
    "on_off": 1,
    "speed": 3,
    "mod": 1,
    "umd": 55,
    "AMB_tmpr": 21.5,
    "EXT_tmpr": 10.0,
    "night_mod": 0,
}


@pytest.fixture
async def loaded_entry(hass: HomeAssistant):
    """Set up a config entry with all network calls mocked."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
        data={CONF_IP: MOCK_IP, CONF_PIN: MOCK_PIN, CONF_SERIAL: MOCK_SERIAL},
        title="Test Pico",
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.tecnosystemi.coordinator.TecnoClient"),
        patch("custom_components.tecnosystemi.coordinator.PicoDevice") as mock_pico_cls,
    ):
        mock_pico = mock_pico_cls.return_value
        mock_pico.get_info = AsyncMock(return_value=MOCK_INFO)
        mock_pico.get_state = AsyncMock(return_value=MOCK_STATE)
        mock_pico.turn_on = AsyncMock(return_value=True)
        mock_pico.turn_off = AsyncMock(return_value=True)
        mock_pico.set_speed = AsyncMock(return_value=True)
        mock_pico.set_mode = AsyncMock(return_value=True)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        yield entry, mock_pico


async def test_fan_state(hass: HomeAssistant, loaded_entry) -> None:
    """Fan is on, speed=3→60%, preset=Recupero, LED color=Turchese."""
    entry, _ = loaded_entry
    state = hass.states.get("fan.test_pico")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["percentage"] == 60
    assert state.attributes["preset_mode"] == "Recupero 🔵"
    assert state.attributes["led_color_name"] == "Turchese"
    assert state.attributes["led_color_hex"] == "#4DB6AC"


async def test_fan_turn_off(hass: HomeAssistant, loaded_entry) -> None:
    entry, mock_pico = loaded_entry
    await hass.services.async_call(
        FAN_DOMAIN, "turn_off", {"entity_id": "fan.test_pico"}, blocking=True
    )
    mock_pico.turn_off.assert_called_once()


async def test_fan_set_speed(hass: HomeAssistant, loaded_entry) -> None:
    entry, mock_pico = loaded_entry
    await hass.services.async_call(
        FAN_DOMAIN,
        "set_percentage",
        {"entity_id": "fan.test_pico", "percentage": 40},
        blocking=True,
    )
    mock_pico.set_speed.assert_called_once_with(2)


async def test_fan_set_preset_mode(hass: HomeAssistant, loaded_entry) -> None:
    entry, mock_pico = loaded_entry
    await hass.services.async_call(
        FAN_DOMAIN,
        "set_preset_mode",
        {"entity_id": "fan.test_pico", "preset_mode": "Estrazione 🟢"},
        blocking=True,
    )
    mock_pico.set_mode.assert_called_once_with(2)


async def test_sensors(hass: HomeAssistant, loaded_entry) -> None:
    """Sensor values are read from coordinator state."""
    assert hass.states.get("sensor.test_pico_ambient_temperature").state == "21.5"
    assert hass.states.get("sensor.test_pico_external_temperature").state == "10.0"
    assert hass.states.get("sensor.test_pico_humidity").state == "55"


async def test_led_color_sensor(hass: HomeAssistant, loaded_entry) -> None:
    """LED color sensor reflects the color for the current mode."""
    state = hass.states.get("sensor.test_pico_led_color")
    assert state is not None
    assert state.state == "Turchese"
    assert state.attributes["led_color_hex"] == "#4DB6AC"
