"""Sensors: built-in temperature sensor, power, error code."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfPower, UnitOfTemperature
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import BekoEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for eid in coordinator.data:
        entities += [
            BekoTemperature(coordinator, eid),
            BekoPower(coordinator, eid),
            BekoErrorCode(coordinator, eid),
            BekoTemperatureUpdated(coordinator, eid),
        ]
    async_add_entities(entities)


class BekoTemperature(BekoEntity, SensorEntity):
    _attr_translation_key = "internal_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, endpoint_id: str) -> None:
        super().__init__(coordinator, endpoint_id, "temperature")

    @property
    def native_value(self):
        return self.ep.get("temperature")


class BekoPower(BekoEntity, SensorEntity):
    _attr_translation_key = "power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, endpoint_id: str) -> None:
        super().__init__(coordinator, endpoint_id, "power")

    @property
    def native_value(self):
        # The cloud keeps the last reading when the unit is switched off.
        if not self.ep.get("acPower"):
            return 0
        return self.ep.get("acInstantPower")


class BekoErrorCode(BekoEntity, SensorEntity):
    _attr_translation_key = "error_code"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, endpoint_id: str) -> None:
        super().__init__(coordinator, endpoint_id, "error_code")

    @property
    def native_value(self):
        return self.ep.get("acErrorCode")


class BekoTemperatureUpdated(BekoEntity, SensorEntity):
    """When the unit last reported a temperature (it stops while switched off)."""

    _attr_translation_key = "temperature_updated"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, endpoint_id: str) -> None:
        super().__init__(coordinator, endpoint_id, "temperature_updated")

    @property
    def native_value(self):
        value = self.ep.get("lastTemperatureUpdate")
        return dt_util.parse_datetime(value) if value else None
