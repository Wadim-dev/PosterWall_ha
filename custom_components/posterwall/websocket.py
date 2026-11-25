"""Websocket API for the card and the panel."""

from __future__ import annotations

from typing import Any

from homeassistant.components.websocket_api import async_register_command
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.decorators import async_response, require_admin, websocket_command
from homeassistant.components.websocket_api.messages import event_message
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import voluptuous as vol

from .browse import async_chain, async_open
from .const import (
    ALBUM_ALL,
    BACKGROUNDS,
    CONF_CALENDARS,
    CONF_DEVICES,
    CONF_EVENT_DAYS,
    CONF_EVENTS,
    CONF_FOLDER,
    CONF_FOLDER_TITLE,
    CONF_WEATHER,
    DOMAIN,
    EFFECTS,
    NIGHT_MODES,
    SETTINGS_DEFAULTS,
    SIGNAL_UPDATE,
    SIZES,
    SOURCE_MEDIA,
)
from .devices import async_set_keep, async_show, cast_ready, dashboard_path, find_screens


@callback
def async_register(hass: HomeAssistant) -> None:
    for cmd in (ws_walls, ws_subscribe, ws_next, ws_set, ws_options, ws_refresh, ws_screens, ws_show, ws_keep, ws_browse, ws_folder):
        async_register_command(hass, cmd)


