"""Tecnosistemi integration setup."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_DEVICE_TYPE, DEVICE_TYPE_POLARIS5X, DOMAIN
from .coordinator import Polaris5XCoordinator, TecnosystemiCoordinator

_LOGGER = logging.getLogger(__name__)

_PICO_PLATFORMS = ["fan", "sensor"]
_POLARIS_PLATFORMS = ["climate"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    device_type = entry.data.get(CONF_DEVICE_TYPE, "pico")

    if device_type == DEVICE_TYPE_POLARIS5X:
        coordinator: Polaris5XCoordinator | TecnosystemiCoordinator = (
            Polaris5XCoordinator(hass, entry)
        )
        platforms = _POLARIS_PLATFORMS
    else:
        coordinator = TecnosystemiCoordinator(hass, entry)
        platforms = _PICO_PLATFORMS

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await coordinator.async_shutdown()
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    device_type = entry.data.get(CONF_DEVICE_TYPE, "pico")
    platforms = (
        _POLARIS_PLATFORMS if device_type == DEVICE_TYPE_POLARIS5X else _PICO_PLATFORMS
    )

    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unload_ok
