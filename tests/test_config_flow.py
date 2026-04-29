"""Tests for the Tecnosistemi config flow."""
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tecnosystemi.const import CONF_IP, CONF_PIN, CONF_SERIAL, DOMAIN


MOCK_IP = "192.168.1.100"
MOCK_PIN = "1234"
MOCK_SERIAL = "PICO12345"
MOCK_INFO = {
    "ser": MOCK_SERIAL,
    "name": "Test Pico",
    "fw_ver": "1.0.0",
}
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
def mock_validate_and_fetch_info():
    with patch(
        "custom_components.tecnosystemi.config_flow._validate_and_fetch_info",
        return_value=MOCK_INFO,
    ) as mock:
        yield mock


@pytest.fixture
def mock_discovery():
    with patch(
        "custom_components.tecnosystemi.config_flow._do_discovery",
        return_value=[MOCK_IP],
    ) as mock:
        yield mock


@pytest.fixture
def mock_coordinator_setup():
    """Patch TecnoClient so no real UDP calls happen during coordinator setup."""
    with (
        patch("custom_components.tecnosystemi.coordinator.TecnoClient") as mock_client_cls,
        patch("custom_components.tecnosystemi.coordinator.PicoDevice") as mock_pico_cls,
        patch("custom_components.tecnosystemi.coordinator.IDPManager"),
    ):
        mock_pico = mock_pico_cls.return_value
        mock_pico.get_info.return_value = MOCK_INFO
        mock_pico.get_state.return_value = MOCK_STATE
        mock_pico.turn_on.return_value = True
        mock_pico.turn_off.return_value = True
        mock_pico.set_speed.return_value = True
        mock_pico.set_mode.return_value = True
        yield mock_pico


async def test_config_flow_discover(
    hass: HomeAssistant,
    mock_discovery,
    mock_validate_and_fetch_info,
    mock_coordinator_setup,
) -> None:
    """Happy path: discover → select device → enter PIN → entry created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "menu"
    assert "discover" in result["menu_options"]

    # Choose discover
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "discover"

    # Select the discovered device
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP: MOCK_IP}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "pin"

    # Enter PIN
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: MOCK_PIN}
    )
    assert result["type"] == "create_entry"
    assert result["title"] == MOCK_INFO["name"]
    assert result["data"][CONF_IP] == MOCK_IP
    assert result["data"][CONF_PIN] == MOCK_PIN
    assert result["data"][CONF_SERIAL] == MOCK_SERIAL


async def test_config_flow_manual(
    hass: HomeAssistant,
    mock_validate_and_fetch_info,
    mock_coordinator_setup,
) -> None:
    """Manual IP entry → PIN → entry created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP: MOCK_IP}
    )
    assert result["step_id"] == "pin"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: MOCK_PIN}
    )
    assert result["type"] == "create_entry"


async def test_config_flow_invalid_pin(
    hass: HomeAssistant,
    mock_coordinator_setup,
) -> None:
    """Wrong PIN shows an error and keeps the form open."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP: MOCK_IP}
    )

    with patch(
        "custom_components.tecnosystemi.config_flow._validate_and_fetch_info",
        return_value=None,  # PIN rejected
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PIN: "wrong"}
        )

    assert result["type"] == "form"
    assert result["errors"] == {CONF_PIN: "invalid_pin"}


async def test_config_flow_no_devices_found(
    hass: HomeAssistant,
    mock_coordinator_setup,
) -> None:
    """Discovery finds nothing → error shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )

    with patch(
        "custom_components.tecnosystemi.config_flow._do_discovery",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "no_devices_found"}


async def test_duplicate_device_aborted(
    hass: HomeAssistant,
    mock_validate_and_fetch_info,
    mock_coordinator_setup,
) -> None:
    """Adding the same serial twice aborts the second flow."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
        data={CONF_IP: MOCK_IP, CONF_PIN: MOCK_PIN, CONF_SERIAL: MOCK_SERIAL},
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP: MOCK_IP}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: MOCK_PIN}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
