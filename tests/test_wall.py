"""A media wall: entities, websocket API, screens, diagnostics, unload."""

from __future__ import annotations

from datetime import datetime, timedelta
import random

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.posterwall.const import DOMAIN
from custom_components.posterwall.diagnostics import async_get_config_entry_diagnostics
from custom_components.posterwall.sources import Photo, date_from_name, pick

from .conftest import FOLDER


async def test_entities(hass: HomeAssistant, loaded: MockConfigEntry) -> None:
    wall = loaded.runtime_data
    assert hass.states.get("sensor.kitchen_photos").state == "6"
    assert hass.states.get("number.kitchen_interval").state == "15"
    album = hass.states.get("select.kitchen_album")
    assert album.attributes["options"] == ["All photos", "2019", "2021", "Phone", "2021 / Summer"]
    assert album.state == "All photos"
    assert hass.states.get("switch.kitchen_favourites_more_often") is None  # media folders know no favourites

    await hass.services.async_call("number", "set_value", {"entity_id": "number.kitchen_interval", "value": 30}, blocking=True)
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.kitchen_date_under_the_photo"}, blocking=True)
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.kitchen_clock"}, blocking=True)
    await hass.services.async_call("select", "select_option", {"entity_id": "select.kitchen_effect", "option": "flip"}, blocking=True)
    await hass.services.async_call("time", "set_value", {"entity_id": "time.kitchen_night_from", "time": "21:30"}, blocking=True)
    await hass.services.async_call("select", "select_option", {"entity_id": "select.kitchen_album", "option": "2021"}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert wall.settings["interval"] == 30 and wall.settings["caption"] and not wall.settings["clock"]
    assert wall.settings["effect"] == "flip" and wall.settings["night_start"] == "21:30:00"
    assert len(wall.photos) == 2
    assert hass.states.get("sensor.kitchen_photos").state == "2"
    assert hass.states.get("time.kitchen_night_from").state == "21:30:00"
    await hass.services.async_call("button", "press", {"entity_id": "button.kitchen_read_photos_again"}, blocking=True)
    assert hass.states.get("sensor.kitchen_photos_read").state != "unknown"

    # settings survive a restart
    await hass.config_entries.async_reload(loaded.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert loaded.runtime_data.settings["interval"] == 30
    assert hass.states.get("select.kitchen_album").state == "2021"


async def test_album_gone(hass: HomeAssistant, loaded: MockConfigEntry, media_dir) -> None:
    wall = loaded.runtime_data
    await wall.async_set("album", f"{FOLDER}/Phone")
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(wall.photos) == 1
    (media_dir / "Photos/Phone/2023-11-25 12.00.00.png").unlink()
    (media_dir / "Photos/Phone").rmdir()
    await wall.async_refresh()
    assert wall.settings["album"] == "all"
    assert len(wall.photos) == 5


async def test_folder_gone(hass: HomeAssistant, loaded: MockConfigEntry, media_dir) -> None:
    import shutil

    wall = loaded.runtime_data
    shutil.rmtree(media_dir / "Photos")
    await wall.async_refresh()
    assert wall.error
    assert len(wall.photos) == 6  # old list stays
    (media_dir / "Photos").mkdir()
    await wall.async_refresh()
    assert wall.error is None and wall.photos == []


async def test_websocket(hass: HomeAssistant, loaded: MockConfigEntry, hass_ws_client) -> None:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "posterwall/walls"})
    walls = (await client.receive_json())["result"]
    assert walls[0]["title"] == "Kitchen" and walls[0]["dashboard"].startswith("posterwall-") and walls[0]["photos"] == 6
    assert "folder" not in walls[0] and walls[0]["folder_title"] == "Photos"  # the name for admins, never the source data

    await client.send_json_auto_id({"type": "posterwall/subscribe", "entry_id": loaded.entry_id})
    assert (await client.receive_json())["success"]
    event = (await client.receive_json())["event"]
    assert event["settings"]["count"] == 7 and event["weather"] == "weather.home" and event["calendars"] == ["calendar.family"]

    await client.send_json_auto_id({"type": "posterwall/set", "entry_id": loaded.entry_id, "key": "count", "value": 9})
    msgs = [await client.receive_json(), await client.receive_json()]
    assert any(m.get("event", {}).get("settings", {}).get("count") == 9 for m in msgs)

    for key, value in (("count", 40), ("effect", "spin"), ("clock", "yes"), ("night_end", "7")):
        await client.send_json_auto_id({"type": "posterwall/set", "entry_id": loaded.entry_id, "key": key, "value": value})
        assert (await client.receive_json())["error"]["code"] == "invalid_format"
    await client.send_json_auto_id({"type": "posterwall/set", "entry_id": loaded.entry_id, "key": "night_end", "value": "07:15"})
    msgs = [await client.receive_json(), await client.receive_json()]
    assert loaded.runtime_data.settings["night_end"] == "07:15:00"

    await client.send_json_auto_id({"type": "posterwall/next", "entry_id": loaded.entry_id, "count": 3})
    res = (await client.receive_json())["result"]
    assert len(res["photos"]) == 3 and res["total"] == 6
    assert all(p["url"].startswith("/media/local/Photos/") and "authSig=" in p["url"] for p in res["photos"])
    assert len({p["id"] for p in res["photos"]}) == 3

    await client.send_json_auto_id({"type": "posterwall/options", "entry_id": loaded.entry_id, "weather": "", "calendars": ["calendar.x"], "events": 2})
    await client.receive_json()
    assert loaded.options["weather"] is None and loaded.options["calendars"] == ["calendar.x"]

    await client.send_json_auto_id({"type": "posterwall/refresh", "entry_id": loaded.entry_id})
    for _ in range(20):
        m = await client.receive_json()
        if m.get("type") == "result" and m["result"]:
            break
    assert m["result"] == {"photos": 6, "error": None}

    await client.send_json_auto_id({"type": "posterwall/next", "entry_id": "nope"})
    assert (await client.receive_json())["error"]["code"] == "not_found"


