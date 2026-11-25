"""Photo sources: Home Assistant media, Immich and Synology Photos.

Every source lists photos as `Photo` objects. Media photos are resolved by Home
Assistant itself; Immich and Synology photos are fetched by this integration
(the card never sees an API key, password or session).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
import random
import re
from typing import Any
from urllib.parse import unquote

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout
from homeassistant.components import media_source
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ALBUM_ALL,
    ALBUM_FAVORITES,
    CONF_API_KEY,
    CONF_DEVICE_TOKEN,
    CONF_FOLDER,
    CONF_PASSWORD,
    CONF_SOURCE,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    MAX_FOLDERS,
    MAX_PHOTOS,
    SOURCE_IMMICH,
    SOURCE_MEDIA,
    SOURCE_SYNOLOGY,
)

_LOGGER = logging.getLogger(__name__)

IMAGE = re.compile(r"\.(jpe?g|png|webp|gif|heic|heif|avif)$", re.I)
BROWSER_IMAGE = re.compile(r"\.(jpe?g|png|webp|gif|avif)$", re.I)
SKIP_FOLDER = re.compile(r"@eaDir|#recycle|#snapshot|\.thumb|^\.", re.I)
# 20231125, 2023-11-25, 2023_11_25, 2023.11.25 inside a file name
DATE_IN_NAME = re.compile(r"(?<!\d)((?:19|20)\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])(?!\d)")
YEAR_FOLDER = re.compile(r"^((?:19|20)\d{2})$")
TIMEOUT = ClientTimeout(total=30)
PAGE = 1000


class SourceError(HomeAssistantError):
    """The photo source cannot be reached."""


class AuthError(SourceError):
    """The photo source refused the credentials."""


class OtpRequired(AuthError):
    """Synology asks for a two-factor code."""


@dataclass(slots=True)
class Photo:
    """One photo of a wall."""

    id: str
    date: str | None = None  # "2023-11-25", "2023" or None
    favorite: bool = False
    albums: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Album:
    """A folder or album the user can pick on the wall."""

    key: str
    title: str


def date_from_name(name: str) -> str | None:
    """Read a capture date from a file name like IMG_20231125_123456.jpg."""
    if m := DATE_IN_NAME.search(name):
        try:
            datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


class PhotoSource:
    """Base class of a photo source."""

    kind = ""
    #: photos are delivered through this integration (True) or resolved by HA (False)
    proxied = True
    #: the source knows favourites
    has_favorites = False

    def __init__(self, hass: HomeAssistant, data: dict[str, Any]) -> None:
        self.hass = hass
        self.data = data

    async def async_validate(self) -> None:
        """Raise when the source cannot be used."""
        raise NotImplementedError

    async def async_albums(self) -> list[Album]:
        """Albums or folders the user can pick (without "all")."""
        raise NotImplementedError

    async def async_photos(self, album: str) -> list[Photo]:
        """All photos of an album (or of everything)."""
        raise NotImplementedError

    def in_root(self, album: str) -> bool:
        """A folder below the wall's folder that is not in the album list (only media folders)."""
        return False

    def folder_title(self, album: str) -> str:
        return album

    async def async_fetch(self, photo: Photo) -> tuple[bytes, str]:
        """Image bytes and content type of a proxied photo."""
        raise NotImplementedError

    @property
    def device_token(self) -> str | None:
        """A token the source wants to remember (Synology two-factor)."""
        return None


# ---------------------------------------------------------------- HA media


