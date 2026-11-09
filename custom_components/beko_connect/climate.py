"""Air conditioner as a Home Assistant climate entity."""
from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .const import DOMAIN, FAN_TO_VALUE, POWER_ON_DELAY
from .coordinator import BekoEntity

# acMode values found in the Beko Connect app code.
ACMODE_TO_HVAC = {
    0: HVACMode.COOL,
    4: HVACMode.HEAT,
    1: HVACMode.DRY,
    2: HVACMode.FAN_ONLY,
    6: HVACMode.AUTO,
}
HVAC_TO_ACMODE = {v: k for k, v in ACMODE_TO_HVAC.items()}
VALUE_TO_FAN = {v: k for k, v in FAN_TO_VALUE.items()}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(BekoClimate(coordinator, eid) for eid in coordinator.data)


class BekoClimate(BekoEntity, ClimateEntity):
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_max_temp = 30
    _attr_hvac_modes = [
        HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT,
        HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.AUTO,
    ]
    _attr_fan_modes = list(FAN_TO_VALUE)
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator, endpoint_id: str) -> None:
        super().__init__(coordinator, endpoint_id)

    @property
    def min_temp(self) -> float:
        return 16 if self.hvac_mode == HVACMode.HEAT else 18

    @property
    def current_temperature(self) -> float | None:
        return self.ep.get("temperature")

    @property
    def target_temperature(self) -> float | None:
        return self.ep.get("targetTemperature")

    @property
    def hvac_mode(self) -> HVACMode | None:
        if not self.ep.get("acPower"):
            return HVACMode.OFF
        return ACMODE_TO_HVAC.get(self.ep.get("acMode"))

    @property
    def fan_mode(self) -> str | None:
        return VALUE_TO_FAN.get(self.ep.get("acFanSpeed"))

    async def async_turn_on(self) -> None:
        await self.send("acPower", 1)

    async def async_turn_off(self) -> None:
        await self.send("acPower", 0)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.send("acPower", 0)
            return
        if not self.ep.get("acPower"):
            await self.send("acPower", 1)
            await asyncio.sleep(POWER_ON_DELAY)
        if self.hvac_mode != hvac_mode:
            await self.send("acMode", HVAC_TO_ACMODE[hvac_mode])

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_set_hvac_mode(mode)
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            value = int(round(min(max(temp, self.min_temp), self.max_temp)))
            await self.send("targetTemperature", value)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        await self.send("acFanSpeed", FAN_TO_VALUE[fan_mode])
