"""DataUpdateCoordinator for Tecnosistemi devices."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_IP, CONF_PIN, CONF_SERIAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(seconds=60)


class TecnosistemiCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator that polls a single Tecnosistemi Pico device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.data[CONF_IP]}",
            config_entry=entry,
            update_interval=POLL_INTERVAL,
        )
        self._ip: str = entry.data[CONF_IP]
        self._pin: str = entry.data[CONF_PIN]
        self._serial: str = entry.data.get(CONF_SERIAL, self._ip)
        self._lock = asyncio.Lock()
        self.device_info_data: dict = {}
        self._client = None
        self.pico = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _async_setup(self) -> None:
        """Start the client and fetch static device info."""
        from tecnosystemy_unofficial import TecnoClient
        from tecnosystemy_unofficial.devices import PicoDevice
        from tecnosystemy_unofficial.idp import IDPManager

        idp_path = (
            Path(self.hass.config.config_dir)
            / ".storage"
            / f"tecnosystemi_{self._ip.replace('.', '_')}_idp.json"
        )
        idp_mgr = IDPManager(backend="file", path=idp_path)
        self._client = TecnoClient(ip=self._ip, idp_manager=idp_mgr, timeout=25.0)
        self.pico = PicoDevice(self._client, pin=self._pin)

        try:
            await self.hass.async_add_executor_job(self._client.start)
            info = await self.hass.async_add_executor_job(self.pico.get_info)
            if info:
                self.device_info_data = info
        except Exception as exc:
            await self.hass.async_add_executor_job(self._client.stop)
            raise ConfigEntryNotReady(f"Failed to connect to {self._ip}: {exc}") from exc

    async def async_shutdown(self) -> None:
        """Stop the underlying client."""
        if self._client is not None:
            await self.hass.async_add_executor_job(self._client.stop)

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        async with self._lock:
            state = await self.hass.async_add_executor_job(self.pico.get_state)
        if state is None:
            raise UpdateFailed(f"No response from {self._ip} (timeout)")
        return state

    # ------------------------------------------------------------------
    # Control helpers (serialize with lock, then refresh)
    # ------------------------------------------------------------------

    async def async_turn_on(self) -> None:
        async with self._lock:
            await self.hass.async_add_executor_job(self.pico.turn_on)
        await self.async_request_refresh()

    async def async_turn_off(self) -> None:
        async with self._lock:
            await self.hass.async_add_executor_job(self.pico.turn_off)
        await self.async_request_refresh()

    async def async_set_speed(self, speed: int) -> None:
        async with self._lock:
            await self.hass.async_add_executor_job(self.pico.set_speed, speed)
        await self.async_request_refresh()

    async def async_set_mode(self, mode: int) -> None:
        async with self._lock:
            await self.hass.async_add_executor_job(self.pico.set_mode, mode)
        await self.async_request_refresh()
