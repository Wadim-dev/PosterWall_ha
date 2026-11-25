"""Delivers Immich and Synology photos to the displays (signed, short-lived URLs)."""

from __future__ import annotations

from http import HTTPStatus
import logging

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView

from .const import DOMAIN
from .sources import SourceError

_LOGGER = logging.getLogger(__name__)


class PhotoView(HomeAssistantView):
    """GET /api/posterwall/<entry_id>/photo/<photo_id>."""

    url = "/api/posterwall/{entry_id}/photo/{photo_id}"
    name = "api:posterwall:photo"
    requires_auth = True

    async def get(self, request: web.Request, entry_id: str, photo_id: str) -> web.StreamResponse:
        hass = request.app[KEY_HASS]
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN or not hasattr(entry, "runtime_data"):
            return web.Response(status=HTTPStatus.NOT_FOUND)
        wall = entry.runtime_data
        photo = wall.photo(photo_id)
        if photo is None or not wall.source.proxied:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        try:
            body, content_type = await wall.source.async_fetch(photo)
        except SourceError as err:
            _LOGGER.debug("Photo %s could not be fetched: %s", photo_id, err)
            return web.Response(status=HTTPStatus.BAD_GATEWAY)
        return web.Response(body=body, content_type=content_type.split(";")[0],
                            headers={"Cache-Control": "private, max-age=3600"})