async def test_photo_media_is_served(hass: HomeAssistant, loaded: MockConfigEntry, hass_ws_client, hass_client_no_auth) -> None:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "posterwall/next", "entry_id": loaded.entry_id})
    url = (await client.receive_json())["result"]["photos"][0]["url"]
    http = await hass_client_no_auth()
    resp = await http.get(url)
    assert resp.status == 200
    assert (await http.get(url.split("?")[0])).status == 401


async def test_screens_and_show(hass: HomeAssistant, loaded: MockConfigEntry, hass_ws_client) -> None:
    hass.config.components.add("cast")
    hass.config.components.add("fully_kiosk")
    hass.config.components.add("browser_mod")
    calls: list[ServiceCall] = []

    async def record(call: ServiceCall) -> None:
        calls.append(call)

    for domain, service in (("cast", "show_lovelace_view"), ("fully_kiosk", "load_url"), ("fully_kiosk", "set_config"), ("browser_mod", "navigate")):
        hass.services.async_register(domain, service, record)
    hass.config.internal_url = "http://ha.local:8123"
    other = MockConfigEntry(domain="cast")
    other.add_to_hass(hass)
    dev_reg, ent_reg = dr.async_get(hass), er.async_get(hass)
    hub = dev_reg.async_get_or_create(config_entry_id=other.entry_id, identifiers={("cast", "hub")}, name="Kitchen display", model="Google Nest Hub")
    ent_reg.async_get_or_create("media_player", "cast", "hub", device_id=hub.id, suggested_object_id="kitchen_display")
    hass.states.async_set("media_player.kitchen_display", "off", {"friendly_name": "Kitchen display"})
    fk = MockConfigEntry(domain="fully_kiosk")
    fk.add_to_hass(hass)
    tablet = dev_reg.async_get_or_create(config_entry_id=fk.entry_id, identifiers={("fully_kiosk", "abc")}, name="Hall tablet")
    bm = MockConfigEntry(domain="browser_mod")
    bm.add_to_hass(hass)
    browser = dev_reg.async_get_or_create(config_entry_id=bm.entry_id, identifiers={("browser_mod", "b-123")}, name="Office browser")

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "posterwall/screens"})
    res = (await client.receive_json())["result"]
    assert [s["id"] for s in res["screens"]] == [f"browser_mod:{browser.id}", f"fully_kiosk:{tablet.id}", "cast:media_player.kitchen_display"] or \
        {s["id"] for s in res["screens"]} == {f"browser_mod:{browser.id}", f"fully_kiosk:{tablet.id}", "cast:media_player.kitchen_display"}
    assert res["cast_ready"] is False

    await client.send_json_auto_id({"type": "posterwall/show", "entry_id": loaded.entry_id, "screen": "cast:media_player.kitchen_display", "keep": True})
    assert (await client.receive_json())["success"]
    path = f"posterwall-{loaded.entry_id[:8].lower()}"
    assert calls[-1].data == {"entity_id": "media_player.kitchen_display", "dashboard_path": path, "view_path": "wall"}
    assert loaded.options["devices"] == {"cast:media_player.kitchen_display": {"keep": True}}

    await client.send_json_auto_id({"type": "posterwall/show", "entry_id": loaded.entry_id, "screen": f"fully_kiosk:{tablet.id}", "keep": True})
    assert (await client.receive_json())["success"]
    assert calls[-2].data["key"] == "startURL" and calls[-1].data["url"] == f"http://ha.local:8123/{path}/wall"

    await client.send_json_auto_id({"type": "posterwall/show", "entry_id": loaded.entry_id, "screen": f"browser_mod:{browser.id}"})
    assert (await client.receive_json())["success"]
    assert calls[-1].data == {"path": f"/{path}/wall", "browser_id": ["b-123"]}

    await client.send_json_auto_id({"type": "posterwall/show", "entry_id": loaded.entry_id, "screen": "tv:1"})
    assert (await client.receive_json())["error"]["code"] == "show_failed"

    # kept screen is started again when it shows nothing, not while it plays music
    n = len(calls)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=3))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(calls) == n + 1
    hass.states.async_set("media_player.kitchen_display", "playing")
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(calls) == n + 1

    await client.send_json_auto_id({"type": "posterwall/keep", "entry_id": loaded.entry_id, "screen": "cast:media_player.kitchen_display", "keep": False})
    assert (await client.receive_json())["success"]
    assert "cast:media_player.kitchen_display" not in loaded.options["devices"]

    await hass.services.async_call(DOMAIN, "show", {"config_entry_id": loaded.entry_id, "screen": "cast:media_player.kitchen_display"}, blocking=True)
    assert calls[-1].domain == "cast"
    with pytest.raises(Exception, match="nknown"):
        await hass.services.async_call(DOMAIN, "show", {"config_entry_id": "nope", "screen": "cast:x"}, blocking=True)


