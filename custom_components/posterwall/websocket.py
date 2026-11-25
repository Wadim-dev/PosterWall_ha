"""Websocket API for the card and the panel."""

from __future__ import annotations

from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import voluptuous as vol

from .const import (
    BACKGROUNDS,
    CONF_CALENDARS,
    CONF_DEVICES,
    CONF_EVENT_DAYS,
    CONF_EVENTS,
    CONF_WEATHER,
    DOMAIN,
    EFFECTS,
    NIGHT_MODES,
    SETTINGS_DEFAULTS,
    SIGNAL_UPDATE,
    SIZES,
)
from .devices import async_set_keep, async_show, cast_ready, dashboard_path, find_screens


@callback
def async_register(hass: HomeAssistant) -> None:
    for cmd in (ws_walls, ws_subscribe, ws_next, ws_set, ws_options, ws_refresh, ws_screens, ws_show, ws_keep):
        websocket_api.async_register_command(hass, cmd)


def _wall(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> Any:
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        connection.send_error(msg["id"], "not_found", "This wall does not exist or is not loaded")
        return None
    return entry.runtime_data


@websocket_api.websocket_command({vol.Required("type"): "posterwall/walls"})
@callback
def ws_walls(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
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


@websocket_api.websocket_command({vol.Required("type"): "posterwall/subscribe", vol.Required("entry_id"): str})
@callback
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Settings of a wall now and after every change."""
    if (wall := _wall(hass, connection, msg)) is None:
        return

    @callback
    def send() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], wall.payload()))

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(hass, SIGNAL_UPDATE.format(entry_id=msg["entry_id"]), send)
    connection.send_result(msg["id"])
    send()


@websocket_api.websocket_command({
    vol.Required("type"): "posterwall/next",
    vol.Required("entry_id"): str,
    vol.Optional("count", default=1): vol.All(int, vol.Range(min=1, max=4)),
})
@websocket_api.async_response
async def ws_next(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
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


@websocket_api.websocket_command({
    vol.Required("type"): "posterwall/set",
    vol.Required("entry_id"): str,
    vol.Required("key"): vol.In(list(SETTINGS_DEFAULTS)),
    vol.Required("value"): vol.Any(str, int, float, bool),
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_set(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
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


@websocket_api.websocket_command({
    vol.Required("type"): "posterwall/options",
    vol.Required("entry_id"): str,
    vol.Optional(CONF_WEATHER): vol.Any(None, str),
    vol.Optional(CONF_CALENDARS): [str],
    vol.Optional(CONF_EVENTS): vol.All(int, vol.Range(min=1, max=10)),
    vol.Optional(CONF_EVENT_DAYS): vol.All(int, vol.Range(min=1, max=31)),
})
@websocket_api.require_admin
@callback
def ws_options(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Weather and calendars from the panel."""
    if (wall := _wall(hass, connection, msg)) is None:
        return
    changes = {k: msg[k] for k in (CONF_WEATHER, CONF_CALENDARS, CONF_EVENTS, CONF_EVENT_DAYS) if k in msg}
    if changes.get(CONF_WEATHER) == "":
        changes[CONF_WEATHER] = None
    hass.config_entries.async_update_entry(wall.entry, options={**wall.entry.options, **changes})
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): "posterwall/refresh", vol.Required("entry_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_refresh(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    if (wall := _wall(hass, connection, msg)) is None:
        return
    await wall.async_refresh()
    connection.send_result(msg["id"], {"photos": len(wall.photos), "error": wall.error})


@websocket_api.websocket_command({vol.Required("type"): "posterwall/screens"})
@websocket_api.require_admin
@callback
def ws_screens(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
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


@websocket_api.websocket_command({
    vol.Required("type"): "posterwall/show",
    vol.Required("entry_id"): str,
    vol.Required("screen"): str,
    vol.Optional("keep", default=False): bool,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_show(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
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


@websocket_api.websocket_command({
    vol.Required("type"): "posterwall/keep",
    vol.Required("entry_id"): str,
    vol.Required("screen"): str,
    vol.Required("keep"): bool,
})
@websocket_api.require_admin
@callback
def ws_keep(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
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
