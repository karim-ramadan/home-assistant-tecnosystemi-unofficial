"""DataUpdateCoordinator for Tecnosistemi devices."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from tecnosystemi_unofficial import TecnoClient
from tecnosystemi_unofficial.devices import PicoDevice

from .const import CONF_IP, CONF_PIN, CONF_SERIAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(seconds=60)


class TecnosystemiCoordinator(DataUpdateCoordinator[dict]):
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
        self._client = TecnoClient(ip=self._ip, timeout=40.0)
        self.pico = PicoDevice(self._client, pin=self._pin)

        try:
            self._client.start()
            info = await self.pico.get_info()
            if info:
                self.device_info_data = info
        except Exception as exc:
            self._client.stop()
            raise ConfigEntryNotReady(
                f"Failed to connect to {self._ip}: {exc}"
            ) from exc

    async def async_shutdown(self) -> None:
        """Stop the underlying client."""
        if self._client is not None:
            self._client.stop()

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        if self._lock.locked():
            return self.data or {}
        state = await self.pico.get_state()
        if state is None:
            raise UpdateFailed(f"No response from {self._ip} (timeout)")
        return state

    def _merge_data(self, patch: dict) -> dict:
        return {**(self.data or {}), **patch}

    async def async_turn_on(self) -> None:
        async with self._lock:
            res = await self.pico.turn_on()
            if res:
                self.async_set_updated_data(self._merge_data({"on_off": 1}))

    async def async_turn_off(self) -> None:
        async with self._lock:
            res = await self.pico.turn_off()
            if res:
                self.async_set_updated_data(self._merge_data({"on_off": 2}))

    async def async_set_speed(self, speed: int) -> None:
        async with self._lock:
            if self.data.get("on_off") != 1:
                await self.pico.turn_on()
            res = await self.pico.set_speed(speed)
            if res:
                self.async_set_updated_data(
                    self._merge_data({"on_off": 1, "speed": speed})
                )

    async def async_set_mode(self, mode: int) -> None:
        async with self._lock:
            res = await self.pico.set_mode(mode)
            if res:
                self.async_set_updated_data(self._merge_data({"mod": mode}))
