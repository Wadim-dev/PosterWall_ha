"""A media wall: entities, websocket API, screens, diagnostics, unload."""

from __future__ import annotations

from datetime import datetime, timedelta
import random

from homeassistant.core import HomeAssistant, ServiceCall
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
    assert "folder" not in str(walls)

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
