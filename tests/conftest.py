"""Fixtures: a media folder with photos, fake Immich and Synology servers."""

from __future__ import annotations

from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.posterwall.const import DOMAIN

JPEG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffdb004300") + b"\x08" * 64 + bytes.fromhex("ffd9")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    return


@pytest.fixture
def media_dir(hass: HomeAssistant, tmp_path: Path) -> Path:
    """media/Photos with years, a phone folder and junk."""
    root = tmp_path / "media"
    for rel in ("Photos/2019/IMG_20191125_101010.jpg", "Photos/2019/beach.jpg", "Photos/2021/PXL_20211124_090000.jpg",
                "Photos/2021/Summer/IMG_20210701_1.jpg", "Photos/Phone/2023-11-25 12.00.00.png", "Photos/@eaDir/thumb.jpg",
                "Photos/readme.txt", "Photos/top.webp"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(JPEG)
    hass.config.media_dirs = {"local": str(root)}
    return root


@pytest.fixture
async def media_ready(hass: HomeAssistant, media_dir: Path) -> None:
    assert await async_setup_component(hass, "media_source", {})
    await hass.async_block_till_done(wait_background_tasks=True)


FOLDER = "media-source://media_source/local/Photos"


@pytest.fixture
def media_entry() -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, title="Kitchen", data={"source": "media", "folder": FOLDER, "folder_title": "Photos"},
                           options={"weather": "weather.home", "calendars": ["calendar.family"], "events": 4, "event_days": 7})


@pytest.fixture
async def loaded(hass: HomeAssistant, media_ready, media_entry: MockConfigEntry):
    media_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(media_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    yield media_entry
