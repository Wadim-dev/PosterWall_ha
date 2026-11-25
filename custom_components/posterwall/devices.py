"""Screens a wall can be sent to, found automatically.

Only public actions of the other integrations are used:
- Google Cast (Nest Hub, Chromecast, Google TV, Cast TVs): cast.show_lovelace_view
- Fully Kiosk Browser: fully_kiosk.load_url (and set_config startURL to keep it)
- Browser Mod: browser_mod.navigate
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, STATE_OFF
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import CONF_DEVICES, DOMAIN

_LOGGER = logging.getLogger(__name__)

VIEW_PATH = "wall"
KIND_CAST = "cast"
KIND_FULLY = "fully_kiosk"
KIND_BROWSER_MOD = "browser_mod"


@dataclass(slots=True)
class Screen:
    """A screen that can show a wall."""

    id: str  # "<kind>:<entity_id or device_id>"
    kind: str
    name: str
    state: str | None
    area: str | None
    model: str | None

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "name": self.name, "state": self.state, "area": self.area, "model": self.model}


def dashboard_path(entry_id: str) -> str:
    """URL path of the dashboard that shows a wall (created by the PosterWall panel)."""
    return f"posterwall-{entry_id[:8].lower()}"


def cast_ready(hass: HomeAssistant) -> bool:
    """Google Cast needs Home Assistant reachable over HTTPS."""
    try:
        get_url(hass, require_ssl=True, prefer_external=True)
    except NoURLAvailableError:
        return False
    return True


def find_screens(hass: HomeAssistant) -> list[Screen]:
    """Every screen of the supported integrations."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)

    def area_name(area_id: str | None) -> str | None:
        return a.name if area_id and (a := area_reg.async_get_area(area_id)) else None

    screens: list[Screen] = []
    if "cast" in hass.config.components:
        for ent in ent_reg.entities.values():
            if ent.platform != "cast" or ent.domain != "media_player" or ent.disabled:
                continue
            dev = dev_reg.async_get(ent.device_id) if ent.device_id else None
            state = hass.states.get(ent.entity_id)
            name = (state.name if state else None) or ent.name or ent.original_name or ent.entity_id
            screens.append(Screen(f"{KIND_CAST}:{ent.entity_id}", KIND_CAST, name, state.state if state else None,
                                  area_name(ent.area_id or (dev.area_id if dev else None)), dev.model if dev else None))
    for kind in (KIND_FULLY, KIND_BROWSER_MOD):
        if kind not in hass.config.components:
            continue
        for dev in dev_reg.devices.values():
            if dev.disabled or not any(i[0] == kind for i in dev.identifiers):
                continue
            screens.append(Screen(f"{kind}:{dev.id}", kind, dev.name_by_user or dev.name or dev.id, None,
                                  area_name(dev.area_id), dev.model))
    screens.sort(key=lambda s: (s.area or "~", s.name.lower()))
    return screens


def _wall_url(hass: HomeAssistant, entry_id: str) -> str:
    try:
        base = get_url(hass, prefer_external=False)
    except NoURLAvailableError as err:
        raise HomeAssistantError("No URL of Home Assistant is known (Settings → System → Network)") from err
    return f"{base}/{dashboard_path(entry_id)}/{VIEW_PATH}"


async def async_show(hass: HomeAssistant, entry_id: str, screen_id: str, *, keep: bool = False) -> None:
    """Send a wall to a screen."""
    kind, _, target = screen_id.partition(":")
    if not target:
        raise ServiceValidationError("Unknown screen", translation_domain=DOMAIN, translation_key="unknown_screen")
    path = dashboard_path(entry_id)
    if kind == KIND_CAST:
        await hass.services.async_call("cast", "show_lovelace_view",
                                       {"entity_id": target, "dashboard_path": path, "view_path": VIEW_PATH}, blocking=True)
    elif kind == KIND_FULLY:
        url = _wall_url(hass, entry_id)
        if keep:
            await hass.services.async_call("fully_kiosk", "set_config", {"device_id": target, "key": "startURL", "value": url},
                                           blocking=True)
        await hass.services.async_call("fully_kiosk", "load_url", {"device_id": target, "url": url}, blocking=True)
    elif kind == KIND_BROWSER_MOD:
        dev = dr.async_get(hass).async_get(target)
        browser_ids = [i[1] for i in dev.identifiers if i[0] == KIND_BROWSER_MOD] if dev else []
        if not browser_ids:
            raise ServiceValidationError("Unknown screen", translation_domain=DOMAIN, translation_key="unknown_screen")
        await hass.services.async_call("browser_mod", "navigate", {"path": f"/{path}/{VIEW_PATH}", "browser_id": browser_ids},
                                       blocking=True)
    else:
        raise ServiceValidationError("Unknown screen", translation_domain=DOMAIN, translation_key="unknown_screen")


def needs_restart(hass: HomeAssistant, screen_id: str) -> bool:
    """A kept Cast screen shows nothing anymore (never interrupts music or a video)."""
    kind, _, target = screen_id.partition(":")
    if kind != KIND_CAST:
        return False
    state = hass.states.get(target)
    return state is not None and state.state in (STATE_OFF, STATE_IDLE)


@callback
def async_set_keep(hass: HomeAssistant, entry: ConfigEntry, screen: str, keep: bool) -> None:
    """Remember (or forget) a screen that always shows this wall."""
    devices: dict[str, Any] = dict(entry.options.get(CONF_DEVICES) or {})
    if keep:
        devices[screen] = {"keep": True}
    else:
        devices.pop(screen, None)
    if devices != (entry.options.get(CONF_DEVICES) or {}):
        hass.config_entries.async_update_entry(entry, options={**entry.options, CONF_DEVICES: devices})