async def test_one_wall_per_kept_screen(hass: HomeAssistant, loaded: MockConfigEntry, hass_ws_client) -> None:
    second = MockConfigEntry(domain=DOMAIN, title="Hall", data=dict(loaded.data), options={})
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    client = await hass_ws_client(hass)
    for entry in (loaded, second):
        await client.send_json_auto_id({"type": "posterwall/keep", "entry_id": entry.entry_id, "screen": "cast:media_player.x", "keep": True})
        assert (await client.receive_json())["success"]
    assert "cast:media_player.x" not in (loaded.options.get("devices") or {})
    assert "cast:media_player.x" in second.options["devices"]


async def test_diagnostics(hass: HomeAssistant, loaded: MockConfigEntry) -> None:
    d = await async_get_config_entry_diagnostics(hass, loaded)
    assert d["photos"] == 6 and d["photos_with_date"] == 4 and d["settings"]["count"] == 7


async def test_unload_and_remove(hass: HomeAssistant, loaded: MockConfigEntry) -> None:
    assert await hass.config_entries.async_unload(loaded.entry_id)
    await hass.config_entries.async_remove(loaded.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not hass.states.async_entity_ids(DOMAIN)


def test_date_from_name() -> None:
    assert date_from_name("IMG_20231125_101010.jpg") == "2023-11-25"
    assert date_from_name("2023-02-30 x.jpg") is None
    assert date_from_name("beach.jpg") is None
    assert date_from_name("123420231125.jpg") is None


def test_pick() -> None:
    today = datetime(2026, 11, 25)
    photos = [Photo(str(i), None) for i in range(20)] + [Photo("old", "2019-11-24"), Photo("fav", None, True)]
    rnd = random.Random(1)
    got = [pick(photos, [], today=today, favorites=True, on_this_day=True, rnd=rnd) for _ in range(300)]
    assert any(p.id == "old" and years == 7 for p, years in got)
    assert sum(p.id == "fav" for p, _ in got) > 40
    assert pick([], [], today=today, favorites=True, on_this_day=True) is None
    # nothing shown just before comes again, unless there is nothing else
    only = [Photo("a"), Photo("b")]
    assert all(pick(only, ["a"], today=today, favorites=False, on_this_day=False, rnd=rnd)[0].id == "b" for _ in range(20))
    assert pick(only, ["a", "b"], today=today, favorites=False, on_this_day=False, rnd=rnd) is not None


async def test_card_and_panel_files(hass: HomeAssistant, loaded: MockConfigEntry, hass_client) -> None:
    assert await async_setup_component(hass, "http", {})
    http = await hass_client()
    for name in ("posterwall-card.js", "posterwall-panel.js"):
        resp = await http.get(f"/posterwall_static/{name}")
        assert resp.status == 200, name


async def test_album_read_completely(hass: HomeAssistant, media_ready) -> None:
    """A chosen folder is read on its own, so a big library never cuts it short."""
    from custom_components.posterwall import sources

    source = sources.MediaPhotoSource(hass, {"folder": FOLDER})
    albums = await source.async_albums()
    assert [a.title for a in albums] == ["2019", "2021", "Phone", "2021 / Summer"]
    old = sources.MAX_PHOTOS
    sources.MAX_PHOTOS = 1
    try:
        everything = await source.async_photos("all")
        summer = await source.async_photos(f"{FOLDER}/2021/Summer")
        year = await source.async_photos(f"{FOLDER}/2019")
    finally:
        sources.MAX_PHOTOS = old
    assert len(everything) == 1
    assert [p.date for p in summer] == ["2021-07-01"]
    assert sorted(p.date for p in year) == ["2019", "2019-11-25"]


async def test_folders_on_the_page(hass: HomeAssistant, loaded: MockConfigEntry, media_dir, hass_ws_client) -> None:
    """The PosterWall page clicks through the real folders, in any depth."""
    from .conftest import JPEG

    deep = media_dir / "Photos/2021/Summer/Beach"
    deep.mkdir()
    (deep / "IMG_20210702_1.jpg").write_bytes(JPEG)
    wall = loaded.runtime_data
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "posterwall/browse", "entry_id": loaded.entry_id})
    res = (await client.receive_json())["result"]
    assert res["folder"]["id"] == FOLDER and res["showing"] == FOLDER
    # top, the local media folder once (not twice), Photos
    assert [c["title"] for c in res["chain"]] == ["Media", "media", "Photos"]
    assert [f["title"] for f in res["folder"]["folders"]] == ["2019", "2021", "Phone"]  # no @eaDir
    assert res["folder"]["photos"] == 1
    summer = f"{FOLDER}/2021/Summer/Beach"
    await client.send_json_auto_id({"type": "posterwall/browse", "entry_id": loaded.entry_id, "folder": summer})
    res = (await client.receive_json())["result"]
    assert res["folder"]["photos"] == 1 and res["chain"][-1]["title"] == "Beach"
    # a folder three levels down becomes the album
    await client.send_json_auto_id({"type": "posterwall/folder", "entry_id": loaded.entry_id, "folder": summer})
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done(wait_background_tasks=True)
    assert wall.settings["album"] == summer and len(wall.photos) == 1
    assert ("media-source://media_source/local/Photos/2021/Summer/Beach", "2021 / Summer / Beach") in wall.album_options()
    assert hass.states.get("select.kitchen_album").state == "2021 / Summer / Beach"
    await client.send_json_auto_id({"type": "posterwall/browse", "entry_id": loaded.entry_id})
    assert (await client.receive_json())["result"]["showing"] == summer
    # the wall's own folder = everything
    await client.send_json_auto_id({"type": "posterwall/folder", "entry_id": loaded.entry_id, "folder": FOLDER})
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done(wait_background_tasks=True)
    assert wall.settings["album"] == "all"
    # a folder outside becomes the new folder of the wall; the wall starts again
    await client.send_json_auto_id({"type": "posterwall/folder", "entry_id": loaded.entry_id, "folder": "media-source://media_source/local"})
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done(wait_background_tasks=True)
    assert loaded.data["folder"] == "media-source://media_source/local"
    assert loaded.data["folder_title"] == "media"
    # unknown folder
    await client.send_json_auto_id({"type": "posterwall/browse", "entry_id": loaded.entry_id, "folder": f"{FOLDER}/nope"})
    assert (await client.receive_json())["error"]["code"] == "browse_failed"
    await client.send_json_auto_id({"type": "posterwall/folder", "entry_id": loaded.entry_id, "folder": "media-source://media_source/nope"})
    assert (await client.receive_json())["error"]["code"] == "browse_failed"


