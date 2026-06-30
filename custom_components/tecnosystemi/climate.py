"""Climate entities for Tecnosistemi Polaris 5X multi-zone HVAC."""

from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Polaris5XCoordinator, _zone_id

_HVAC_MODE_TO_OP_MODE: dict[HVACMode, int] = {
    HVACMode.HEAT: 0,
    HVACMode.COOL: 1,
    HVACMode.DRY: 2,
    HVACMode.FAN_ONLY: 3,
}

_OP_MODE_TO_HVAC_MODE: dict[int, HVACMode] = {
    v: k for k, v in _HVAC_MODE_TO_OP_MODE.items()
}

_ALL_HVAC_MODES = [
    HVACMode.OFF,
    HVACMode.HEAT,
    HVACMode.COOL,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
]


def _get(state: dict, *keys, default=0):
    for k in keys:
        if k in state:
            return state[k]
    return default


def _cu_hvac_mode(data: dict) -> HVACMode:
    if _get(data, "is_off", "off") == 1:
        return HVACMode.OFF
    is_cool = _get(data, "is_cool", "cl")
    cool_mod = _get(data, "cool_mod", "cl_m")
    if not is_cool:
        return HVACMode.HEAT
    return _OP_MODE_TO_HVAC_MODE.get(cool_mod, HVACMode.COOL)


def _cu_hvac_action(data: dict) -> HVACAction:
    if _get(data, "is_off", "off") == 1:
        return HVACAction.OFF
    is_cool = _get(data, "is_cool", "cl")
    cool_mod = _get(data, "cool_mod", "cl_m")
    if not is_cool:
        return HVACAction.HEATING
    return {1: HVACAction.COOLING, 2: HVACAction.DRYING, 3: HVACAction.FAN}.get(
        cool_mod, HVACAction.COOLING
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: Polaris5XCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ClimateEntity] = [Polaris5XCUClimate(coordinator)]
    for zone in coordinator.zones:
        entities.append(Polaris5XZoneClimate(coordinator, zone))
    async_add_entities(entities)


def _device_info(coordinator: Polaris5XCoordinator) -> DeviceInfo:
    ip = coordinator.config_entry.data["ip"]
    info = coordinator.device_info_data
    return DeviceInfo(
        identifiers={(DOMAIN, ip)},
        name=info.get("name") or ip,
        manufacturer="Tecnosistemi S.r.l.",
        model="Polaris 5X",
        sw_version=info.get("fw_ver"),
    )


class Polaris5XCUClimate(CoordinatorEntity[Polaris5XCoordinator], ClimateEntity):
    """Climate entity for the Polaris 5X control unit (global on/off, mode, and canal temperature)."""

    _attr_has_entity_name = True
    _attr_name = None  # entity name = device name
    _attr_hvac_modes = _ALL_HVAC_MODES
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 16.0
    _attr_max_temp = 30.0

    def __init__(self, coordinator: Polaris5XCoordinator) -> None:
        super().__init__(coordinator)
        ip = coordinator.config_entry.data["ip"]
        self._attr_unique_id = f"{ip}_cu"
        self._attr_device_info = _device_info(coordinator)

    @property
    def hvac_mode(self) -> HVACMode | None:
        if not self.coordinator.data:
            return None
        return _cu_hvac_mode(self.coordinator.data)

    @property
    def hvac_action(self) -> HVACAction | None:
        if not self.coordinator.data:
            return None
        return _cu_hvac_action(self.coordinator.data)

    @property
    def target_temperature(self) -> float | None:
        if not self.coordinator.data:
            return None
        raw = _get(self.coordinator.data, "t_can", "tc", default=None)
        if raw is None or raw == 0:
            return None
        try:
            return int(raw) / 10.0
        except (TypeError, ValueError):
            return None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_turn_off()
        else:
            await self.coordinator.async_set_mode(_HVAC_MODE_TO_OP_MODE[hvac_mode])

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.coordinator.async_set_canal_temperature(temp)

    async def async_turn_on(self) -> None:
        await self.coordinator.async_turn_on()

    async def async_turn_off(self) -> None:
        await self.coordinator.async_turn_off()


