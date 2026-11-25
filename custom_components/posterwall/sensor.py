"""Number of photos and time of the last read."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PosterWallConfigEntry
from .entity import WallEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: PosterWallConfigEntry, add: AddConfigEntryEntitiesCallback) -> None:
    wall = entry.runtime_data
    add([PhotoCount(wall, "photos"), LastRead(wall, "last_read")])


class PhotoCount(WallEntity, SensorEntity):
    """Photos the wall can show."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        return len(self.wall.photos)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"reading": self.wall.loading, "error": self.wall.error}


class LastRead(WallEntity, SensorEntity):
    """When the photos were read last."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> datetime | None:
        return self.wall.last_refresh