async def test_deep_folder_gone(hass: HomeAssistant, loaded: MockConfigEntry, media_dir) -> None:
    import shutil

    from .conftest import JPEG

    deep = media_dir / "Photos/2021/Summer/Beach"
    deep.mkdir()
    (deep / "a.jpg").write_bytes(JPEG)
    wall = loaded.runtime_data
    await wall.async_set("album", f"{FOLDER}/2021/Summer/Beach")
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(wall.photos) == 1
    shutil.rmtree(deep)
    await wall.async_refresh()
    assert wall.settings["album"] == "all" and not wall.error


async def test_echo_show_techo5(hass: HomeAssistant, loaded: MockConfigEntry, hass_ws_client) -> None:
    """An Echo Show with TECHO5 is found by itself and shows the wall with one tap."""
    from homeassistant.exceptions import HomeAssistantError

    from custom_components.posterwall.devices import async_show, needs_restart

    hass.config.components.add("esphome")
    esp = MockConfigEntry(domain="esphome")
    esp.add_to_hass(hass)
    dev_reg, ent_reg = dr.async_get(hass), er.async_get(hass)
    echo = dev_reg.async_get_or_create(config_entry_id=esp.entry_id, identifiers={("esphome", "show8")}, name="Kitchen Show 8",
                                       model="Echo Show 8")
    ent_reg.async_get_or_create("select", "esphome", "show8-dts", device_id=echo.id, suggested_object_id="show8_dashboard_to_show")
    ent_reg.async_get_or_create("select", "esphome", "show8-d", device_id=echo.id, suggested_object_id="show8_dashboard")
    # an ESPHome device without streaming is no screen
    ent_reg.async_get_or_create("select", "esphome", "other-dts", suggested_object_id="other_dashboard_to_show")
    hass.states.async_set("select.other_dashboard_to_show", "Automatic", {"options": ["Automatic"]})
    hass.states.async_set("select.show8_dashboard", "Off", {"options": ["Off", "Drawn on the device", "Streamed", "Tessera"]})
    hass.states.async_set("select.show8_dashboard_to_show", "Automatic", {"options": ["Automatic", "Overview"]})
    hass.states.async_set("switch.show8_dashboard_when_idle", "off")
    calls: list[ServiceCall] = []

    async def record(call: ServiceCall) -> None:
        calls.append(call)
        if call.domain == "select":
            old = hass.states.get(call.data["entity_id"])
            hass.states.async_set(call.data["entity_id"], call.data["option"], old.attributes)

    hass.services.async_register("select", "select_option", record)
    hass.services.async_register("switch", "turn_on", record)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "posterwall/screens"})
    res = (await client.receive_json())["result"]
    assert [(s["id"], s["kind"], s["name"]) for s in res["screens"]] == [
        ("techo5:select.show8_dashboard_to_show", "techo5", "Kitchen Show 8")]
    screen = "techo5:select.show8_dashboard_to_show"
    # the Echo does not list the page yet
    await client.send_json_auto_id({"type": "posterwall/show", "entry_id": loaded.entry_id, "screen": screen})
    err = (await client.receive_json())["error"]
    assert err["code"] == "show_failed" and "PosterWall Kitchen" in err["message"]
    with pytest.raises(HomeAssistantError):
        await async_show(hass, loaded.entry_id, screen)
    # now it does: one tap sets streaming, the page and "also when idle"
    hass.states.async_set("select.show8_dashboard_to_show", "Automatic", {"options": ["Automatic", "Overview", "PosterWall Kitchen"]})
    await client.send_json_auto_id({"type": "posterwall/show", "entry_id": loaded.entry_id, "screen": screen, "keep": True})
    assert (await client.receive_json())["success"]
    assert hass.states.get("select.show8_dashboard").state == "Streamed"
    assert hass.states.get("select.show8_dashboard_to_show").state == "PosterWall Kitchen"
    assert calls[-1].domain == "switch" and calls[-1].data["entity_id"] == "switch.show8_dashboard_when_idle"
    assert not needs_restart(hass, screen)
    # someone picks another page: "always" brings the wall back
    hass.states.async_set("select.show8_dashboard_to_show", "Overview", {"options": ["Automatic", "Overview", "PosterWall Kitchen"]})
    assert needs_restart(hass, screen)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=3))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("select.show8_dashboard_to_show").state == "PosterWall Kitchen"
    # unknown Echo
    with pytest.raises(HomeAssistantError):
        await async_show(hass, loaded.entry_id, "techo5:select.gone_dashboard_to_show")