class Polaris5XZoneClimate(CoordinatorEntity[Polaris5XCoordinator], ClimateEntity):
    """Climate entity for a single Polaris 5X zone (temperature + on/off)."""

    _attr_has_entity_name = True
    _attr_hvac_modes = _ALL_HVAC_MODES
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 16.0
    _attr_max_temp = 30.0

    def __init__(self, coordinator: Polaris5XCoordinator, zone: dict) -> None:
        super().__init__(coordinator)
        ip = coordinator.config_entry.data["ip"]

        self._zone_id: int = zone["id_zona"]
        self._zone_name: str = zone["name"]
        self._has_fan: bool = zone.get("has_fan", False)

        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        if self._has_fan:
            features |= ClimateEntityFeature.FAN_MODE
        self._attr_supported_features = features

        self._attr_unique_id = f"{ip}_zone_{self._zone_id}"
        self._attr_name = self._zone_name
        self._attr_device_info = _device_info(coordinator)

    def _zone_data(self) -> dict:
        zones = (self.coordinator.data or {}).get("zone", [])
        return next((z for z in zones if _zone_id(z) == self._zone_id), {})

    @property
    def hvac_mode(self) -> HVACMode | None:
        if not self.coordinator.data:
            return None
        zone = self._zone_data()
        if _get(zone, "is_off", "off") == 1:
            return HVACMode.OFF
        return _cu_hvac_mode(self.coordinator.data)

    @property
    def hvac_action(self) -> HVACAction | None:
        if not self.coordinator.data:
            return None
        zone = self._zone_data()
        if _get(zone, "is_off", "off") == 1:
            return HVACAction.OFF
        return _cu_hvac_action(self.coordinator.data)

    @property
    def current_temperature(self) -> float | None:
        from tecnosystemi_unofficial.devices import Polaris5XDevice

        zone = self._zone_data()
        return Polaris5XDevice.parse_zone_temperature(zone.get("t"))

    @property
    def target_temperature(self) -> float | None:
        zone = self._zone_data()
        raw = zone.get("t_set") or zone.get("ts")
        if raw is None:
            return None
        try:
            return int(raw) / 10.0
        except (TypeError, ValueError):
            return None

    @property
    def fan_modes(self) -> list[str] | None:
        return ["1", "2", "3"] if self._has_fan else None

    @property
    def fan_mode(self) -> str | None:
        if not self._has_fan:
            return None
        zone = self._zone_data()
        # fan_set (full) / w (ridotto) for current setpoint
        fan = zone.get("fan_set", zone.get("w"))
        return str(fan) if fan is not None and fan != -1 else None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        zone = self._zone_data()
        current_temp = self.target_temperature or 20.0
        is_crono = int(_get(zone, "is_crono", default=0))
        fan_set = zone.get("fan_set", zone.get("w")) if self._has_fan else None

        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_update_zone(
                zone_id=self._zone_id,
                name=self._zone_name,
                is_off=1,
                set_temp=current_temp,
                is_crono=is_crono,
                fan_set=fan_set,
            )
        else:
            await self.coordinator.async_set_mode(_HVAC_MODE_TO_OP_MODE[hvac_mode])
            await self.coordinator.async_update_zone(
                zone_id=self._zone_id,
                name=self._zone_name,
                is_off=0,
                set_temp=current_temp,
                is_crono=is_crono,
                fan_set=fan_set,
            )

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        zone = self._zone_data()
        await self.coordinator.async_update_zone(
            zone_id=self._zone_id,
            name=self._zone_name,
            is_off=int(_get(zone, "is_off", "off", default=0)),
            set_temp=temp,
            is_crono=int(_get(zone, "is_crono", default=0)),
            fan_set=zone.get("fan_set") if self._has_fan else None,
        )

    async def async_turn_on(self) -> None:
        zone = self._zone_data()
        await self.coordinator.async_update_zone(
            zone_id=self._zone_id,
            name=self._zone_name,
            is_off=0,
            set_temp=self.target_temperature or 20.0,
            is_crono=int(_get(zone, "is_crono", default=0)),
            fan_set=zone.get("fan_set") if self._has_fan else None,
        )

    async def async_turn_off(self) -> None:
        zone = self._zone_data()
        await self.coordinator.async_update_zone(
            zone_id=self._zone_id,
            name=self._zone_name,
            is_off=1,
            set_temp=self.target_temperature or 20.0,
            is_crono=int(_get(zone, "is_crono", default=0)),
            fan_set=zone.get("fan_set") if self._has_fan else None,
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        if not self._has_fan:
            return
        zone = self._zone_data()
        await self.coordinator.async_update_zone(
            zone_id=self._zone_id,
            name=self._zone_name,
            is_off=int(_get(zone, "is_off", "off", default=0)),
            set_temp=self.target_temperature or 20.0,
            is_crono=int(_get(zone, "is_crono", default=0)),
            fan_set=int(fan_mode),
        )
