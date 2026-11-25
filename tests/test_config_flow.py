"""Setting up a wall: media folder, Immich, Synology Photos (with two-factor), reauth, reconfigure, options."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.posterwall.const import DOMAIN

from .conftest import FOLDER

IMMICH = "http://immich.local:2283"
DSM = "https://ds.local:5001"
INFO = {"success": True, "data": {
    "SYNO.API.Auth": {"path": "entry.cgi", "maxVersion": 7, "minVersion": 1},
    "SYNO.Foto.Browse.Item": {"path": "entry.cgi", "maxVersion": 4, "minVersion": 1},
    "SYNO.Foto.Browse.Album": {"path": "entry.cgi", "maxVersion": 4, "minVersion": 1},
    "SYNO.Foto.Thumbnail": {"path": "entry.cgi", "maxVersion": 2, "minVersion": 1},
}}


async def _menu(hass: HomeAssistant, choice: str):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": choice})


async def test_media_folder(hass: HomeAssistant, media_ready) -> None:
    result = await _menu(hass, "media")
    assert result["step_id"] == "folder"
    # root: only folders, no "use" option
    values = [o["value"] for o in result["data_schema"].schema["folder"].config["options"]]
    assert values == [FOLDER]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"folder": FOLDER})
    labels = [o["label"] for o in result["data_schema"].schema["folder"].config["options"]]
    assert not any("@eaDir" in label for label in labels)
    assert result["description_placeholders"]["photos"] == "1"
    # up and down again
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"folder": "__up__"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"folder": FOLDER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"folder": "__use__"})
    assert result["step_id"] == "display"
    hass.states.async_set("weather.home", "sunny")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Kitchen", "weather": "weather.home",
                                                                                "calendars": [], "events": 3, "event_days": 5})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kitchen"
    assert result["data"] == {"source": "media", "folder": FOLDER, "folder_title": "Photos"}
    assert result["options"] == {"weather": "weather.home", "calendars": [], "events": 3, "event_days": 5}


async def test_media_bad_folder(hass: HomeAssistant, media_ready, media_dir) -> None:
    result = await _menu(hass, "media")
    import shutil

    shutil.rmtree(media_dir / "Photos")
    (media_dir / "Photos").write_text("not a folder")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"folder": FOLDER})
    assert result["errors"] == {"base": "browse_failed"}


async def test_immich(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"{IMMICH}/api/users/me", status=401)
    result = await _menu(hass, "immich")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": "immich.local:2283/", "api_key": "bad", "verify_ssl": True})
    assert result["errors"] == {"base": "invalid_auth"}
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{IMMICH}/api/users/me", json={"id": "u1", "name": "Alex"})
    aioclient_mock.get(f"{IMMICH}/api/albums", json=[])
    aioclient_mock.post(f"{IMMICH}/api/search/metadata", json={"assets": {"items": [], "nextPage": None}})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": f"{IMMICH}/api", "api_key": " key ", "verify_ssl": True})
    assert result["step_id"] == "display"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Living room"})
    assert result["data"] == {"source": "immich", "url": IMMICH, "api_key": "key", "verify_ssl": True}
    assert result["options"]["weather"] is None


async def test_immich_unreachable(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"{IMMICH}/api/users/me", exc=TimeoutError)
    result = await _menu(hass, "immich")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": IMMICH, "api_key": "k", "verify_ssl": True})
    assert result["errors"] == {"base": "cannot_connect"}


async def test_synology_with_otp(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"{DSM}/webapi/query.cgi", json=INFO)
    aioclient_mock.post(f"{DSM}/webapi/entry.cgi", json={"success": False, "error": {"code": 403}})
    result = await _menu(hass, "synology")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": DSM, "username": "photos", "password": "pw", "verify_ssl": False})
    assert result["step_id"] == "otp"
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{DSM}/webapi/query.cgi", json=INFO)
    aioclient_mock.post(f"{DSM}/webapi/entry.cgi", json={"success": False, "error": {"code": 404}})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"otp": "000000"})
    assert result["errors"] == {"base": "invalid_auth"}
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{DSM}/webapi/query.cgi", json=INFO)
    aioclient_mock.post(f"{DSM}/webapi/entry.cgi", json={"success": True, "data": {"sid": "S", "device_id": "DEV"}})
    aioclient_mock.get(f"{DSM}/webapi/entry.cgi", json={"success": True, "data": {"count": 3}})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"otp": "123456"})
    assert result["step_id"] == "display"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Hall"})
    assert result["data"]["device_token"] == "DEV"
    assert result["data"]["url"] == DSM
    # the login went in the body, not in the URL
    login = next(c for c in aioclient_mock.mock_calls if c[0] == "POST")
    assert "passwd" not in str(login[1])


async def test_synology_wrong_password(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"{DSM}/webapi/query.cgi", json=INFO)
    aioclient_mock.post(f"{DSM}/webapi/entry.cgi", json={"success": False, "error": {"code": 400}})
    result = await _menu(hass, "synology")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": DSM, "username": "u", "password": "x", "verify_ssl": False})
    assert result["errors"] == {"base": "invalid_auth"}


async def test_synology_without_photos(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    info = {"success": True, "data": {"SYNO.API.Auth": INFO["data"]["SYNO.API.Auth"]}}
    aioclient_mock.get(f"{DSM}/webapi/query.cgi", json=info)
    aioclient_mock.post(f"{DSM}/webapi/entry.cgi", json={"success": True, "data": {"sid": "S"}})
    result = await _menu(hass, "synology")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": DSM, "username": "u", "password": "x", "verify_ssl": False})
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options(hass: HomeAssistant, loaded: MockConfigEntry) -> None:
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"calendars": ["calendar.a", "calendar.b"], "events": 6, "event_days": 14})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert loaded.options["calendars"] == ["calendar.a", "calendar.b"]
    assert loaded.options["weather"] is None
    assert loaded.options["events"] == 6


async def test_reconfigure_media(hass: HomeAssistant, loaded: MockConfigEntry) -> None:
    result = await loaded.start_reconfigure_flow(hass)
    # the source can be changed; the kind the wall has now comes first
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["media", "immich", "synology"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "media"})
    # it starts in the folder the wall shows now, with the way up
    assert result["step_id"] == "folder"
    values = [o["value"] for o in result["data_schema"].schema["folder"].config["options"]]
    assert values[:2] == ["__use__", "__up__"]
    assert f"{FOLDER}/2021" in values
    assert result["description_placeholders"]["path"].endswith("Photos")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"folder": f"{FOLDER}/2021"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"folder": "__use__"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert loaded.data["folder"] == f"{FOLDER}/2021"


async def test_reconfigure_to_immich(hass: HomeAssistant, loaded: MockConfigEntry, aioclient_mock: AiohttpClientMocker) -> None:
    result = await loaded.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "immich"})
    assert result["step_id"] == "immich"
    aioclient_mock.get(f"{IMMICH}/api/users/me", json={"id": "u"})
    aioclient_mock.post(f"{IMMICH}/api/search/metadata", json={"assets": {"items": [], "nextPage": None}})
    aioclient_mock.get(f"{IMMICH}/api/albums", json=[])
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": IMMICH, "api_key": "k", "verify_ssl": True})
    assert result["reason"] == "reconfigure_successful"
    # nothing of the old media source is left
    assert loaded.data == {"source": "immich", "url": IMMICH, "api_key": "k", "verify_ssl": True}


async def test_reauth_immich(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="I", data={"source": "immich", "url": IMMICH, "api_key": "old", "verify_ssl": True})
    entry.add_to_hass(hass)
    aioclient_mock.get(f"{IMMICH}/api/users/me", status=401)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert flows and flows[0]["context"]["source"] == "reauth"
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{IMMICH}/api/users/me", json={"id": "u"})
    aioclient_mock.post(f"{IMMICH}/api/search/metadata", json={"assets": {"items": [], "nextPage": None}})
    aioclient_mock.get(f"{IMMICH}/api/albums", json=[])
    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {"api_key": "new"})
    assert result["reason"] == "reauth_successful"
    assert entry.data["api_key"] == "new"


async def test_reauth_synology_otp(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="S", data={"source": "synology", "url": DSM, "username": "u", "password": "old", "verify_ssl": False})
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    aioclient_mock.get(f"{DSM}/webapi/query.cgi", json=INFO)
    aioclient_mock.post(f"{DSM}/webapi/entry.cgi", json={"success": False, "error": {"code": 403}})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"password": "new"})
    assert result["step_id"] == "otp"
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{DSM}/webapi/query.cgi", json=INFO)
    aioclient_mock.post(f"{DSM}/webapi/entry.cgi", json={"success": False, "error": {"code": 403}})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"otp": "1"})
    assert result["errors"] == {"base": "invalid_otp"}