async def test_screens_never_hang(hass: HomeAssistant, loaded: MockConfigEntry, hass_ws_client) -> None:
    """A screen whose page stops is loaded again by itself; the button does it at once."""
    from unittest.mock import patch

    from custom_components.posterwall import watchdog as wd
    from custom_components.posterwall.devices import async_reload_screen

    hass.config.components.add("esphome")
    esp = MockConfigEntry(domain="esphome")
    esp.add_to_hass(hass)
    dev_reg, ent_reg = dr.async_get(hass), er.async_get(hass)
    echo = dev_reg.async_get_or_create(config_entry_id=esp.entry_id, identifiers={("esphome", "show8")}, name="Show8")
    ent_reg.async_get_or_create("select", "esphome", "show8-dts", device_id=echo.id, suggested_object_id="show8_dashboard_to_show")
    ent_reg.async_get_or_create("select", "esphome", "show8-d", device_id=echo.id, suggested_object_id="show8_dashboard")
    hass.states.async_set("select.show8_dashboard", "Streamed", {"options": ["Off", "Streamed"]})
    hass.states.async_set("select.show8_dashboard_to_show", "PosterWall Kitchen", {"options": ["Automatic", "PosterWall Kitchen"]})
    hass.states.async_set("light.show8_screen", "on")
    ent_reg.async_get_or_create("button", "esphome", "show8-restart", device_id=echo.id, suggested_object_id="show8_restart",
                                original_device_class="restart")
    calls: list[str] = []

    async def record(call: ServiceCall) -> None:
        calls.append(f"{call.domain}.{call.service}")

    for name in ("show8_dashboard_hide", "show8_dashboard_show"):
        hass.services.async_register("esphome", name, record)

    @callback
    def pressed(event) -> None:
        if event.data["domain"] == "button" and event.data["service_data"].get("entity_id") == "button.show8_restart":
            calls.append("button.press")

    hass.bus.async_listen("call_service", pressed)
    hass.services.async_register("select", "select_option", record)
    hass.services.async_register("switch", "turn_on", record)
    screen = "techo5:select.show8_dashboard_to_show"
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "posterwall/keep", "entry_id": loaded.entry_id, "screen": screen, "keep": True})
    assert (await client.receive_json())["success"]
    wall = loaded.runtime_data
    dog = wall.watchdog
    assert wd.screens_on(hass, wall) == [screen]
    now = dt_util.utcnow() + timedelta(minutes=10)
    # the page reports: all fine
    await client.send_json_auto_id({"type": "posterwall/alive", "entry_id": loaded.entry_id, "client": "abc"})
    assert (await client.receive_json())["success"]
    with patch("custom_components.posterwall.watchdog.dt_util.utcnow", return_value=now), \
            patch("custom_components.posterwall.devices.asyncio.sleep"):
        wall.screens_alive["abc"] = now
        await dog.async_check(now)
        assert dog.short_since is None
        # the page stops reporting: first the pages are told to load again …
        wall.screens_alive["abc"] = now - timedelta(minutes=5)
        token = wall.reload_token
        await dog.async_check(now)
        await dog.async_check(now + timedelta(minutes=1))
        assert wall.reload_token == token + 1 and wall.payload()["reload"] == token + 1 and not calls
        await dog.async_check(now + timedelta(minutes=2))
        assert not calls
        # … and when that does not help, the Echo streams the page anew
        await dog.async_check(now + timedelta(minutes=4))
        assert calls[:2] == ["esphome.show8_dashboard_hide", "esphome.show8_dashboard_show"] and dog.restarts == 1
        # still nothing: the Echo itself restarts
        calls.clear()
        await dog.async_check(now + timedelta(minutes=6))
        assert not calls
        await dog.async_check(now + timedelta(minutes=10))
        assert calls == ["button.press"] and dog.restarts == 2
        # then it gets time to come back before it starts over
        calls.clear()
        await dog.async_check(now + timedelta(minutes=20))
        assert not calls and dog.step == 3
        await dog.async_check(now + timedelta(minutes=31))
        assert dog.step == 0
        await dog.async_check(now + timedelta(minutes=32))
        assert dog.step == 1 and wall.reload_token == token + 2
        # second round without success: the Echo is left alone and a repair says why
        calls.clear()
        for minute in (35, 41, 62):
            await dog.async_check(now + timedelta(minutes=minute))
        assert dog.step == 4 and calls.count("button.press") == 1
        from homeassistant.helpers import issue_registry as ir
        issue = ir.async_get(hass).async_get_issue(DOMAIN, dog.issue_id)
        assert issue is not None and issue.translation_placeholders["screens"] == "Show8"
        calls.clear()
        await dog.async_check(now + timedelta(minutes=120))
        assert not calls and dog.step == 4
        # a page asks for photos again: all fine, the repair goes
        await client.send_json_auto_id({"type": "posterwall/next", "entry_id": loaded.entry_id})
        assert (await client.receive_json())["success"]
        await dog.async_check(now + timedelta(minutes=121))
        assert dog.step == 0 and dog.short_since is None
        assert ir.async_get(hass).async_get_issue(DOMAIN, dog.issue_id) is None
        # the preview in the panel does not count as a screen
        wall.screens_alive.clear()
        await client.send_json_auto_id({"type": "posterwall/next", "entry_id": loaded.entry_id, "preview": True})
        assert (await client.receive_json())["success"]
        assert wall.alive_count(timedelta(minutes=3)) == 0
        # screen off (night): nothing to watch
        hass.states.async_set("light.show8_screen", "off")
        assert wd.screens_on(hass, wall) == []
        hass.states.async_set("light.show8_screen", "on")
        # the button: pages load again at once and the Echo restarts
        calls.clear()
        await hass.services.async_call("button", "press", {"entity_id": "button.kitchen_reload_screens"}, blocking=True)
        assert "button.press" in calls and wall.reload_token == token + 3
        calls.clear()
        await client.send_json_auto_id({"type": "posterwall/reload", "entry_id": loaded.entry_id})
        assert (await client.receive_json())["success"]
        assert calls == ["button.press"]
    # an Echo whose actions are unknown still gets the page set; a failing screen does not stop the others
    hass.services.async_remove("esphome", "show8_dashboard_show")
    calls.clear()
    await async_reload_screen(hass, loaded.entry_id, screen)
    assert "esphome.show8_dashboard_hide" not in calls
    with patch("custom_components.posterwall.watchdog.async_reload_screen", side_effect=RuntimeError("boom")):
        await wd.async_restart_screens(hass, wall, [screen, screen])


