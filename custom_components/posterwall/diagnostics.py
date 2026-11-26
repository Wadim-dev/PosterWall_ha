"""Diagnostics without secrets."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import PosterWallConfigEntry
from .const import CONF_API_KEY, CONF_DEVICE_TOKEN, CONF_PASSWORD, CONF_URL, CONF_USERNAME

REDACT = {CONF_API_KEY, CONF_PASSWORD, CONF_DEVICE_TOKEN, CONF_USERNAME, CONF_URL}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: PosterWallConfigEntry) -> dict[str, Any]:
    wall = entry.runtime_data
    dated = sum(1 for p in wall.photos if p.date and len(p.date) == 10)
    return {
        "data": async_redact_data(dict(entry.data), REDACT),
        "options": dict(entry.options),
        "settings": dict(wall.settings),
        "albums": len(wall.albums),
        "photos": len(wall.photos),
        "photos_with_date": dated,
        "favorites": sum(1 for p in wall.photos if p.favorite),
        "error": wall.error,
        "last_refresh": wall.last_refresh.isoformat() if wall.last_refresh else None,
        "screens_alive": {c: t.isoformat() for c, t in wall.screens_alive.items()},
        "watchdog": {"step": wall.watchdog.step, "restarts": wall.watchdog.restarts} if wall.watchdog else None,
    }
