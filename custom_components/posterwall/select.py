"""Album, photo size, effect, background and night mode."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PosterWallConfigEntry
from .const import BACKGROUNDS, EFFECTS, NIGHT_MODES, SIZES
from .entity import SettingEntity

PARALLEL_UPDATES = 0

CHOICES = {"size": SIZES, "effect": EFFECTS, "background": BACKGROUNDS, "night_mode": NIGHT_MODES}


async def async_setup_entry(hass: HomeAssistant, entry: PosterWallConfigEntry, add: AddConfigEntryEntitiesCallback) -> None:
    wall = entry.runtime_data
    add([AlbumSelect(wall, "album"), *(ChoiceSelect(wall, key) for key in CHOICES)])


class ChoiceSelect(SettingEntity, SelectEntity):
    """A fixed choice (translated)."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, wall, key: str) -> None:
        super().__init__(wall, key)
        self._attr_options = list(CHOICES[key])

    @property
    def current_option(self) -> str:
        return str(self.value)

    async def async_select_option(self, option: str) -> None:
        await self.wall.async_set(self.key, option)


class AlbumSelect(SettingEntity, SelectEntity):
    """Which folder or album the wall shows (names come from the source)."""

    def _titles(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for key, title in self.wall.album_options():
            name, n = title, 2
            while name in out:
                name, n = f"{title} ({n})", n + 1
            out[name] = key
        return out

    @property
    def options(self) -> list[str]:
        return list(self._titles())

    @property
    def current_option(self) -> str | None:
        for title, key in self._titles().items():
            if key == self.value:
                return title
        return None

    async def async_select_option(self, option: str) -> None:
        await self.wall.async_set(self.key, self._titles()[option])
