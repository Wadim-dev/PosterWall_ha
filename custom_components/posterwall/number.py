"""Interval, number of photos and night brightness."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PosterWallConfigEntry
from .entity import SettingEntity
from .wall import PosterWall

PARALLEL_UPDATES = 0

NUMBERS = {
    "interval": (5, 600, 1, UnitOfTime.SECONDS, NumberMode.BOX),
    "count": (1, 12, 1, None, NumberMode.SLIDER),
    "night_brightness": (5, 90, 5, PERCENTAGE, NumberMode.SLIDER),
}


async def async_setup_entry(hass: HomeAssistant, entry: PosterWallConfigEntry, add: AddConfigEntryEntitiesCallback) -> None:
    add(WallNumber(entry.runtime_data, key) for key in NUMBERS)


class WallNumber(SettingEntity, NumberEntity):
    """A number setting."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, wall: PosterWall, key: str) -> None:
        super().__init__(wall, key)
        lo, hi, step, unit, mode = NUMBERS[key]
        self._attr_native_min_value, self._attr_native_max_value, self._attr_native_step = lo, hi, step
        self._attr_native_unit_of_measurement = unit
        self._attr_mode = mode

    @property
    def native_value(self) -> float:
        value: float = self.setting  # whole numbers stay whole ("15", not "15.0")
        return value

    async def async_set_native_value(self, value: float) -> None:
        await self.wall.async_set(self.key, int(value))