class MediaPhotoSource(PhotoSource):
    """A folder of the Home Assistant media browser (local, NAS, any media source)."""

    kind = SOURCE_MEDIA
    proxied = False

    def __init__(self, hass: HomeAssistant, data: dict[str, Any]) -> None:
        super().__init__(hass, data)
        self.root: str = data[CONF_FOLDER]
        self._albums: list[Album] = []

    async def _browse(self, media_id: str | None) -> Any:
        try:
            return await asyncio.wait_for(media_source.async_browse_media(self.hass, media_id), 60)
        except (TimeoutError, HomeAssistantError, ValueError) as err:
            raise SourceError(str(err) or "browse failed") from err

    async def async_validate(self) -> None:
        await self._browse(self.root)

    async def _walk(self, start: str, *, photos: bool) -> tuple[list[Album], list[Photo]]:
        """Read a folder breadth first (limited).

        photos=False: only the folders down to two levels (the album list, quick).
        photos=True: every photo below start, so a chosen album is always read completely.
        """
        found: list[Photo] = []
        albums: list[Album] = []
        queue: list[tuple[str, tuple[str, ...], str | None]] = [(start, (), None)]
        folders = 0
        first_error: SourceError | None = None
        while queue and folders < MAX_FOLDERS and len(found) < MAX_PHOTOS:
            media_id, titles, year = queue.pop(0)
            folders += 1
            try:
                item = await self._browse(media_id)
            except SourceError as err:
                if media_id == start:
                    raise
                first_error = first_error or err
                continue
            for child in item.children or []:
                title = child.title or ""
                if child.can_expand:
                    if SKIP_FOLDER.search(title):
                        continue
                    child_year = m.group(1) if (m := YEAR_FOLDER.match(title.strip())) else year
                    if not photos:
                        if len(titles) < 2:
                            albums.append(Album(child.media_content_id, " / ".join((*titles, title))))
                            if len(titles) < 1:
                                queue.append((child.media_content_id, (*titles, title), child_year))
                        continue
                    queue.append((child.media_content_id, titles, child_year))
                elif photos and (BROWSER_IMAGE.search(title) or (child.media_content_type or "").startswith("image/")):
                    found.append(Photo(child.media_content_id, date_from_name(title) or year, False, ()))
        if first_error:
            _LOGGER.debug("Some folders of %s could not be read: %s", start, first_error)
        return albums, found

    def in_root(self, album: str) -> bool:
        return album.startswith(f"{self.root.rstrip('/')}/")

    def folder_title(self, album: str) -> str:
        return " / ".join(unquote(p) for p in album[len(self.root.rstrip("/")) + 1:].split("/") if p)

    async def async_albums(self) -> list[Album]:
        albums, _ = await self._walk(self.root, photos=False)
        self._albums = albums
        return albums

    async def async_photos(self, album: str) -> list[Photo]:
        start = self.root
        if album not in (ALBUM_ALL, ALBUM_FAVORITES, "") and (album == self.root or self.in_root(album)):
            start = album
        year = m.group(1) if (m := YEAR_FOLDER.match(start.rstrip("/").rsplit("/", 1)[-1])) else None
        _, photos = await self._walk(start, photos=True)
        if year:
            photos = [p if p.date else Photo(p.id, year, p.favorite, p.albums, p.extra) for p in photos]
        return photos

    async def async_fetch(self, photo: Photo) -> tuple[bytes, str]:  # pragma: no cover - not proxied
        raise SourceError("media photos are resolved by Home Assistant")


# ---------------------------------------------------------------- Immich


