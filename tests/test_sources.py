"""Immich and Synology Photos walls with fake servers: albums, photos, favourites, delivery through Home Assistant."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.posterwall.const import DOMAIN
from custom_components.posterwall.sources import SourceError

from .conftest import JPEG
from .test_config_flow import DSM, IMMICH, INFO

ASSETS = [
    {"id": "a1", "type": "IMAGE", "localDateTime": "2019-11-25T10:00:00.000Z", "isFavorite": True},
    {"id": "a2", "type": "IMAGE", "localDateTime": "2022-03-01T10:00:00.000Z", "isFavorite": False},
    {"id": "v1", "type": "VIDEO", "localDateTime": "2022-03-01T10:00:00.000Z"},
    {"id": "t1", "type": "IMAGE", "isTrashed": True},
]


@pytest.fixture
async def immich(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    assert await async_setup_component(hass, "media_source", {})
    aioclient_mock.get(f"{IMMICH}/api/users/me", json={"id": "u"})
    aioclient_mock.get(f"{IMMICH}/api/albums", params={"shared": "true"}, json=[{"id": "al1", "albumName": "Holiday"}, {"id": "al2", "albumName": "Family"}])
    aioclient_mock.get(f"{IMMICH}/api/albums", json=[{"id": "al1", "albumName": "Holiday"}])
    aioclient_mock.post(f"{IMMICH}/api/search/metadata", json={"assets": {"items": ASSETS, "nextPage": None}})
    aioclient_mock.get(f"{IMMICH}/api/assets/a1/thumbnail", content=JPEG, headers={"Content-Type": "image/jpeg"})
    aioclient_mock.get(f"{IMMICH}/api/assets/a2/thumbnail", status=500)
    entry = MockConfigEntry(domain=DOMAIN, title="Lounge", data={"source": "immich", "url": IMMICH, "api_key": "secret", "verify_ssl": True})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def test_immich_wall(hass: HomeAssistant, immich: MockConfigEntry, aioclient_mock: AiohttpClientMocker, hass_ws_client, hass_client_no_auth) -> None:
    wall = immich.runtime_data
    assert [p.id for p in wall.photos] == ["ia1", "ia2"]
    assert wall.photos[0].favorite and wall.photos[0].date == "2019-11-25"
    assert hass.states.get("select.lounge_album").attributes["options"] == ["All photos", "Favourites", "Family", "Holiday"]
    assert hass.states.get("switch.lounge_favourites_more_often").state == "on"
    assert all(c[3].get("x-api-key") == "secret" for c in aioclient_mock.mock_calls if c[3])

    await hass.services.async_call("select", "select_option", {"entity_id": "select.lounge_album", "option": "Favourites"}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    body = aioclient_mock.mock_calls[-1][2]
    assert body["isFavorite"] is True and body["type"] == "IMAGE"
    await hass.services.async_call("select", "select_option", {"entity_id": "select.lounge_album", "option": "Holiday"}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert aioclient_mock.mock_calls[-1][2]["albumIds"] == ["al1"]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "posterwall/walls"})
    assert "secret" not in str(await client.receive_json())
    http = await hass_client_no_auth()
    got = set()
    for _ in range(30):
        await client.send_json_auto_id({"type": "posterwall/next", "entry_id": immich.entry_id})
        photo = (await client.receive_json())["result"]["photos"][0]
        assert photo["url"].startswith(f"/api/posterwall/{immich.entry_id}/photo/") and "secret" not in photo["url"]
        resp = await http.get(photo["url"])
        got.add((photo["id"], resp.status))
    assert ("ia1", 200) in got and ("ia2", 502) in got
    assert (await http.get(f"/api/posterwall/{immich.entry_id}/photo/ia1")).status == 401
    resp = await http.get(await _signed(hass, f"/api/posterwall/{immich.entry_id}/photo/nope"))
    assert resp.status == 404
    resp = await http.get(await _signed(hass, "/api/posterwall/nope/photo/ia1"))
    assert resp.status == 404


async def _signed(hass: HomeAssistant, path: str) -> str:
    from datetime import timedelta

    from homeassistant.components.http.auth import async_sign_path

    return async_sign_path(hass, path, timedelta(minutes=1), use_content_user=True)


async def test_immich_paging_and_errors(hass: HomeAssistant, immich: MockConfigEntry, aioclient_mock: AiohttpClientMocker) -> None:
    source = immich.runtime_data.source
    aioclient_mock.clear_requests()
    aioclient_mock.post(f"{IMMICH}/api/search/metadata", json={"assets": {"items": [ASSETS[0]], "nextPage": "2"}})
    calls = 0

    async def count(*args, **kwargs):
        nonlocal calls
        calls += 1

    photos = []
    # first page says "more", the mock answers the same page again -> stops at MAX_PHOTOS? no: we check two pages
    from custom_components.posterwall import sources

    old = sources.MAX_PHOTOS
    sources.MAX_PHOTOS = 3
    try:
        photos = await source.async_photos("all")
    finally:
        sources.MAX_PHOTOS = old
    assert len(photos) == 3
    aioclient_mock.clear_requests()
    aioclient_mock.post(f"{IMMICH}/api/search/metadata", status=500)
    with pytest.raises(SourceError):
        await source.async_photos("all")
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{IMMICH}/api/users/me", json=["not immich"])
    with pytest.raises(SourceError):
        await source.async_validate()
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{IMMICH}/api/assets/a1/thumbnail", exc=TimeoutError)
    with pytest.raises(SourceError):
        await source.async_fetch(immich.runtime_data.photos[0] if immich.runtime_data.photos else sources.Photo("ia1", extra={"asset": "a1"}))
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{IMMICH}/api/users/me", exc=TimeoutError)
    with pytest.raises(SourceError):
        await source.async_validate()


async def test_immich_not_ready(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"{IMMICH}/api/users/me", status=502)
    entry = MockConfigEntry(domain=DOMAIN, title="X", data={"source": "immich", "url": IMMICH, "api_key": "k", "verify_ssl": True})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state.value == "setup_retry"


def _item(i: int, team: bool = False, **extra) -> dict:
    return {"id": i, "type": "photo", "filename": f"IMG_2020010{i}.jpg", "time": 1574676000 + i, "owner_user_id": 0 if team else 5,
            "additional": {"thumbnail": {"cache_key": f"{i}_c", "xl": "ready", "m": "ready", "sm": "ready"}}, **extra}


@pytest.fixture
async def synology(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    assert await async_setup_component(hass, "media_source", {})
    info = {"success": True, "data": {**INFO["data"], "SYNO.FotoTeam.Browse.Item": {"path": "entry.cgi", "maxVersion": 1},
                                      "SYNO.FotoTeam.Thumbnail": {"path": "entry.cgi", "maxVersion": 1}}}
    aioclient_mock.get(f"{DSM}/webapi/query.cgi", json=info)
    aioclient_mock.post(f"{DSM}/webapi/entry.cgi", json={"success": True, "data": {"sid": "SID1", "did": "D1"}})
    aioclient_mock.get(f"{DSM}/webapi/entry.cgi", params={"api": "SYNO.Foto.Browse.Item", "method": "count"}, json={"success": True, "data": {"count": 2}})
    entry = MockConfigEntry(domain=DOMAIN, title="Hall", data={"source": "synology", "url": DSM, "username": "u", "password": "pw", "verify_ssl": False})
    entry.add_to_hass(hass)
    return entry


async def test_synology_wall(hass: HomeAssistant, synology: MockConfigEntry, aioclient_mock: AiohttpClientMocker) -> None:
    from custom_components.posterwall.sources import SynologyPhotoSource

    calls: list[dict] = []

    async def fake_call(self, api, method, params=None, *, raw=False, post=False, retry=True):
        calls.append({"api": api, "method": method, **(params or {})})
        if api == "SYNO.Foto.Browse.Album":
            return {"list": [{"id": 7, "name": "Trip"}, {"id": 8, "name": "Shared with me", "passphrase": "PP"}]}
        if api.endswith("Browse.Item") and method == "list":
            team = api.startswith("SYNO.FotoTeam")
            return {"list": [_item(1, team), _item(2, team), {"id": 3, "type": "video"}, {"id": 4, "type": "photo", "additional": {}}]}
        if api == "SYNO.API.Auth":
            return {"sid": "S", "device_id": "D2"}
        if api.endswith("Thumbnail"):
            return (JPEG, "image/jpeg")
        return {"count": 2}

    SynologyPhotoSource._real_call = SynologyPhotoSource._call
    try:
        SynologyPhotoSource._call = fake_call
        assert await hass.config_entries.async_setup(synology.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        wall = synology.runtime_data
        assert [p.id for p in wall.photos] == ["s1", "s2"]
        assert wall.photos[0].date == "2019-11-25"
        assert hass.states.get("select.hall_album").attributes["options"] == ["All photos", "Personal space", "Trip", "Shared with me"]
        wall.source._apis = {"SYNO.FotoTeam.Browse.Item": {}}
        await wall.async_refresh()
        assert hass.states.get("select.hall_album").attributes["options"] == ["All photos", "Personal space", "Shared space", "Trip", "Shared with me"]
        for option, expect in (("Shared space", "SYNO.FotoTeam.Browse.Item"), ("Trip", "album_id"), ("Shared with me", "passphrase")):
            await hass.services.async_call("select", "select_option", {"entity_id": "select.hall_album", "option": option}, blocking=True)
            await hass.async_block_till_done(wait_background_tasks=True)
            last = [c for c in calls if c["method"] == "list" and c["api"].endswith("Item")][-1]
            assert expect in (last["api"], *last), (option, last)
        body, _ctype = await wall.source.async_fetch(wall.photos[0])
        assert body == JPEG
        assert calls[-1]["api"] == "SYNO.Foto.Thumbnail" and calls[-1]["passphrase"] == "PP"
    finally:
        SynologyPhotoSource._call = SynologyPhotoSource._real_call


async def test_synology_folders(hass: HomeAssistant, synology: MockConfigEntry) -> None:
    """The real folders of Synology Photos (Photos tab), like on the DiskStation."""
    from custom_components.posterwall.sources import SynologyPhotoSource

    calls: list[dict] = []
    tree = {1: [{"id": 10, "name": "/2019"}, {"id": 11, "name": "/Trips"}, {"id": 13, "name": "/@eaDir"}],
            11: [{"id": 12, "name": "/Trips/Rome"}], 20: [{"id": 21, "name": "/Family"}]}

    async def fake_call(self, api, method, params=None, *, raw=False, post=False, retry=True):
        params = params or {}
        calls.append({"api": api, "method": method, **params})
        if api == "SYNO.API.Auth":
            return {"sid": "S"}
        if api.endswith("Browse.Folder"):
            if method == "get":
                return {"folder": {"id": 20 if "Team" in api else 1, "name": "/"}}
            return {"list": tree.get(params["id"], [])}
        if api == "SYNO.Foto.Browse.Album":
            return {"list": []}
        if api.endswith("Browse.Item") and method == "list":
            return {"list": [_item(params.get("folder_id", 1))]}
        return {"count": 1}

    SynologyPhotoSource._real_call = SynologyPhotoSource._call
    try:
        SynologyPhotoSource._call = fake_call
        assert await hass.config_entries.async_setup(synology.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        wall = synology.runtime_data
        wall.source._apis = {k: {} for k in ("SYNO.Foto.Browse.Folder", "SYNO.FotoTeam.Browse.Folder", "SYNO.FotoTeam.Browse.Item")}
        await wall.async_refresh()
        assert hass.states.get("select.hall_album").attributes["options"] == [
            "All photos", "Personal space", "Personal space / 2019", "Personal space / Trips", "Personal space / Trips / Rome",
            "Shared space", "Shared space / Family"]
        # a folder with everything below it
        await hass.services.async_call("select", "select_option", {"entity_id": "select.hall_album", "option": "Personal space / Trips"},
                                       blocking=True)
        await hass.async_block_till_done(wait_background_tasks=True)
        read = sorted(c["folder_id"] for c in calls if c["method"] == "list" and "folder_id" in c)
        assert read == [11, 12]
        assert len(wall.photos) == 2
        await hass.services.async_call("select", "select_option", {"entity_id": "select.hall_album", "option": "Shared space / Family"},
                                       blocking=True)
        await hass.async_block_till_done(wait_background_tasks=True)
        last = [c for c in calls if c["method"] == "list" and "folder_id" in c][-1]
        assert last == {"api": "SYNO.FotoTeam.Browse.Item", "method": "list", "folder_id": 21, "offset": 0, "limit": 1000,
                        "additional": '["thumbnail"]'}
    finally:
        SynologyPhotoSource._call = SynologyPhotoSource._real_call


async def test_synology_without_folders(hass: HomeAssistant, synology: MockConfigEntry) -> None:
    """Older DiskStations without the folder API keep spaces and albums."""
    from custom_components.posterwall.sources import SourceError as SErr, SynologyPhotoSource

    async def fake_call(self, api, method, params=None, *, raw=False, post=False, retry=True):
        if api.endswith("Browse.Folder"):
            raise SErr("no")
        if api == "SYNO.Foto.Browse.Album":
            return {"list": []}
        return {"list": []} if method == "list" else {"count": 0}

    source = SynologyPhotoSource(hass, dict(synology.data))
    source._sid = "S"
    source._apis = {"SYNO.Foto.Browse.Folder": {}}
    SynologyPhotoSource._real_call = SynologyPhotoSource._call
    try:
        SynologyPhotoSource._call = fake_call
        assert [a.key for a in await source.async_albums()] == ["personal"]
        assert await source.async_photos("f99") == []
    finally:
        SynologyPhotoSource._call = SynologyPhotoSource._real_call


async def test_synology_session_expired(hass: HomeAssistant, synology: MockConfigEntry, aioclient_mock: AiohttpClientMocker) -> None:
    from custom_components.posterwall.sources import SynologyPhotoSource

    source = SynologyPhotoSource(hass, dict(synology.data))
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{DSM}/webapi/query.cgi", json=INFO)
    aioclient_mock.post(f"{DSM}/webapi/entry.cgi", json={"success": True, "data": {"sid": "SID2"}})
    aioclient_mock.get(f"{DSM}/webapi/entry.cgi", json={"success": False, "error": {"code": 119}})
    with pytest.raises(SourceError):
        await source.async_validate()
    logins = [c for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert len(logins) == 2  # logged in again once, then gave up
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{DSM}/webapi/query.cgi", status=500)
    with pytest.raises(SourceError):
        await SynologyPhotoSource(hass, dict(synology.data)).async_validate()
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{DSM}/webapi/query.cgi", json=INFO)
    aioclient_mock.post(f"{DSM}/webapi/entry.cgi", json={"success": True, "data": {"sid": "S"}})
    aioclient_mock.get(f"{DSM}/webapi/entry.cgi", content=JPEG, headers={"Content-Type": "image/jpeg"})
    s = SynologyPhotoSource(hass, dict(synology.data))
    from custom_components.posterwall.sources import Photo

    assert await s.async_fetch(Photo("s1", extra={"id": 1, "cache_key": "c", "size": "xl", "team": False})) == (JPEG, "image/jpeg")


def test_pick_skips_same_file_name() -> None:
    """A copy of a photo in another folder counts as shown."""
    from datetime import datetime
    import random

    from custom_components.posterwall.sources import Photo, pick

    a = Photo("media-source://x/Backup/IMG_1.jpg")
    b = Photo("media-source://x/2019/img_1.JPG")
    c = Photo("media-source://x/2019/IMG_2.jpg")
    for _ in range(20):
        p, _years = pick([a, b, c], [a.id], today=datetime(2026, 11, 25), favorites=False, on_this_day=False, rnd=random.Random())
        assert p is c
