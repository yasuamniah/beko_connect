"""On/off features of the air conditioner."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN
from .coordinator import BekoEntity

# (field, translation key, enabled by default)
SWITCHES = [
    ("acTurbo", "turbo", True),
    ("acSubAirClean", "air_clean", False),
    ("acSubAutoDrying", "auto_drying", False),
]


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        BekoSwitch(coordinator, eid, field, key, default)
        for eid in coordinator.data
        for field, key, default in SWITCHES
    )


class BekoSwitch(BekoEntity, SwitchEntity):
    def __init__(self, coordinator, endpoint_id: str, field: str,
                 translation_key: str, enabled_default: bool) -> None:
        super().__init__(coordinator, endpoint_id, field)
        self._field = field
        self._attr_translation_key = translation_key
        self._attr_entity_registry_enabled_default = enabled_default

    @property
    def is_on(self) -> bool | None:
        value = self.ep.get(self._field)
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.send(self._field, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.send(self._field, 0)
