"""Read the photos again."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PosterWallConfigEntry
from .entity import WallEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: PosterWallConfigEntry, add: AddConfigEntryEntitiesCallback) -> None:
    add([RefreshButton(entry.runtime_data, "refresh")])


class RefreshButton(WallEntity, ButtonEntity):
    """Read the folder or album again (new photos appear without waiting)."""

    _attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        await self.wall.async_refresh()
