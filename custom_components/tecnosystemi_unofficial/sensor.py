"""Sensor entities for Tecnosistemi VMC devices."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODE_LED_COLORS
from .coordinator import TecnosystemiCoordinator


@dataclass(frozen=True)
class TecnosistemiSensorDescription(SensorEntityDescription):
    """Description for a Tecnosistemi sensor, including the state dict key."""

    state_key: str = ""


SENSOR_DESCRIPTIONS: tuple[TecnosistemiSensorDescription, ...] = (
    TecnosistemiSensorDescription(
        key="amb_temp",
        state_key="AMB_tmpr",
        name="Ambient Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
    TecnosistemiSensorDescription(
        key="ext_temp",
        state_key="EXT_tmpr",
        name="External Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
    TecnosistemiSensorDescription(
        key="humidity",
        state_key="umd",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TecnosystemiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            *(
                TecnosistemiSensor(coordinator, description)
                for description in SENSOR_DESCRIPTIONS
            ),
            TecnosistemiLedColorSensor(coordinator),
        ]
    )


class TecnosistemiSensor(CoordinatorEntity[TecnosystemiCoordinator], SensorEntity):
    """A sensor entity that reads one field from the device state."""

    entity_description: TecnosistemiSensorDescription

    def __init__(
        self,
        coordinator: TecnosystemiCoordinator,
        description: TecnosistemiSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description

        ip = coordinator.config_entry.data["ip"]
        serial = coordinator.config_entry.data.get("serial", ip)
        info = coordinator.device_info_data

        self._attr_unique_id = f"{serial}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=info.get("name") or ip,
            manufacturer="Tecnosistemi S.r.l.",
            model="Pico",
            sw_version=info.get("fw_ver"),
            serial_number=info.get("ser"),
        )

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.state_key)


class TecnosistemiLedColorSensor(
    CoordinatorEntity[TecnosystemiCoordinator], SensorEntity
):
    """Sensor that exposes the LED color for the current operating mode."""

    _attr_has_entity_name = True
    _attr_name = "LED Color"
    _attr_icon = "mdi:led-on"

    def __init__(self, coordinator: TecnosystemiCoordinator) -> None:
        super().__init__(coordinator)
        ip = coordinator.config_entry.data["ip"]
        serial = coordinator.config_entry.data.get("serial", ip)
        info = coordinator.device_info_data

        self._attr_unique_id = f"{serial}_led_color"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=info.get("name") or ip,
            manufacturer="Tecnosistemi S.r.l.",
            model="Pico",
            sw_version=info.get("fw_ver"),
            serial_number=info.get("ser"),
        )

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        mode = self.coordinator.data.get("mod")
        if mode is None:
            return None
        color = MODE_LED_COLORS.get(mode)
        return color[0] if color else None

    @property
    def extra_state_attributes(self) -> dict | None:
        if not self.coordinator.data:
            return None
        mode = self.coordinator.data.get("mod")
        if mode is None:
            return None
        color = MODE_LED_COLORS.get(mode)
        if color is None:
            return None
        return {"led_color_hex": color[1]}
