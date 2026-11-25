"""Start and end of the night."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PosterWallConfigEntry
from .entity import SettingEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: PosterWallConfigEntry, add: AddConfigEntryEntitiesCallback) -> None:
    add(WallTime(entry.runtime_data, key) for key in ("night_start", "night_end"))


class WallTime(SettingEntity, TimeEntity):
    """A time of day."""

    _attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self) -> time:
        return time.fromisoformat(str(self.value))

    async def async_set_value(self, value: time) -> None:
        await self.wall.async_set(self.key, value.strftime("%H:%M:%S"))
