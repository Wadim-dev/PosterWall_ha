"""One poster wall: its photo source, live settings and photo list."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta
import hashlib
import logging
from typing import Any

from homeassistant.components import media_source
from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.media_player.browse_media import async_process_play_media_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ALBUM_ALL,
    ALBUM_FAVORITES,
    CONF_CALENDARS,
    CONF_EVENT_DAYS,
    CONF_EVENTS,
    CONF_WEATHER,
    DEFAULT_EVENT_DAYS,
    DEFAULT_EVENTS,
    DOMAIN,
    PHOTO_URL,
    REFRESH_HOURS,
    SETTINGS_DEFAULTS,
    SIGNAL_UPDATE,
    VERSION,
)
from .shrink import shrink
from .sources import Album, Photo, PhotoSource, SourceError, index_days, pick

_LOGGER = logging.getLogger(__name__)

ALL_TITLE = {"de": "Alle Fotos", "en": "All photos"}
FAV_TITLE = {"de": "Favoriten", "en": "Favourites"}


def _key(photo_id: str) -> str:
    """A short key of a photo for its URL."""
    return hashlib.sha256(photo_id.encode()).hexdigest()[:24]


class PosterWall:
    """Runtime data of a config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, source: PhotoSource) -> None:
        self.hass = hass
        self.entry = entry
        self.source = source
        self.store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.settings: dict[str, Any] = dict(SETTINGS_DEFAULTS)
        self.albums: list[Album] = []
        self.photos: list[Photo] = []
        self._by_id: dict[str, Photo] = {}
        self._favs: list[Photo] = []
        self._by_day: dict[str, list[Photo]] = {}  # dated photos by "MM-DD" for "on this day"
        self._by_key: dict[str, Photo] = {}  # a short key for the photo URL (media ids hold slashes)
        self._shrinking = asyncio.Semaphore(2)  # photos shrunk at the same time: keeps Home Assistant light
        self.recent: deque[str] = deque(maxlen=60)
        self.last_refresh: datetime | None = None
        self.error: str | None = None
        self.loading = False
        # display pages that show this wall full screen: id -> last time they pinned a photo (or slept at night)
        self.screens_alive: dict[str, datetime] = {}
        self.screens_info: dict[str, dict[str, int]] = {}  # what each display page holds, for diagnostics
        self.reload_token = 0
        self.started = dt_util.utcnow()
        self.watchdog: Any = None
        self._unsubs: list[Callable[[], None]] = []

    # ------------------------------------------------------------ lifecycle

    async def async_start(self) -> None:
        """Load the settings and the first photo list (raises SourceError)."""
        stored = await self.store.async_load() or {}
        self.settings.update({k: v for k, v in stored.items() if k in SETTINGS_DEFAULTS})
        await self.source.async_validate()
        self._unsubs.append(async_track_time_interval(self.hass, self._interval, timedelta(hours=REFRESH_HOURS)))

    async def _interval(self, _now: datetime) -> None:
        await self.async_refresh()

    @callback
    def async_stop(self) -> None:
        while self._unsubs:
            self._unsubs.pop()()

    async def async_refresh(self) -> None:
        """Read albums and photos again."""
        if self.loading:
            return
        self.loading = True
        self.async_notify()
        try:
            self.albums = await self.source.async_albums()
            album = self.settings["album"]
            keys = {a.key for a in self.albums} | {ALBUM_ALL} | ({ALBUM_FAVORITES} if self.source.has_favorites else set())
            if album not in keys and not self.source.in_root(album):
                album = self.settings["album"] = ALBUM_ALL
            try:
                photos = await self.source.async_photos(album)
            except SourceError:
                if album == ALBUM_ALL or album in keys:
                    raise
                # a deeper folder that is gone: show everything again
                album = self.settings["album"] = ALBUM_ALL
                photos = await self.source.async_photos(album)
        except SourceError as err:
            if self.error is None:
                _LOGGER.warning("PosterWall %s: photos could not be read: %s", self.entry.title, err)
            self.error = str(err)
        else:
            if self.error:
                _LOGGER.info("PosterWall %s: photos can be read again", self.entry.title)
            self.error = None
            self.photos = photos
            self._by_id = {p.id: p for p in photos}
            self._by_key = {_key(p.id): p for p in photos}
            self._by_day = index_days(photos)
            self._favs = [p for p in photos if p.favorite]
            self.recent.clear()
            self.last_refresh = dt_util.utcnow()
        finally:
            self.loading = False
            self.async_notify()

    # ------------------------------------------------------------ settings

    @callback
    def async_notify(self) -> None:
        async_dispatcher_send(self.hass, SIGNAL_UPDATE.format(entry_id=self.entry.entry_id))

    async def async_set(self, key: str, value: Any) -> None:
        """Change one live setting."""
        if key not in SETTINGS_DEFAULTS:
            raise KeyError(key)
        old = self.settings.get(key)
        self.settings[key] = value
        self.store.async_delay_save(lambda: dict(self.settings), 2)
        self.async_notify()
        if key == "album" and old != value:
            self.hass.async_create_task(self.async_refresh(), f"{DOMAIN} refresh")

    @callback
    def async_alive(self, client: str, info: dict[str, int] | None = None) -> None:
        """A display page is fine: it pinned a photo (or sleeps at night)."""
        now = dt_util.utcnow()
        self.screens_alive[client] = now
        if info:
            self.screens_info[client] = info
        for old in [c for c, t in self.screens_alive.items() if now - t > timedelta(hours=1)]:
            del self.screens_alive[old]
            self.screens_info.pop(old, None)

    def alive_count(self, within: timedelta) -> int:
        """How many display pages were fine lately."""
        now = dt_util.utcnow()
        return sum(1 for t in self.screens_alive.values() if now - t <= within)

    @callback
    def async_reload_pages(self) -> None:
        """Every display page of this wall loads again."""
        self.reload_token += 1
        self.screens_alive.clear()
        self.screens_info.clear()
        self.async_notify()

    def album_options(self) -> list[tuple[str, str]]:
        """(key, title) of every album choice, "all" first."""
        lang = "de" if (self.hass.config.language or "en").startswith("de") else "en"
        opts = [(ALBUM_ALL, ALL_TITLE[lang])]
        if self.source.has_favorites:
            opts.append((ALBUM_FAVORITES, FAV_TITLE[lang]))
        opts += [(a.key, a.title) for a in self.albums]
        album = self.settings["album"]
        if all(k != album for k, _ in opts) and self.source.in_root(album):
            # a deeper folder picked on the PosterWall page
            opts.append((album, self.source.folder_title(album)))
        return opts

    def payload(self) -> dict[str, Any]:
        """Everything the card needs to know (no secrets)."""
        o = self.entry.options
        return {
            "entry_id": self.entry.entry_id,
            "title": self.entry.title,
            "version": VERSION,
            "reload": self.reload_token,
            "settings": dict(self.settings),
            "weather": o.get(CONF_WEATHER),
            "calendars": list(o.get(CONF_CALENDARS) or []),
            "events": int(o.get(CONF_EVENTS, DEFAULT_EVENTS)),
            "event_days": int(o.get(CONF_EVENT_DAYS, DEFAULT_EVENT_DAYS)),
            "photos": len(self.photos),
            "loading": self.loading,
            "error": self.error,
            "source": self.source.kind,
            "albums": [{"key": k, "title": t} for k, t in self.album_options()],
        }

    # ------------------------------------------------------------ photos

    def photo(self, photo_id: str) -> Photo | None:
        return self._by_id.get(photo_id) or self._by_key.get(photo_id)

    async def async_photo_bytes(self, photo: Photo) -> tuple[bytes, str]:
        """The display-sized image of a photo."""
        async with self._shrinking:
            if (path := self.source.local_path(photo)) is not None:
                try:
                    return await self.hass.async_add_executor_job(shrink, path)
                except OSError as err:
                    raise SourceError(f"photo cannot be read: {err}") from err
            if not self.source.proxied:
                raise SourceError("photo is not delivered by PosterWall")
            body, content_type = await self.source.async_fetch(photo)
            return await self.hass.async_add_executor_job(shrink, body, content_type)

    async def async_next(self, count: int = 1) -> list[dict[str, Any]]:
        """The next photos for a display, each with a short-lived URL."""
        out: list[dict[str, Any]] = []
        now = dt_util.now()
        for _ in range(max(1, min(count, 4))):
            chosen = pick(self.photos, self.recent, today=now, favorites=bool(self.settings["favorites"]),
                          on_this_day=bool(self.settings["on_this_day"]), by_day=self._by_day, favs=self._favs)
            if chosen is None:
                break
            photo, years = chosen
            try:
                url = await self._url(photo)
            except SourceError as err:
                _LOGGER.debug("Photo %s cannot be shown: %s", photo.id, err)
                self.recent.append(photo.id)
                continue
            self.recent.append(photo.id)
            out.append({"id": photo.id, "url": url, "date": photo.date, "years_ago": years, "favorite": photo.favorite})
        return out

    async def _url(self, photo: Photo) -> str:
        if not self.source.proxied and self.source.local_path(photo) is None:
            try:
                play = await media_source.async_resolve_media(self.hass, photo.id, None)
            except media_source.Unresolvable as err:
                raise SourceError(str(err)) from err
            return async_process_play_media_url(self.hass, play.url, allow_relative_url=True)
        path = PHOTO_URL.format(entry_id=self.entry.entry_id, photo_id=_key(photo.id))
        return async_sign_path(self.hass, path, timedelta(hours=1))
