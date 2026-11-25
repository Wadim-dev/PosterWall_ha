"""Click through the Home Assistant media browser to a folder (setup and PosterWall page)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from homeassistant.components import media_source
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .sources import BROWSER_IMAGE, SKIP_FOLDER

# media sources that never hold photos
NO_PHOTOS = {"camera", "radio_browser", "tts", "music_assistant", "ai_task"}
ROOT_TITLE = "Media"
PREFIX = "media-source://"


@dataclass(slots=True)
class Folder:
    """One opened folder: its sub folders and how many photos lie directly in it."""

    id: str | None
    title: str
    folders: list[tuple[str, str]] = field(default_factory=list)
    photos: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "photos": self.photos,
                "folders": [{"id": i, "title": t} for i, t in self.folders]}


def _provider(media_id: str) -> str:
    return media_id.removeprefix(PREFIX).split("/", 1)[0]


async def async_open(hass: HomeAssistant, media_id: str | None) -> Folder:
    """Open a folder (None = the list of media sources). Raises HomeAssistantError."""
    try:
        item = await asyncio.wait_for(media_source.async_browse_media(hass, media_id), 60)
    except TimeoutError as err:
        raise HomeAssistantError("The folder did not answer in time") from err
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err
    children = item.children or []
    folders = [(c.media_content_id, c.title or c.media_content_id) for c in children
               if c.can_expand and not SKIP_FOLDER.search(c.title or "") and _provider(c.media_content_id) not in NO_PHOTOS]
    photos = sum(1 for c in children if not c.can_expand and (BROWSER_IMAGE.search(c.title or "")
                                                               or (c.media_content_type or "").startswith("image/")))
    return Folder(media_id, ROOT_TITLE if media_id is None else (item.title or media_id), folders, photos)


async def async_chain(hass: HomeAssistant, media_id: str | None) -> list[tuple[str | None, str]]:
    """The way from the list of media sources down to a folder: [(id, title), …], top first.

    Media ids are paths ("media-source://media_source/local/Photos/2023"), so every shorter
    prefix that opens is a parent. Prefixes that do not open (opaque ids) are left out.
    """
    chain: list[tuple[str | None, str]] = [(None, ROOT_TITLE)]
    if not media_id or not media_id.startswith(PREFIX):
        return chain
    try:
        top = await asyncio.wait_for(media_source.async_browse_media(hass, None), 15)
        names = {c.media_content_id.removesuffix("/."): c.title for c in top.children or []}
    except (TimeoutError, HomeAssistantError, ValueError):
        names = {}
    parts = media_id.removeprefix(PREFIX).split("/")
    seen: set[str] = set()
    for n in range(1, len(parts) + 1):
        prefix = PREFIX + "/".join(parts[:n])
        try:
            item = await asyncio.wait_for(media_source.async_browse_media(hass, prefix), 15)
        except (TimeoutError, HomeAssistantError, ValueError):
            if n == len(parts):
                chain.append((media_id, parts[-1]))
            continue
        # "media-source://media_source" and ".../local" can be the same folder: keep it once
        same = item.media_content_id.removesuffix("/.")
        if not item.can_expand or same in seen:
            continue
        seen.add(same)
        chain.append((prefix, names.get(prefix) or names.get(same) or item.title or parts[n - 1]))
    if chain[-1][0] != media_id:
        chain[-1] = (media_id, chain[-1][1])
    return chain
