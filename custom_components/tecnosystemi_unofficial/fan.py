"""Fan entity for Tecnosistemi VMC devices."""
from __future__ import annotations

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DOMAIN, MODE_TO_PRESET, ORDERED_SPEED_LIST, PRESET_MODE_MAP
from .coordinator import TecnosystemiCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TecnosystemiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TecnosistemiFan(coordinator)])


class TecnosistemiFan(CoordinatorEntity[TecnosystemiCoordinator], FanEntity):
    """Fan entity representing a Tecnosistemi Pico VMC unit."""

    _attr_has_entity_name = True
    _attr_name = None  # entity name = device name
    _attr_preset_modes = list(PRESET_MODE_MAP.keys())
    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE

    def __init__(self, coordinator: TecnosystemiCoordinator) -> None:
        super().__init__(coordinator)
        ip = coordinator.config_entry.data["ip"]
        serial = coordinator.config_entry.data.get("serial", ip)
        info = coordinator.device_info_data

        self._attr_unique_id = f"{serial}_fan"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=info.get("name") or ip,
            manufacturer="Tecnosistemi S.r.l.",
            model="Pico",
            sw_version=info.get("fw_ver"),
            serial_number=info.get("ser"),
        )

    # ------------------------------------------------------------------
    # State properties
    # ------------------------------------------------------------------

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("on_off") == 1

    @property
    def percentage(self) -> int | None:
        if not self.coordinator.data:
            return None
        speed = self.coordinator.data.get("speed")
        if speed is None:
            return None
        speed_str = str(speed)
        if speed_str not in ORDERED_SPEED_LIST:
            return None
        return ordered_list_item_to_percentage(ORDERED_SPEED_LIST, speed_str)

    @property
    def percentage_step(self) -> float:
        return 100 / len(ORDERED_SPEED_LIST)

    @property
    def preset_mode(self) -> str | None:
        if not self.coordinator.data:
            return None
        mode = self.coordinator.data.get("mod")
        return MODE_TO_PRESET.get(mode)

    # ------------------------------------------------------------------
    # Service calls
    # ------------------------------------------------------------------

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        await self.coordinator.async_turn_on()
        if percentage is not None:
            await self.async_set_percentage(percentage)
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_turn_off()

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
        speed_str = percentage_to_ordered_list_item(ORDERED_SPEED_LIST, percentage)
        await self.coordinator.async_set_speed(int(speed_str))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        mode = PRESET_MODE_MAP.get(preset_mode)
        if mode is not None:
            await self.coordinator.async_set_mode(mode)