def _wall(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> Any:
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        connection.send_error(msg["id"], "not_found", "This wall does not exist or is not loaded")
        return None
    return entry.runtime_data


@websocket_command({vol.Required("type"): "posterwall/walls"})
@callback
def ws_walls(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    """All walls (also those that could not start)."""
    walls = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            data = entry.runtime_data.payload()
        else:
            data = {"entry_id": entry.entry_id, "title": entry.title, "error": entry.reason or entry.state.value}
        data["dashboard"] = dashboard_path(entry.entry_id)
        data["state"] = entry.state.value
        walls.append(data)
    connection.send_result(msg["id"], walls)


@websocket_command({vol.Required("type"): "posterwall/subscribe", vol.Required("entry_id"): str})
@callback
def ws_subscribe(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    """Settings of a wall now and after every change."""
    if (wall := _wall(hass, connection, msg)) is None:
        return

    @callback
    def send() -> None:
        connection.send_message(event_message(msg["id"], wall.payload()))

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(hass, SIGNAL_UPDATE.format(entry_id=msg["entry_id"]), send)
    connection.send_result(msg["id"])
    send()


@websocket_command({
    vol.Required("type"): "posterwall/next",
    vol.Required("entry_id"): str,
    vol.Optional("count", default=1): vol.All(int, vol.Range(min=1, max=4)),
})
@async_response
async def ws_next(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    """The next photos to pin on the wall."""
    if (wall := _wall(hass, connection, msg)) is None:
        return
    connection.send_result(msg["id"], {"photos": await wall.async_next(msg["count"]), "total": len(wall.photos)})


def _valid(key: str, value: Any) -> bool:
    choices = {"size": SIZES, "effect": EFFECTS, "background": BACKGROUNDS, "night_mode": NIGHT_MODES}
    default = SETTINGS_DEFAULTS[key]
    if key in choices:
        return value in choices[key]
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int):
        limits = {"interval": (5, 600), "count": (1, 12), "night_brightness": (5, 90)}[key]
        return isinstance(value, int | float) and limits[0] <= value <= limits[1]
    if key in ("night_start", "night_end"):
        return isinstance(value, str) and len(value) >= 5 and value[2] == ":"
    return isinstance(value, str)


@websocket_command({
    vol.Required("type"): "posterwall/set",
    vol.Required("entry_id"): str,
    vol.Required("key"): vol.In(list(SETTINGS_DEFAULTS)),
    vol.Required("value"): vol.Any(str, int, float, bool),
})
@require_admin
@async_response
async def ws_set(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    """Change a live setting from the panel."""
    if (wall := _wall(hass, connection, msg)) is None:
        return
    key, value = msg["key"], msg["value"]
    if not _valid(key, value):
        connection.send_error(msg["id"], "invalid_format", f"{value!r} is not allowed for {key}")
        return
    if isinstance(SETTINGS_DEFAULTS[key], int) and not isinstance(SETTINGS_DEFAULTS[key], bool):
        value = int(value)
    if key in ("night_start", "night_end") and len(value) == 5:
        value += ":00"
    await wall.async_set(key, value)
    connection.send_result(msg["id"])


@websocket_command({
    vol.Required("type"): "posterwall/options",
    vol.Required("entry_id"): str,
    vol.Optional(CONF_WEATHER): vol.Any(None, str),
    vol.Optional(CONF_CALENDARS): [str],
    vol.Optional(CONF_EVENTS): vol.All(int, vol.Range(min=1, max=10)),
    vol.Optional(CONF_EVENT_DAYS): vol.All(int, vol.Range(min=1, max=31)),
})
@require_admin
@callback
def ws_options(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    """Weather and calendars from the panel."""
    if (wall := _wall(hass, connection, msg)) is None:
        return
    changes: dict[str, Any] = {k: msg[k] for k in (CONF_WEATHER, CONF_CALENDARS, CONF_EVENTS, CONF_EVENT_DAYS) if k in msg}
    if changes.get(CONF_WEATHER) == "":
        changes[CONF_WEATHER] = None
    hass.config_entries.async_update_entry(wall.entry, options={**wall.entry.options, **changes})
    connection.send_result(msg["id"])


@websocket_command({vol.Required("type"): "posterwall/refresh", vol.Required("entry_id"): str})
@require_admin
@async_response
async def ws_refresh(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    if (wall := _wall(hass, connection, msg)) is None:
        return
    await wall.async_refresh()
    connection.send_result(msg["id"], {"photos": len(wall.photos), "error": wall.error})


@websocket_command({vol.Required("type"): "posterwall/screens"})
@require_admin
@callback
def ws_screens(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    """Screens found in the house and which wall each one keeps showing."""
    kept: dict[str, str] = {}
    for entry in hass.config_entries.async_entries(DOMAIN):
        for screen, conf in (entry.options.get(CONF_DEVICES) or {}).items():
            if conf.get("keep"):
                kept[screen] = entry.entry_id
    connection.send_result(msg["id"], {
        "screens": [s.as_dict() for s in find_screens(hass)],
        "kept": kept,
        "cast_ready": cast_ready(hass),
        "integrations": {k: k in hass.config.components for k in ("cast", "fully_kiosk", "browser_mod")},
    })


@websocket_command({
    vol.Required("type"): "posterwall/show",
    vol.Required("entry_id"): str,
    vol.Required("screen"): str,
    vol.Optional("keep", default=False): bool,
})
@require_admin
@async_response
async def ws_show(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    """Show a wall on a screen now."""
    if (wall := _wall(hass, connection, msg)) is None:
        return
    try:
        await async_show(hass, wall.entry.entry_id, msg["screen"], keep=msg["keep"])
    except Exception as err:
        connection.send_error(msg["id"], "show_failed", str(err) or type(err).__name__)
        return
    if msg["keep"]:
        _release(hass, msg["screen"], wall.entry.entry_id)
        async_set_keep(hass, wall.entry, msg["screen"], True)
    connection.send_result(msg["id"])


@websocket_command({
    vol.Required("type"): "posterwall/keep",
    vol.Required("entry_id"): str,
    vol.Required("screen"): str,
    vol.Required("keep"): bool,
})
@require_admin
@callback
def ws_keep(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    """Turn "always show" on or off for a screen."""
    if (wall := _wall(hass, connection, msg)) is None:
        return
    if msg["keep"]:
        _release(hass, msg["screen"], wall.entry.entry_id)
    async_set_keep(hass, wall.entry, msg["screen"], msg["keep"])
    connection.send_result(msg["id"])


def _release(hass: HomeAssistant, screen: str, keep_on: str) -> None:
    """A screen keeps only one wall: forget it on every other wall."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id != keep_on and screen in (entry.options.get(CONF_DEVICES) or {}):
            async_set_keep(hass, entry, screen, False)


@websocket_command({
    vol.Required("type"): "posterwall/browse",
    vol.Required("entry_id"): str,
    vol.Optional("folder"): vol.Any(None, str),
})
@require_admin
@async_response
async def ws_browse(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    """One folder of the Home Assistant media browser, with the way to it (only walls of HA media).

    Without "folder" it opens the folder the wall shows now.
    """
    if (wall := _wall(hass, connection, msg)) is None:
        return
    if wall.source.kind != SOURCE_MEDIA:
        connection.send_error(msg["id"], "not_supported", "Only walls of Home Assistant media have folders")
        return
    root: str = wall.entry.data[CONF_FOLDER]
    album = wall.settings["album"]
    folder = msg["folder"] if "folder" in msg else (album if wall.source.in_root(album) else root)
    try:
        opened = await async_open(hass, folder)
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "browse_failed", str(err) or "The folder cannot be opened")
        return
    chain = await async_chain(hass, folder)
    connection.send_result(msg["id"], {
        "chain": [{"id": i, "title": t} for i, t in chain],
        "folder": opened.as_dict(),
        "root": root,
        "showing": album if wall.source.in_root(album) else root,
    })


@websocket_command({
    vol.Required("type"): "posterwall/folder",
    vol.Required("entry_id"): str,
    vol.Required("folder"): str,
})
@require_admin
@async_response
async def ws_folder(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    """Show the photos of a folder: below the wall's folder it is chosen like an album, anywhere else it
    becomes the wall's new folder (the wall starts again, settings and screens stay)."""
    if (wall := _wall(hass, connection, msg)) is None:
        return
    if wall.source.kind != SOURCE_MEDIA:
        connection.send_error(msg["id"], "not_supported", "Only walls of Home Assistant media have folders")
        return
    folder: str = msg["folder"]
    root: str = wall.entry.data[CONF_FOLDER]
    if folder == root:
        await wall.async_set("album", ALBUM_ALL)
    elif wall.source.in_root(folder):
        await wall.async_set("album", folder)
    else:
        try:
            await async_open(hass, folder)
        except HomeAssistantError as err:
            connection.send_error(msg["id"], "browse_failed", str(err) or "The folder cannot be opened")
            return
        chain = await async_chain(hass, folder)
        wall.settings["album"] = ALBUM_ALL
        hass.config_entries.async_update_entry(wall.entry, data={
            **wall.entry.data, CONF_FOLDER: folder, CONF_FOLDER_TITLE: " / ".join(t for _, t in chain[1:]) or folder})
        hass.config_entries.async_schedule_reload(wall.entry.entry_id)
    connection.send_result(msg["id"])
