"""Read-only status flags."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import DOMAIN
from .coordinator import BekoEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(BekoDisplayOff(coordinator, eid) for eid in coordinator.data)


class BekoDisplayOff(BekoEntity, BinarySensorEntity):
    """The cloud reports the display-light state, but commands sent from here
    do not reach the unit (the app itself never sends this one), so this is
    read-only."""

    _attr_translation_key = "display_off"

    def __init__(self, coordinator, endpoint_id: str) -> None:
        super().__init__(coordinator, endpoint_id, "acLightsOff")

    @property
    def is_on(self) -> bool | None:
        value = self.ep.get("acLightsOff")
        return None if value is None else bool(value)
