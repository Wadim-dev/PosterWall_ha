"""Set up a wall in a few clicks: pick the photos, weather and calendars, done."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components import media_source
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

from .const import (
    CONF_API_KEY,
    CONF_CALENDARS,
    CONF_DEVICE_TOKEN,
    CONF_EVENT_DAYS,
    CONF_EVENTS,
    CONF_FOLDER,
    CONF_FOLDER_TITLE,
    CONF_PASSWORD,
    CONF_SOURCE,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONF_WEATHER,
    DEFAULT_EVENT_DAYS,
    DEFAULT_EVENTS,
    DOMAIN,
    SOURCE_IMMICH,
    SOURCE_MEDIA,
    SOURCE_SYNOLOGY,
)
from .sources import BROWSER_IMAGE, SKIP_FOLDER, AuthError, OtpRequired, SourceError, create_source

USE = "__use__"
UP = "__up__"
OTP = "otp"
# media sources that never hold photos
NO_PHOTOS = {"camera", "radio_browser", "tts", "music_assistant", "ai_task"}


def _url(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        value = f"http://{value}"
    return value.removesuffix("/api")


def _display_schema(hass: Any, defaults: Mapping[str, Any], name: str | None = None) -> vol.Schema:
    weather = next(iter(sorted(hass.states.async_entity_ids("weather"))), None)
    fields: dict[Any, Any] = {}
    if name is not None:
        fields[vol.Required("name", default=name)] = TextSelector()
    w = defaults.get(CONF_WEATHER, weather)
    fields[vol.Optional(CONF_WEATHER, **({"description": {"suggested_value": w}} if w else {}))] = EntitySelector(
        EntitySelectorConfig(domain="weather"))
    fields[vol.Optional(CONF_CALENDARS, default=list(defaults.get(CONF_CALENDARS) or []))] = EntitySelector(
        EntitySelectorConfig(domain="calendar", multiple=True))
    fields[vol.Optional(CONF_EVENTS, default=int(defaults.get(CONF_EVENTS, DEFAULT_EVENTS)))] = NumberSelector(
        NumberSelectorConfig(min=1, max=10, step=1, mode=NumberSelectorMode.SLIDER))
    fields[vol.Optional(CONF_EVENT_DAYS, default=int(defaults.get(CONF_EVENT_DAYS, DEFAULT_EVENT_DAYS)))] = NumberSelector(
        NumberSelectorConfig(min=1, max=31, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="d"))
    return vol.Schema(fields)


def _display_options(user_input: Mapping[str, Any]) -> dict[str, Any]:
    return {
        CONF_WEATHER: user_input.get(CONF_WEATHER) or None,
        CONF_CALENDARS: list(user_input.get(CONF_CALENDARS) or []),
        CONF_EVENTS: int(user_input.get(CONF_EVENTS, DEFAULT_EVENTS)),
        CONF_EVENT_DAYS: int(user_input.get(CONF_EVENT_DAYS, DEFAULT_EVENT_DAYS)),
    }


class PosterWallConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a wall."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._path: list[tuple[str | None, str]] = [(None, "Media")]
        self._children: list[tuple[str, str]] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PosterWallOptionsFlow()

    # ------------------------------------------------------------ choose source

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["media", "immich", "synology"])

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        self._data = dict(entry.data)
        kind = entry.data.get(CONF_SOURCE, SOURCE_MEDIA)
        return await getattr(self, f"async_step_{kind}")()

    # ------------------------------------------------------------ HA media

    async def async_step_media(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        self._data = {**self._data, CONF_SOURCE: SOURCE_MEDIA}
        return await self.async_step_folder()

    async def async_step_folder(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Click through the media browser to the folder with the photos."""
        errors: dict[str, str] = {}
        if user_input is not None:
            choice = user_input[CONF_FOLDER]
            if choice == USE:
                folder, title = self._path[-1]
                if folder is None:
                    errors["base"] = "pick_folder"
                else:
                    self._data[CONF_FOLDER] = folder
                    self._data[CONF_FOLDER_TITLE] = " / ".join(t for _, t in self._path[1:]) or title
                    return await self._finish_source()
            elif choice == UP:
                if len(self._path) > 1:
                    self._path.pop()
            else:
                title = next((t for i, t in self._children if i == choice), choice)
                self._path.append((choice, title))
        try:
            item = await media_source.async_browse_media(self.hass, self._path[-1][0])
        except (HomeAssistantError, ValueError):
            if len(self._path) > 1:
                self._path.pop()
            errors["base"] = "browse_failed"
            item = await media_source.async_browse_media(self.hass, self._path[-1][0])
        children = item.children or []
        self._children = [(c.media_content_id, c.title) for c in children if c.can_expand and not SKIP_FOLDER.search(c.title or "")
                          and c.media_content_id.split("/")[2] not in NO_PHOTOS]
        here = sum(1 for c in children if not c.can_expand and (BROWSER_IMAGE.search(c.title or "")
                                                                  or (c.media_content_type or "").startswith("image/")))
        options: list[SelectOptionDict] = []
        if self._path[-1][0] is not None:
            options.append(SelectOptionDict(value=USE, label=f"✓ {self._path[-1][1]}"))
        if len(self._path) > 1:
            options.append(SelectOptionDict(value=UP, label="↑ .."))
        options += [SelectOptionDict(value=i, label=f"📁 {t}") for i, t in self._children]
        return self.async_show_form(
            step_id="folder",
            data_schema=vol.Schema({vol.Required(CONF_FOLDER): SelectSelector(
                SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST))}),
            description_placeholders={"path": " / ".join(t for _, t in self._path) or "Media", "photos": str(here),
                                      "folders": str(len(self._children))},
            errors=errors,
        )

    # ------------------------------------------------------------ Immich

    async def async_step_immich(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**self._data, CONF_SOURCE: SOURCE_IMMICH, CONF_URL: _url(user_input[CONF_URL]),
                    CONF_API_KEY: user_input[CONF_API_KEY].strip(), CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL]}
            errors = await self._test(data)
            if not errors:
                self._data = data
                return await self._finish_source()
        d = user_input or self._data
        return self.async_show_form(
            step_id="immich",
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default=d.get(CONF_URL, "")): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
                vol.Required(CONF_API_KEY, default=d.get(CONF_API_KEY, "")): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                vol.Required(CONF_VERIFY_SSL, default=d.get(CONF_VERIFY_SSL, True)): BooleanSelector(),
            }),
            errors=errors,
        )

    # ------------------------------------------------------------ Synology Photos

    async def async_step_synology(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**self._data, CONF_SOURCE: SOURCE_SYNOLOGY, CONF_URL: _url(user_input[CONF_URL]),
                    CONF_USERNAME: user_input[CONF_USERNAME].strip(), CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL]}
            data.pop(CONF_DEVICE_TOKEN, None)
            errors = await self._test(data)
            self._data = data
            if errors.get("base") == OTP:
                return await self.async_step_otp()
            if not errors:
                return await self._finish_source()
        d = user_input or self._data
        return self.async_show_form(
            step_id="synology",
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default=d.get(CONF_URL, "")): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
                vol.Required(CONF_USERNAME, default=d.get(CONF_USERNAME, "")): TextSelector(),
                vol.Required(CONF_PASSWORD, default=d.get(CONF_PASSWORD, "")): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                vol.Required(CONF_VERIFY_SSL, default=d.get(CONF_VERIFY_SSL, False)): BooleanSelector(),
            }),
            errors=errors,
        )

    async def async_step_otp(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Two-factor code of the DiskStation (asked once; the DiskStation then trusts PosterWall)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._test(self._data, otp=str(user_input[OTP]).strip())
            if not errors:
                return await self._finish_source()
            if errors.get("base") == OTP:
                errors = {"base": "invalid_otp"}
        return self.async_show_form(step_id="otp", data_schema=vol.Schema({vol.Required(OTP): TextSelector()}), errors=errors)

    async def _test(self, data: dict[str, Any], otp: str | None = None) -> dict[str, str]:
        source = create_source(self.hass, data, otp)
        try:
            await source.async_validate()
        except OtpRequired:
            return {"base": OTP}
        except AuthError:
            return {"base": "invalid_auth"}
        except SourceError:
            return {"base": "cannot_connect"}
        if source.device_token:
            data[CONF_DEVICE_TOKEN] = source.device_token
        return {}

    # ------------------------------------------------------------ finish

    async def _finish_source(self) -> ConfigFlowResult:
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(self._get_reconfigure_entry(), data=self._data)
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data=self._data)
        return await self.async_step_display()

    async def async_step_display(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Name, weather and calendars."""
        if user_input is not None:
            return self.async_create_entry(title=user_input["name"].strip() or "PosterWall", data=self._data,
                                           options=_display_options(user_input))
        kind = self._data[CONF_SOURCE]
        default = {SOURCE_IMMICH: "Immich", SOURCE_SYNOLOGY: "Synology Photos"}.get(kind) or self._data.get(CONF_FOLDER_TITLE, "")
        count = len(self._async_current_entries())
        name = "PosterWall" if not count else f"PosterWall {count + 1}"
        return self.async_show_form(step_id="display", data_schema=_display_schema(self.hass, {}, name),
                                    description_placeholders={"source": str(default)})

    # ------------------------------------------------------------ reauth

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        self._data = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        kind = self._data.get(CONF_SOURCE)
        secret = CONF_API_KEY if kind == SOURCE_IMMICH else CONF_PASSWORD
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**self._data, secret: user_input[secret]}
            errors = await self._test(data)
            self._data = data
            if errors.get("base") == OTP:
                return await self.async_step_otp()
            if not errors:
                return await self._finish_source()
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(secret): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}),
            description_placeholders={"url": str(self._data.get(CONF_URL, ""))},
            errors=errors,
        )


class PosterWallOptionsFlow(OptionsFlow):
    """Weather and calendars of a wall (everything else is in the PosterWall panel)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={**self.config_entry.options, **_display_options(user_input)})
        return self.async_show_form(step_id="init", data_schema=_display_schema(self.hass, self.config_entry.options))
