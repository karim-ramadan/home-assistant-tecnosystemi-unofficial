"""Tests for fan, sensor, and climate entities."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.climate import HVACMode
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tecnosystemi.const import (
    CONF_DEVICE_TYPE,
    CONF_IP,
    CONF_PIN,
    CONF_SERIAL,
    DEVICE_TYPE_POLARIS5X,
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
    assert state.attributes["percentage"] == 100
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


# ---------------------------------------------------------------------------
# Polaris 5X climate entity tests
# ---------------------------------------------------------------------------

MOCK_POLARIS_IP = "192.168.1.200"
MOCK_POLARIS_PIN = "5678"
MOCK_POLARIS_INFO = {"name": "Test Polaris", "fw_ver": "2.0.0"}
MOCK_POLARIS_STATE = {
    "is_off": 0,
    "is_cool": 0,
    "cool_mod": 0,
    "t_can": 200,
    "f_inv": 2,
    "f_est": 2,
    "name": "Test Polaris",
    "fw_ver": "2.0.0",
    "zone": [
        {
            "nr": 1,
            "n": "Living Room",
            "off": 0,
            "t": 215,
            "ts": 220,
            "w": -1,
            "b": -1,
            "co": 0,
            "err": 0,
        },
        {
            "nr": 2,
            "n": "Bedroom",
            "off": 1,
            "t": 180,
            "ts": 200,
            "w": -1,
            "b": -1,
            "co": 0,
            "err": 0,
        },
    ],
}


@pytest.fixture
async def loaded_polaris_entry(hass: HomeAssistant):
    """Set up a Polaris 5X config entry with all network calls mocked."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_POLARIS_IP,
        data={
            CONF_IP: MOCK_POLARIS_IP,
            CONF_PIN: MOCK_POLARIS_PIN,
            CONF_SERIAL: MOCK_POLARIS_IP,
            CONF_DEVICE_TYPE: DEVICE_TYPE_POLARIS5X,
        },
        title="Test Polaris",
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.tecnosystemi.coordinator.PolarisClient"),
        patch(
            "custom_components.tecnosystemi.coordinator.Polaris5XDevice"
        ) as mock_dev_cls,
    ):
        mock_dev = mock_dev_cls.return_value
        mock_dev.get_state = AsyncMock(return_value=MOCK_POLARIS_STATE)
        mock_dev.turn_on = AsyncMock(return_value=True)
        mock_dev.turn_off = AsyncMock(return_value=True)
        mock_dev.set_mode = AsyncMock(return_value=True)
        mock_dev.update_zone = AsyncMock(return_value=True)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        yield entry, mock_dev


async def test_polaris_cu_state(hass: HomeAssistant, loaded_polaris_entry) -> None:
    """CU entity reflects heating mode and canal temperature setpoint."""
    state = hass.states.get("climate.test_polaris")
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes["temperature"] == 20.0  # tc=200 → 20.0 °C


async def test_polaris_zone_state(hass: HomeAssistant, loaded_polaris_entry) -> None:
    """Zone entities reflect correct state and temperature."""
    zone1 = hass.states.get("climate.test_polaris_living_room")
    assert zone1 is not None
    assert zone1.state == HVACMode.HEAT
    assert zone1.attributes["current_temperature"] == 21.5
    assert zone1.attributes["temperature"] == 22.0  # ts=220 → 22.0 °C

    zone2 = hass.states.get("climate.test_polaris_bedroom")
    assert zone2 is not None
    assert zone2.state == HVACMode.OFF


async def test_polaris_cu_turn_off(hass: HomeAssistant, loaded_polaris_entry) -> None:
    """Setting CU to OFF calls turn_off on the device."""
    entry, mock_dev = loaded_polaris_entry
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {"entity_id": "climate.test_polaris", "hvac_mode": HVACMode.OFF},
        blocking=True,
    )
    mock_dev.turn_off.assert_called_once()


async def test_polaris_cu_set_temperature(
    hass: HomeAssistant, loaded_polaris_entry
) -> None:
    """Setting canal temperature on the CU entity calls set_canal_temperature."""
    entry, mock_dev = loaded_polaris_entry
    mock_dev.set_canal_temperature = AsyncMock(return_value=True)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {"entity_id": "climate.test_polaris", "temperature": 22.0},
        blocking=True,
    )
    mock_dev.set_canal_temperature.assert_called_once_with(22.0)


async def test_polaris_zone_set_temperature(
    hass: HomeAssistant, loaded_polaris_entry
) -> None:
    """Setting temperature on a zone calls update_zone with correct setpoint."""
    entry, mock_dev = loaded_polaris_entry
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {"entity_id": "climate.test_polaris_living_room", "temperature": 21.0},
        blocking=True,
    )
    mock_dev.update_zone.assert_called_once()
    call_kwargs = mock_dev.update_zone.call_args.kwargs
    assert call_kwargs["zone_id"] == 1
    assert call_kwargs["set_temp"] == 21.0
    assert call_kwargs["is_off"] == 0