class ImmichPhotoSource(PhotoSource):
    """Immich server, talked to with an API key."""

    kind = SOURCE_IMMICH
    has_favorites = True

    def __init__(self, hass: HomeAssistant, data: dict[str, Any]) -> None:
        super().__init__(hass, data)
        self.base = str(data[CONF_URL]).rstrip("/")
        if self.base.endswith("/api"):
            self.base = self.base[:-4]
        self._session: ClientSession = async_get_clientsession(hass, verify_ssl=data.get(CONF_VERIFY_SSL, True))

    def _headers(self, accept: str = "application/json") -> dict[str, str]:
        return {"x-api-key": self.data[CONF_API_KEY], "Accept": accept}

    @staticmethod
    async def _check(resp: ClientResponse) -> None:
        if resp.status in (401, 403):
            raise AuthError("Immich refused the API key")
        if resp.status >= 400:
            raise SourceError(f"Immich answered {resp.status}")

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        try:
            async with self._session.get(f"{self.base}/api/{path}", params=params, headers=self._headers(), timeout=TIMEOUT) as resp:
                await self._check(resp)
                return await resp.json()
        except (ClientError, TimeoutError, ValueError) as err:
            raise SourceError(f"Immich not reachable: {err}") from err

    async def _post(self, path: str, body: dict[str, Any]) -> Any:
        try:
            async with self._session.post(f"{self.base}/api/{path}", json=body, headers=self._headers(), timeout=TIMEOUT) as resp:
                await self._check(resp)
                return await resp.json()
        except (ClientError, TimeoutError, ValueError) as err:
            raise SourceError(f"Immich not reachable: {err}") from err

    async def async_validate(self) -> None:
        me = await self._get("users/me")
        if not isinstance(me, dict) or "id" not in me:
            raise SourceError("This is not an Immich server")

    async def async_albums(self) -> list[Album]:
        own = await self._get("albums")
        shared = await self._get("albums", {"shared": "true"})
        seen: set[str] = set()
        albums: list[Album] = []
        for a in [*(own or []), *(shared or [])]:
            if a.get("id") and a["id"] not in seen:
                seen.add(a["id"])
                albums.append(Album(a["id"], a.get("albumName") or a["id"]))
        albums.sort(key=lambda a: a.title.lower())
        return albums

    @staticmethod
    def _photo(asset: dict[str, Any]) -> Photo | None:
        if asset.get("type") != "IMAGE" or asset.get("isTrashed") or asset.get("isArchived"):
            return None
        when = asset.get("localDateTime") or asset.get("fileCreatedAt") or ""
        return Photo(f"i{asset['id']}", when[:10] if len(when) >= 10 else None, bool(asset.get("isFavorite")),
                     extra={"asset": asset["id"]})

    async def async_photos(self, album: str) -> list[Photo]:
        body: dict[str, Any] = {"type": "IMAGE", "size": PAGE, "withArchived": False}
        if album == ALBUM_FAVORITES:
            body["isFavorite"] = True
        elif album not in (ALBUM_ALL, ""):
            body["albumIds"] = [album]
        photos: list[Photo] = []
        page = 1
        while len(photos) < MAX_PHOTOS:
            result = await self._post("search/metadata", {**body, "page": page})
            assets = (result or {}).get("assets") or {}
            photos.extend(p for a in assets.get("items") or [] if (p := self._photo(a)))
            if not assets.get("nextPage"):
                break
            page += 1
        return photos

    async def async_fetch(self, photo: Photo) -> tuple[bytes, str]:
        url = f"{self.base}/api/assets/{photo.extra['asset']}/thumbnail"
        try:
            async with self._session.get(url, params={"size": "preview"}, headers=self._headers("application/octet-stream"),
                                         timeout=TIMEOUT) as resp:
                await self._check(resp)
                return await resp.read(), resp.headers.get("Content-Type", "image/jpeg")
        except (ClientError, TimeoutError) as err:
            raise SourceError(f"Immich not reachable: {err}") from err


# ---------------------------------------------------------------- Synology Photos


SYNO_ERRORS_AUTH = {400, 401, 402, 404, 406, 407, 408, 409, 410}


