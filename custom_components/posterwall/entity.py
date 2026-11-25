"""Base entity of a wall."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_UPDATE, VERSION
from .wall import PosterWall

MODELS = {"media": "Home Assistant media", "immich": "Immich", "synology": "Synology Photos"}


class WallEntity(Entity):
    """Belongs to the device of a wall and follows its changes."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, wall: PosterWall, key: str) -> None:
        self.wall = wall
        self.key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{wall.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, wall.entry.entry_id)},
            name=wall.entry.title,
            manufacturer="PosterWall",
            model=MODELS.get(wall.source.kind, wall.source.kind),
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE.format(entry_id=self.wall.entry.entry_id), self.async_write_ha_state))


class SettingEntity(WallEntity):
    """A live setting of the wall."""

    @property
    def value(self):
        return self.wall.settings[self.key]
