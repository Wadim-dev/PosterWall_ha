"""Constants for PosterWall."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "posterwall"
VERSION: Final = "1.0.2"

STATIC_URL: Final = "/posterwall_static"
CARD_FILE: Final = "posterwall-card.js"
PANEL_FILE: Final = "posterwall-panel.js"
PANEL_URL: Final = "posterwall"
PANEL_ELEMENT: Final = "posterwall-panel"
PANEL_ICON: Final = "mdi:image-frame"
PHOTO_URL: Final = "/api/posterwall/{entry_id}/photo/{photo_id}"

# config entry data
CONF_SOURCE: Final = "source"
SOURCE_MEDIA: Final = "media"
SOURCE_IMMICH: Final = "immich"
SOURCE_SYNOLOGY: Final = "synology"
CONF_FOLDER: Final = "folder"
CONF_FOLDER_TITLE: Final = "folder_title"
CONF_URL: Final = "url"
CONF_API_KEY: Final = "api_key"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_DEVICE_TOKEN: Final = "device_token"

# config entry options
CONF_WEATHER: Final = "weather"
CONF_CALENDARS: Final = "calendars"
CONF_EVENTS: Final = "events"
CONF_EVENT_DAYS: Final = "event_days"
CONF_DEVICES: Final = "devices"  # {target: {"keep": bool}}

DEFAULT_EVENTS: Final = 4
DEFAULT_EVENT_DAYS: Final = 7

# album keys that are not a real album
ALBUM_ALL: Final = "all"
ALBUM_FAVORITES: Final = "favorites"

# live settings (entities of the wall)
SETTINGS_DEFAULTS: Final[dict[str, object]] = {
    "interval": 15,
    "count": 7,
    "size": "medium",
    "effect": "drop",
    "background": "cork",
    "album": ALBUM_ALL,
    "clock": True,
    "weather": True,
    "events": True,
    "caption": False,
    "favorites": True,
    "on_this_day": True,
    "night_mode": "off",
    "night_start": "22:00:00",
    "night_end": "06:30:00",
    "night_brightness": 25,
}
SIZES: Final = ["small", "medium", "large"]
EFFECTS: Final = ["drop", "fade", "blow", "flip", "random"]
BACKGROUNDS: Final = ["cork", "wood", "slate", "black"]
NIGHT_MODES: Final = ["off", "dim", "clock", "dark"]

# limits when reading a photo library
MAX_FOLDERS: Final = 3000
MAX_PHOTOS: Final = 50000
REFRESH_HOURS: Final = 6

SIGNAL_UPDATE: Final = "posterwall_update_{entry_id}"
EVENT_SHOWN: Final = "posterwall_shown"