class SynologyPhotoSource(PhotoSource):
    """Synology Photos on a DiskStation (DSM 7), with a user and password."""

    kind = SOURCE_SYNOLOGY

    PERSONAL = "personal"
    SHARED = "shared"

    def __init__(self, hass: HomeAssistant, data: dict[str, Any], otp: str | None = None) -> None:
        super().__init__(hass, data)
        self.base = str(data[CONF_URL]).rstrip("/")
        self._session: ClientSession = async_get_clientsession(hass, verify_ssl=data.get(CONF_VERIFY_SSL, True))
        self._apis: dict[str, dict[str, Any]] = {}
        self._sid: str | None = None
        self._otp = otp
        self._device_token: str | None = data.get(CONF_DEVICE_TOKEN)
        self._lock = asyncio.Lock()
        self._passphrases: dict[str, str] = {}
        # folder key ("f<id>" personal, "t<id>" shared space) -> (folder id, shared space, path)
        self._folders: dict[str, tuple[int, bool, str]] = {}

    @property
    def device_token(self) -> str | None:
        return self._device_token

    async def _call(self, api: str, method: str, params: dict[str, Any] | None = None, *, raw: bool = False,
                    post: bool = False, retry: bool = True) -> Any:
        if not self._apis:
            await self._discover()
        info = self._apis.get(api)
        if info is None:
            raise SourceError(f"{api} is missing – is Synology Photos installed?")
        query: dict[str, Any] = {"api": api, "version": min(int(info["maxVersion"]), 7 if api == "SYNO.API.Auth" else 99),
                                 "method": method, **(params or {})}
        if self._sid and api != "SYNO.API.Auth":
            query["_sid"] = self._sid
        url = f"{self.base}/webapi/{info['path']}"
        try:
            if post:
                req = self._session.post(url, data={k: str(v) for k, v in query.items()}, timeout=TIMEOUT)
            else:
                req = self._session.get(url, params={k: str(v) for k, v in query.items()}, timeout=TIMEOUT)
            async with req as resp:
                if resp.status >= 400:
                    raise SourceError(f"DiskStation answered {resp.status}")
                if raw and not resp.headers.get("Content-Type", "").startswith(("application/json", "text/")):
                    return await resp.read(), resp.headers.get("Content-Type", "image/jpeg")
                result = await resp.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise SourceError(f"DiskStation not reachable: {err}") from err
        if not result.get("success"):
            code = int((result.get("error") or {}).get("code", 0))
            if api == "SYNO.API.Auth":
                if code == 403:
                    raise OtpRequired("two-factor code needed")
                if code in SYNO_ERRORS_AUTH:
                    raise AuthError(f"login refused ({code})")
            if code in (106, 107, 119) and retry and api != "SYNO.API.Auth":
                self._sid = None
                await self._login()
                return await self._call(api, method, params, raw=raw, post=post, retry=False)
            raise SourceError(f"{api} {method} failed ({code})")
        return result.get("data")

    async def _discover(self) -> None:
        self._apis = {"SYNO.API.Info": {"path": "query.cgi", "maxVersion": 1}}
        data = await self._call("SYNO.API.Info", "query", {"query": "SYNO.API.Auth,SYNO.Foto.,SYNO.FotoTeam."})
        self._apis.update(data or {})

    async def _login(self) -> None:
        params: dict[str, Any] = {"account": self.data[CONF_USERNAME], "passwd": self.data[CONF_PASSWORD],
                                  "session": "PosterWall", "format": "sid",
                                  "enable_device_token": "yes", "device_name": "PosterWall"}
        if self._otp:
            params["otp_code"] = self._otp
        if self._device_token:
            params["device_id"] = self._device_token
        data = await self._call("SYNO.API.Auth", "login", params, post=True)
        self._sid = data["sid"]
        self._otp = None
        self._device_token = data.get("device_id") or data.get("did") or self._device_token

    async def _ensure(self) -> None:
        async with self._lock:
            if not self._sid:
                await self._login()

    async def async_validate(self) -> None:
        await self._ensure()
        await self._call("SYNO.Foto.Browse.Item", "count", {})

    async def async_albums(self) -> list[Album]:
        await self._ensure()
        albums: list[Album] = []
        offset = 0
        while True:
            data = await self._call("SYNO.Foto.Browse.Album", "list",
                                    {"offset": offset, "limit": 500, "category": "normal_share_with_me"})
            chunk = (data or {}).get("list") or []
            for a in chunk:
                key = f"a{a['id']}"
                if a.get("passphrase"):
                    self._passphrases[key] = a["passphrase"]
                albums.append(Album(key, a.get("name") or str(a["id"])))
            if len(chunk) < 500:
                break
            offset += 500
        self._folders = {}
        out = [Album(self.PERSONAL, "Personal space"), *await self._folder_tree(False)]
        if "SYNO.FotoTeam.Browse.Item" in self._apis:
            out += [Album(self.SHARED, "Shared space"), *await self._folder_tree(True)]
        return out + albums

    async def _folder_tree(self, team: bool) -> list[Album]:
        """The real folders of the personal (or shared) space, like in the Photos tab of Synology Photos."""
        api = "SYNO.FotoTeam.Browse.Folder" if team else "SYNO.Foto.Browse.Folder"
        if api not in self._apis:
            return []
        try:
            root = int(((await self._call(api, "get", {})) or {})["folder"]["id"])
        except (SourceError, KeyError, TypeError, ValueError) as err:
            _LOGGER.debug("Synology Photos: folders of the %s space cannot be listed: %s", "shared" if team else "personal", err)
            return []
        space = "Shared space" if team else "Personal space"
        found: list[Album] = []
        queue = [root]
        while queue and len(self._folders) < MAX_FOLDERS:
            parent = queue.pop(0)
            offset = 0
            while True:
                try:
                    data = await self._call(api, "list", {"id": parent, "offset": offset, "limit": 500})
                except SourceError as err:
                    _LOGGER.debug("Synology Photos: folder %s cannot be listed: %s", parent, err)
                    break
                chunk = (data or {}).get("list") or []
                for f in chunk:
                    path = str(f.get("name") or f["id"]).strip("/")
                    if not path or SKIP_FOLDER.search(path.rsplit("/", 1)[-1]):
                        continue
                    key = f"{'t' if team else 'f'}{f['id']}"
                    self._folders[key] = (int(f["id"]), team, path)
                    found.append(Album(key, " / ".join((space, *path.split("/")))))
                    queue.append(int(f["id"]))
                if len(chunk) < 500:
                    break
                offset += 500
        found.sort(key=lambda a: a.title.lower())
        return found

    @staticmethod
    def _photo(item: dict[str, Any], team: bool, passphrase: str | None) -> Photo | None:
        if item.get("type") not in (None, "photo", "live"):
            return None
        thumb = (item.get("additional") or {}).get("thumbnail") or {}
        if not thumb.get("cache_key"):
            return None
        size = "xl" if thumb.get("xl") == "ready" else "m" if thumb.get("m") == "ready" else "sm"
        when = None
        if isinstance(item.get("time"), int | float):
            when = datetime.fromtimestamp(item["time"], UTC).strftime("%Y-%m-%d")
        elif item.get("filename"):
            when = date_from_name(item["filename"])
        team = team or item.get("owner_user_id") == 0
        return Photo(f"s{item['id']}", when, False,
                     extra={"id": item["id"], "cache_key": thumb["cache_key"], "size": size, "team": team, "passphrase": passphrase})

    async def _items(self, api: str, params: dict[str, Any], team: bool, passphrase: str | None) -> list[Photo]:
        photos: list[Photo] = []
        offset = 0
        while len(photos) < MAX_PHOTOS:
            data = await self._call(api, "list", {**params, "offset": offset, "limit": PAGE, "additional": '["thumbnail"]'})
            chunk = (data or {}).get("list") or []
            photos.extend(p for i in chunk if (p := self._photo(i, team, passphrase)))
            if len(chunk) < PAGE:
                break
            offset += PAGE
        return photos

    async def async_photos(self, album: str) -> list[Photo]:
        await self._ensure()
        if album == self.SHARED:
            return await self._items("SYNO.FotoTeam.Browse.Item", {}, True, None)
        if album[:1] in ("f", "t") and album[1:].isdigit():
            if not self._folders:
                await self.async_albums()
            if album in self._folders:
                # the folder and every folder below it
                _, team, path = self._folders[album]
                api = "SYNO.FotoTeam.Browse.Item" if team else "SYNO.Foto.Browse.Item"
                photos: list[Photo] = []
                for fid, t, p in self._folders.values():
                    if t == team and (p == path or p.startswith(f"{path}/")) and len(photos) < MAX_PHOTOS:
                        photos += await self._items(api, {"folder_id": fid}, team, None)
                return photos
        if album.startswith("a"):
            if not self._passphrases:
                await self.async_albums()
            if pp := self._passphrases.get(album):
                return await self._items("SYNO.Foto.Browse.Item", {"passphrase": pp}, False, pp)
            return await self._items("SYNO.Foto.Browse.Item", {"album_id": album[1:]}, False, None)
        return await self._items("SYNO.Foto.Browse.Item", {}, False, None)

    async def async_fetch(self, photo: Photo) -> tuple[bytes, str]:
        await self._ensure()
        e = photo.extra
        params: dict[str, Any] = {"id": e["id"], "cache_key": e["cache_key"], "size": e["size"], "type": "unit"}
        if e.get("passphrase"):
            params["passphrase"] = e["passphrase"]
        api = "SYNO.FotoTeam.Thumbnail" if e.get("team") else "SYNO.Foto.Thumbnail"
        result = await self._call(api, "get", params, raw=True)
        if not isinstance(result, tuple):
            raise SourceError("DiskStation sent no image")
        return result


