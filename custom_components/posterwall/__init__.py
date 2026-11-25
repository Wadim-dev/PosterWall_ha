"""PosterWall – your photos as a pinboard on any screen.

- Every wall is a config entry with its own photo source (Home Assistant media,
  Immich or Synology Photos), live settings as entities and a ready card.
- The sidebar panel "PosterWall" shows a live preview, all settings and the screens
  found in the house (Google Cast, Fully Kiosk, Browser Mod) with a button to show
  the wall there.
"""

from __future__ import annotations

from datetime import timedelta
import logging
import os
from typing import Any

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from . import websocket
from .const import CONF_DEVICE_TOKEN, CONF_DEVICES, DOMAIN, PANEL_ELEMENT, PANEL_FILE, PANEL_ICON, PANEL_URL, STATIC_URL, VERSION
from .devices import async_set_keep, async_show, needs_restart
from .sources import AuthError, SourceError, create_source
from .view import PhotoView
from .wall import PosterWall

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON, Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.SWITCH, Platform.TIME]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type PosterWallConfigEntry = ConfigEntry[PosterWall]

SHOW_SCHEMA = vol.Schema({
    vol.Required("config_entry_id"): cv.string,
    vol.Required("screen"): cv.string,
    vol.Optional("keep", default=False): cv.boolean,
})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Card, panel, websocket API and the show action."""
    hass.data.setdefault(DOMAIN, {})
    websocket.async_register(hass)
    if "http" in hass.config.components:
        hass.http.register_view(PhotoView())
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, os.path.join(os.path.dirname(__file__), "frontend"), cache_headers=False)]
        )

    async def show(call: ServiceCall) -> None:
        entry = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError("Unknown wall", translation_domain=DOMAIN, translation_key="unknown_wall")
        await async_show(hass, entry.entry_id, call.data["screen"], keep=call.data["keep"])
        async_set_keep(hass, entry, call.data["screen"], call.data["keep"])

    async_register_admin_service(hass, DOMAIN, "show", show, SHOW_SCHEMA)
    return True


async def _panel(hass: HomeAssistant) -> None:
    if PANEL_URL in hass.data.get(frontend.DATA_PANELS, {}):
        return
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL,
        webcomponent_name=PANEL_ELEMENT,
        sidebar_title="PosterWall",
        sidebar_icon=PANEL_ICON,
        module_url=f"{STATIC_URL}/{PANEL_FILE}?v={VERSION}",
        require_admin=True,
        config={},
    )


async def async_setup_entry(hass: HomeAssistant, entry: PosterWallConfigEntry) -> bool:
    """Start one wall."""
    source = create_source(hass, dict(entry.data))
    wall = PosterWall(hass, entry, source)
    try:
        await wall.async_start()
    except AuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SourceError as err:
        raise ConfigEntryNotReady(str(err)) from err
    if source.device_token and source.device_token != entry.data.get(CONF_DEVICE_TOKEN):
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_DEVICE_TOKEN: source.device_token})
    entry.runtime_data = wall
    entry.async_on_unload(wall.async_stop)
    entry.async_create_background_task(hass, wall.async_refresh(), f"{DOMAIN} first read")

    async def keep_alive(_now: Any) -> None:
        for screen, conf in (entry.options.get(CONF_DEVICES) or {}).items():
            if conf.get("keep") and needs_restart(hass, screen):
                try:
                    await async_show(hass, entry.entry_id, screen)
                except Exception as err:
                    _LOGGER.debug("Screen %s could not be started again: %s", screen, err)

    entry.async_on_unload(async_track_time_interval(hass, keep_alive, timedelta(minutes=2)))
    entry.async_on_unload(entry.add_update_listener(_options_changed))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if "frontend" in hass.config.components:
        await _panel(hass)
    return True


async def _options_changed(hass: HomeAssistant, entry: PosterWallConfigEntry) -> None:
    """Weather, calendars or screens changed: tell the displays."""
    entry.runtime_data.async_notify()


async def async_unload_entry(hass: HomeAssistant, entry: PosterWallConfigEntry) -> bool:
    """Stop one wall; the panel goes when the last wall goes."""
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.store.async_save(dict(entry.runtime_data.settings))
    others = [e for e in hass.config_entries.async_loaded_entries(DOMAIN) if e.entry_id != entry.entry_id]
    if ok and not others and "frontend" in hass.config.components:
        frontend.async_remove_panel(hass, PANEL_URL, warn_if_unknown=False)
    return ok


async def async_remove_entry(hass: HomeAssistant, entry: PosterWallConfigEntry) -> None:
    """Delete the stored settings of a removed wall."""
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()
