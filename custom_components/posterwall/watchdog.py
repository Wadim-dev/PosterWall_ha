"""Keeps the screens of a wall running: a display page that hangs is loaded again by itself.

Every display page reports when it pinned a photo (or sleeps at night). When fewer pages report
than kept screens are on, the pages are told to load again; if that does not help, the screens
are restarted (Echo: dashboard closed and opened, Fully Kiosk: page loaded again).
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.util import dt as dt_util

from .const import CONF_DEVICES, DOMAIN
from .devices import KIND_FULLY, KIND_TECHO5, STREAMED, TECHO5_MODE, TECHO5_SHOW, async_reload_screen, dashboard_title, find_screens

if TYPE_CHECKING:
    from .wall import PosterWall

_LOGGER = logging.getLogger(__name__)

ALIVE = timedelta(minutes=3)  # a page that pinned nothing for this long counts as hung
GRACE = timedelta(minutes=5)  # after a start or a reload
SOFT_WAIT = timedelta(minutes=2)  # pages told to load again: wait this long before restarting screens
PAUSE = timedelta(minutes=20)  # at most one restart of the screens in this time
ROUNDS = 2  # rounds of restarts; then the screens are left alone and a repair tells why
HEALTHY = timedelta(hours=1)  # only screens that ran this long without a break count as fixed
DEVICE_WINDOW = timedelta(hours=6)  # an Echo itself is restarted at most once in this time


def screens_on(hass: HomeAssistant, wall: PosterWall) -> list[str]:
    """Kept screens that show this wall now and whose screen is on."""
    out = []
    title = dashboard_title(wall.entry.title)
    for screen, conf in (wall.entry.options.get(CONF_DEVICES) or {}).items():
        if not conf.get("keep"):
            continue
        kind, _, target = screen.partition(":")
        if kind == KIND_TECHO5:
            base = target.removesuffix(TECHO5_SHOW)
            page, mode = hass.states.get(target), hass.states.get(base + TECHO5_MODE)
            light = hass.states.get(f"light.{base.split('.', 1)[1]}_screen")
            if (page and page.state == title and mode and mode.state == STREAMED
                    and (light is None or light.state != STATE_OFF)):
                out.append(screen)
        elif kind == KIND_FULLY:
            screen_switch = next((e.entity_id for e in er.async_entries_for_device(er.async_get(hass), target)
                                  if e.domain == "switch" and e.translation_key == "screen"), None)
            state = hass.states.get(screen_switch) if screen_switch else None
            if state is None or state.state != STATE_OFF:
                out.append(screen)
    return out


class Watchdog:
    """Checks one wall every minute and gets hung screens going again, one step after another."""

    def __init__(self, hass: HomeAssistant, wall: PosterWall) -> None:
        self.hass = hass
        self.wall = wall
        self.short_since: datetime | None = None
        self.step = 0  # 0 fine, 1 pages told to load again, 2 screens restarted, 3 devices restarted, 4 given up
        self.step_at: datetime | None = None
        self.restarts = 0
        self.rounds = 0
        self.healthy_since: datetime | None = None
        self.device_at: datetime | None = None  # last restart of the devices themselves

    @property
    def issue_id(self) -> str:
        return f"screens_hung_{self.wall.entry.entry_id}"

    async def async_check(self, now: datetime) -> None:
        wall = self.wall
        expected = screens_on(self.hass, wall)
        if not expected or now - wall.started < GRACE or not wall.photos:
            # nothing to watch now (screens off, Echo starting, no photos): wait, and forget nothing,
            # so a screen that keeps breaking down is not restarted again and again
            self.short_since = None
            return
        if wall.alive_count(ALIVE) >= len(expected):
            self.short_since = None
            if self.step:
                self.step, self.step_at = 0, None
            if self.healthy_since is None:
                self.healthy_since = now
            elif self.rounds and now - self.healthy_since >= HEALTHY:
                # ran an hour without a break: really fixed
                ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
                self.rounds = 0
            return
        self.healthy_since = None
        if self.step == 4:
            return  # given up: the repair says why; the button "Reload screens" or photos coming again end it
        if self.short_since is None:
            self.short_since = now
            return
        since = now - (self.step_at or now)
        if self.step == 0:
            _LOGGER.info("PosterWall %s: a screen shows no new photos, its page loads again", wall.entry.title)
            wall.async_reload_pages()
        elif self.step == 1 and since >= SOFT_WAIT:
            _LOGGER.warning("PosterWall %s: a screen still shows no new photos, restarting %s", wall.entry.title, ", ".join(expected))
            await async_restart_screens(self.hass, wall, expected)
        elif self.step == 2 and since >= GRACE:
            if self.device_at is None or now - self.device_at >= DEVICE_WINDOW:
                _LOGGER.warning("PosterWall %s: still no new photos, restarting the devices %s", wall.entry.title, ", ".join(expected))
                self.device_at = now
                await async_restart_screens(self.hass, wall, expected, device=True)
            else:
                _LOGGER.info("PosterWall %s: devices were restarted lately, not again", wall.entry.title)
        elif self.step == 3 and since >= PAUSE:
            self.rounds += 1
            if self.rounds < ROUNDS:
                self.step = -1  # start over
            else:
                # restarting did not help (the screen's server may be down): stop and say so
                _LOGGER.warning("PosterWall %s: restarting did not help, leaving %s alone", wall.entry.title, ", ".join(expected))
                names = {s.id: s.name for s in find_screens(self.hass)}
                ir.async_create_issue(self.hass, DOMAIN, self.issue_id, is_fixable=False, severity=ir.IssueSeverity.WARNING,
                                      translation_key="screens_hung",
                                      translation_placeholders={"wall": wall.entry.title,
                                                                "screens": ", ".join(names.get(s, s) for s in expected)})
        else:
            return
        self.step += 1
        self.step_at = now
        self.restarts += self.step in (2, 3)

    def async_reset(self) -> None:
        """Start afresh (the button "Reload screens")."""
        ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
        self.short_since = self.step_at = self.healthy_since = None
        self.step = self.rounds = 0


async def async_restart_screens(hass: HomeAssistant, wall: PosterWall, screens: list[str], *, device: bool = False) -> None:
    """Restart screens one after another; one that fails does not stop the others."""
    for screen in screens:
        try:
            await async_reload_screen(hass, wall.entry.entry_id, screen, device=device)
        except Exception as err:
            _LOGGER.warning("PosterWall %s: %s could not be restarted: %s", wall.entry.title, screen, err)


async def async_reload_everything(hass: HomeAssistant, wall: PosterWall) -> None:
    """The button "Reload screens": every page loads again, every kept screen that is on restarts (Echo: the device)."""
    wall.async_reload_pages()
    wall.started = dt_util.utcnow()
    if wall.watchdog is not None:
        wall.watchdog.async_reset()
    await async_restart_screens(hass, wall, screens_on(hass, wall), device=True)
