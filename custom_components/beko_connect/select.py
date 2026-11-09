"""Air-direction selectors (raw values from the app)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity

from .const import DOMAIN, HORIZONTAL_SWING, VERTICAL_SWING
from .coordinator import BekoEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for eid in coordinator.data:
        entities += [
            BekoSwingSelect(coordinator, eid, "acVerticalSwing",
                            "swing_vertical", VERTICAL_SWING),
            BekoSwingSelect(coordinator, eid, "acHorizontalSwing",
                            "swing_horizontal", HORIZONTAL_SWING),
        ]
    async_add_entities(entities)


class BekoSwingSelect(BekoEntity, SelectEntity):
    def __init__(self, coordinator, endpoint_id: str, field: str,
                 translation_key: str, options: dict[str, int]) -> None:
        super().__init__(coordinator, endpoint_id, field)
        self._field = field
        self._to_value = options
        self._to_option = {v: k for k, v in options.items()}
        self._attr_translation_key = translation_key
        self._attr_options = list(options)

    @property
    def current_option(self) -> str | None:
        return self._to_option.get(self.ep.get(self._field))

    async def async_select_option(self, option: str) -> None:
        await self.send(self._field, self._to_value[option])