async def test_reload_other_screens(hass: HomeAssistant, loaded: MockConfigEntry) -> None:
    """Fully Kiosk and Browser Mod screens load the wall again too."""
    from custom_components.posterwall import watchdog as wd
    from custom_components.posterwall.devices import async_reload_screen

    calls: list[ServiceCall] = []

    async def record(call: ServiceCall) -> None:
        calls.append(call)

    for dom, srv in (("fully_kiosk", "load_url"), ("fully_kiosk", "set_config"), ("browser_mod", "refresh")):
        hass.services.async_register(dom, srv, record)
    fk = MockConfigEntry(domain="fully_kiosk")
    fk.add_to_hass(hass)
    dev_reg, ent_reg = dr.async_get(hass), er.async_get(hass)
    tab = dev_reg.async_get_or_create(config_entry_id=fk.entry_id, identifiers={("fully_kiosk", "tab")}, name="Tablet")
    bm = dev_reg.async_get_or_create(config_entry_id=fk.entry_id, identifiers={("browser_mod", "b1")}, name="Browser")
    await async_reload_screen(hass, loaded.entry_id, f"fully_kiosk:{tab.id}")
    assert calls[-1].service == "load_url"
    await async_reload_screen(hass, loaded.entry_id, f"browser_mod:{bm.id}")
    assert calls[-1].service == "refresh" and calls[-1].data["browser_id"] == ["b1"]
    # a kept tablet counts unless its screen is off
    hass.config_entries.async_update_entry(loaded, options={**loaded.options, "devices": {f"fully_kiosk:{tab.id}": {"keep": True}}})
    assert wd.screens_on(hass, loaded.runtime_data) == [f"fully_kiosk:{tab.id}"]
    ent_reg.async_get_or_create("switch", "fully_kiosk", "tab-screen", device_id=tab.id, translation_key="screen",
                                suggested_object_id="tablet_screen")
    hass.states.async_set("switch.tablet_screen", "off")
    assert wd.screens_on(hass, loaded.runtime_data) == []