def create_source(hass: HomeAssistant, data: dict[str, Any], otp: str | None = None) -> PhotoSource:
    """The source of a config entry."""
    kind = data.get(CONF_SOURCE, SOURCE_MEDIA)
    if kind == SOURCE_IMMICH:
        return ImmichPhotoSource(hass, data)
    if kind == SOURCE_SYNOLOGY:
        return SynologyPhotoSource(hass, data, otp)
    return MediaPhotoSource(hass, data)


def _name(photo_id: str) -> str:
    """File name of a photo id (whole id for servers)."""
    return photo_id.rsplit("/", 1)[-1].lower()


def pick(photos: list[Photo], recent: Iterable[str], *, today: datetime, favorites: bool, on_this_day: bool,
         rnd: random.Random | None = None) -> tuple[Photo, int | None] | None:
    """Choose the next photo: favourites more often, "on this day" photos now and then, nothing shown just before.

    Returns the photo and, for an "on this day" pick, how many years ago it was taken.
    """
    if not photos:
        return None
    r = rnd or random
    # the same picture often sits in two folders (backup and sorted copy): never show the same file name twice
    seen = {_name(i) for i in recent}
    if on_this_day and r.random() < 0.4:
        day = today.strftime("%m-%d")
        years = []
        for p in photos:
            if p.date and len(p.date) == 10 and _name(p.id) not in seen and int(p.date[:4]) < today.year:
                diff = abs((datetime(2000, int(p.date[5:7]), int(p.date[8:10])) - datetime(2000, today.month, today.day)).days)
                if p.date[5:] == day or diff <= 3:
                    years.append(p)
        if years:
            p = r.choice(years)
            return p, today.year - int(p.date[:4])  # type: ignore[index]
    if favorites and r.random() < 0.35:
        favs = [p for p in photos if p.favorite and _name(p.id) not in seen]
        if favs:
            return r.choice(favs), None
    for _ in range(12):
        p = r.choice(photos)
        if _name(p.id) not in seen:
            return p, None
    # many photos were shown just before: choose among the others (only all shown → any)
    fresh = [p for p in photos if _name(p.id) not in seen]
    return r.choice(fresh or photos), None
