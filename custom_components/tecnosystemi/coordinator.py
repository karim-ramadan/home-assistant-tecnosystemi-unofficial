"""DataUpdateCoordinator for Tecnosistemi devices."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from tecnosystemi_unofficial import PolarisClient, TecnoClient
from tecnosystemi_unofficial.devices import PicoDevice, Polaris5XDevice

from homeassistant.const import CONF_NAME

from .const import CONF_IP, CONF_PIN, CONF_SERIAL, DOMAIN


def _zone_id(z: dict) -> int:
    """Return zone ID from either full ('id_zona') or ridotto ('nr') format."""
    return z.get("id_zona") or z.get("nr", 0)


def _zone_fan(z: dict) -> int:
    """Return fan coil speed from either full ('fan') or ridotto ('w') format."""
    v = z.get("fan", z.get("w", -1))
    return v if v is not None else -1

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


class Polaris5XCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator that polls a Tecnosistemi Polaris 5X multi-zone HVAC unit."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_polaris5x {entry.data[CONF_IP]}",
            config_entry=entry,
            update_interval=POLL_INTERVAL,
        )
        self._ip: str = entry.data[CONF_IP]
        self._pin: str = entry.data[CONF_PIN]
        self._lock = asyncio.Lock()
        self.device_info_data: dict = {}
        self.zones: list[dict] = []
        self._client: PolarisClient | None = None
        self.polaris: Polaris5XDevice | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _async_setup(self) -> None:
        """Connect to the device and discover zones from the initial state."""
        self._client = PolarisClient(ip=self._ip, pin=self._pin, timeout=10.0)
        self.polaris = Polaris5XDevice(self._client)
        try:
            state = await self.polaris.get_state()
            if state is None:
                raise ConfigEntryNotReady(f"No response from {self._ip}")
            self.device_info_data = {
                "name": self.config_entry.data.get(CONF_NAME) or state.get("name"),
                "fw_ver": state.get("fw_ver"),
            }
            self.zones = [
                {
                    "id_zona": _zone_id(z),
                    "name": z.get("name") or z.get("n") or f"Zone {_zone_id(z)}",
                    "has_fan": _zone_fan(z) != -1,
                }
                for z in state.get("zone", [])
            ]
        except ConfigEntryNotReady:
            raise
        except Exception as exc:
            raise ConfigEntryNotReady(
                f"Failed to connect to {self._ip}: {exc}"
            ) from exc

    async def async_shutdown(self) -> None:
        """No-op — PolarisClient uses stateless per-command TCP connections."""

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        if self._lock.locked():
            return self.data or {}
        state = await self.polaris.get_state()
        if state is None:
            raise UpdateFailed(f"No response from {self._ip} (timeout)")
        return state

    def _merge_data(self, patch: dict) -> dict:
        return {**(self.data or {}), **patch}

    # ------------------------------------------------------------------
    # CU-level control
    # ------------------------------------------------------------------

    async def async_turn_on(self) -> None:
        async with self._lock:
            res = await self.polaris.turn_on()
            if res:
                self.async_set_updated_data(self._merge_data({"is_off": 0, "off": 0}))

    async def async_turn_off(self) -> None:
        async with self._lock:
            res = await self.polaris.turn_off()
            if res:
                self.async_set_updated_data(self._merge_data({"is_off": 1, "off": 1}))

    async def async_set_mode(self, mode: int) -> None:
        async with self._lock:
            res = await self.polaris.set_mode(mode)
            if res:
                if mode == 0:  # HEATING
                    patch = {"is_off": 0, "off": 0, "is_cool": 0, "cl": 0, "cool_mod": 0, "cl_m": 0}
                else:
                    patch = {"is_off": 0, "off": 0, "is_cool": 1, "cl": 1, "cool_mod": mode, "cl_m": mode}
                self.async_set_updated_data(self._merge_data(patch))

    async def async_set_canal_temperature(self, temp: float) -> None:
        async with self._lock:
            res = await self.polaris.set_canal_temperature(temp)
            if res:
                raw = round(temp * 10)
                self.async_set_updated_data(self._merge_data({"t_can": raw, "tc": raw}))

    # ------------------------------------------------------------------
    # Zone-level control
    # ------------------------------------------------------------------

    async def async_update_zone(
        self,
        zone_id: int,
        name: str,
        *,
        is_off: int,
        set_temp: float,
        is_crono: int = 0,
        fan_set: int | None = None,
    ) -> None:
        async with self._lock:
            res = await self.polaris.update_zone(
                zone_id=zone_id,
                name=name,
                is_off=is_off,
                set_temp=set_temp,
                is_crono=is_crono,
                fan_set=fan_set,
            )
            if res:
                raw_set = str(round(set_temp * 10))
                current = dict(self.data or {})
                zones = list(current.get("zone", []))
                for i, z in enumerate(zones):
                    if _zone_id(z) == zone_id:
                        updated = {**z, "is_off": is_off, "off": is_off, "t_set": raw_set, "ts": raw_set}
                        if fan_set is not None and fan_set != -1:
                            updated["fan_set"] = fan_set
                        zones[i] = updated
                        break
                current["zone"] = zones
                self.async_set_updated_data(current)
