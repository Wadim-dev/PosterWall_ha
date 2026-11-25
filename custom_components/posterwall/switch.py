"""Clock, weather, events, caption, favourites and "on this day"."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PosterWallConfigEntry
from .entity import SettingEntity

PARALLEL_UPDATES = 0

SWITCHES = ["clock", "weather", "events", "caption", "favorites", "on_this_day"]


async def async_setup_entry(hass: HomeAssistant, entry: PosterWallConfigEntry, add: AddConfigEntryEntitiesCallback) -> None:
    wall = entry.runtime_data
    add(WallSwitch(wall, key) for key in SWITCHES if key != "favorites" or wall.source.has_favorites)


class WallSwitch(SettingEntity, SwitchEntity):
    """An on/off setting."""

    _attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool:
        return bool(self.value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.wall.async_set(self.key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.wall.async_set(self.key, False)
