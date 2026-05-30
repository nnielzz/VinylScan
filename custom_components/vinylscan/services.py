"""Service handlers for the VinylScan integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from functools import partial
import logging
from math import sqrt
from typing import Any

from aiohttp import ClientError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DOMAIN, ATTR_SERVICE, CONF_ENTITY_ID, EVENT_CALL_SERVICE, SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_OFF
from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import color as color_util

from .const import (
    ATTR_BRIGHTNESS_PCT,
    ATTR_ENTRY_ID,
    ATTR_HEX_COLOR,
    ATTR_IMAGE_URL,
    ATTR_RGB_COLOR,
    CONF_COLOR_DURATION,
    CONF_HUE_SHIFT_DEGREES,
    CONF_IMAGE_ENTITY_ID,
    CONF_INITIAL_TRANSITION,
    CONF_LIGHT_ENTITY_IDS,
    CONF_LOOP_FOREVER,
    CONF_MAX_COLORS,
    CONF_MIN_BRIGHTNESS,
    CONF_SATURATION_BOOST,
    CONF_STEP_TRANSITION,
    CONF_TRANSITION_DURATION,
    DATA_PLAYBACKS,
    DEFAULT_COLOR_DURATION,
    DEFAULT_HUE_SHIFT_DEGREES,
    DEFAULT_LOOP_FOREVER,
    DEFAULT_MAX_COLORS,
    DEFAULT_MIN_BRIGHTNESS,
    DEFAULT_SATURATION_BOOST,
    DEFAULT_TRANSITION_DURATION,
    DOMAIN,
    SERVICE_PLAY_IMAGE_PALETTE,
    SERVICE_STOP_PALETTE_PLAYBACK,
    SERVICE_TRANSITION_TO_COLOR,
    UNKNOWN_STATES,
)
from .palette import PaletteExtractionError, extract_dominant_colors, shift_hue

_LOGGER = logging.getLogger(__name__)


PLAY_IMAGE_PALETTE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Optional(CONF_IMAGE_ENTITY_ID): cv.entity_id,
        vol.Optional(ATTR_IMAGE_URL): cv.url,
        vol.Optional(CONF_LIGHT_ENTITY_IDS): vol.All(cv.ensure_list, [cv.entity_id]),
        vol.Optional(CONF_COLOR_DURATION): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=3600)),
        vol.Optional(CONF_TRANSITION_DURATION): vol.All(vol.Coerce(float), vol.Range(min=0, max=3600)),
        vol.Optional(CONF_LOOP_FOREVER): cv.boolean,
        vol.Optional(CONF_HUE_SHIFT_DEGREES): vol.All(vol.Coerce(float), vol.Range(min=0, max=45)),
        vol.Optional(CONF_MAX_COLORS): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
        vol.Optional(CONF_INITIAL_TRANSITION): vol.All(vol.Coerce(float), vol.Range(min=0, max=3600)),
        vol.Optional(CONF_STEP_TRANSITION): vol.All(vol.Coerce(float), vol.Range(min=0, max=3600)),
        vol.Optional(CONF_MIN_BRIGHTNESS): vol.All(vol.Coerce(int), vol.Range(min=1, max=180)),
        vol.Optional(CONF_SATURATION_BOOST): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=3.0)),
        vol.Optional(ATTR_BRIGHTNESS_PCT): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
    }
)

TRANSITION_TO_COLOR_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Optional(CONF_LIGHT_ENTITY_IDS): vol.All(cv.ensure_list, [cv.entity_id]),
        vol.Optional(ATTR_RGB_COLOR): vol.All(
            cv.ensure_list, vol.Length(min=3, max=3), [vol.All(vol.Coerce(int), vol.Range(min=0, max=255))]
        ),
        vol.Optional(ATTR_HEX_COLOR): cv.string,
        vol.Optional(CONF_TRANSITION_DURATION): vol.All(vol.Coerce(float), vol.Range(min=0, max=3600)),
        vol.Optional(CONF_INITIAL_TRANSITION): vol.All(vol.Coerce(float), vol.Range(min=0, max=3600)),
        vol.Optional(ATTR_BRIGHTNESS_PCT): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
    }
)

STOP_PALETTE_PLAYBACK_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Optional(CONF_LIGHT_ENTITY_IDS): vol.All(cv.ensure_list, [cv.entity_id]),
    }
)


@dataclass(slots=True, frozen=True)
class ResolvedConfig:
    """Resolved service config values."""

    entry_id: str
    image_entity_id: str | None
    light_entity_ids: list[str]
    color_duration: float
    transition_duration: float
    loop_forever: bool
    hue_shift_degrees: float
    max_colors: int
    min_brightness: int
    saturation_boost: float


@dataclass(slots=True)
class PlaybackRegistration:
    """Track an active palette playback task."""

    entry_id: str
    light_entity_ids: list[str]
    task: asyncio.Task[None]
    unsubscribe_state_listener: Any = None
    unsubscribe_service_listener: Any = None
    expected_rgb_color: tuple[int, int, int] | None = None
    internal_command_count: int = 0


async def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""

    if hass.services.has_service(DOMAIN, SERVICE_PLAY_IMAGE_PALETTE):
        return

    _get_playback_registry(hass)

    async def handle_play_image_palette(call: ServiceCall) -> None:
        """Play a dominant color palette over the configured lights."""

        config = _resolve_config(hass, call.data)
        image_url = call.data.get(ATTR_IMAGE_URL) or await _resolve_image_url(hass, config.image_entity_id)
        brightness_pct = call.data.get(ATTR_BRIGHTNESS_PCT)

        image_bytes = await _download_image(hass, image_url)
        try:
            colors = await hass.async_add_executor_job(
                partial(
                    extract_dominant_colors,
                    image_bytes,
                    max_colors=config.max_colors,
                    min_brightness=config.min_brightness,
                    saturation_boost=config.saturation_boost,
                )
            )
        except PaletteExtractionError as err:
            raise vol.Invalid(str(err)) from err

        await _cancel_playbacks(
            hass,
            light_entity_ids=config.light_entity_ids,
        )

        task = hass.async_create_task(
            _run_palette_playback(
                hass,
                config=config,
                colors=colors,
                brightness_pct=brightness_pct,
            )
        )
        _register_playback(hass, config.entry_id, config.light_entity_ids, task)

        if not config.loop_forever:
            await task

    async def handle_stop_palette_playback(call: ServiceCall) -> None:
        """Stop a running palette playback."""

        entry_id = call.data.get(ATTR_ENTRY_ID)
        light_entity_ids = call.data.get(CONF_LIGHT_ENTITY_IDS)
        await _cancel_playbacks(hass, entry_id=entry_id, light_entity_ids=light_entity_ids)

    async def handle_transition_to_color(call: ServiceCall) -> None:
        """Transition configured lights to a specific color."""

        config = _resolve_config(hass, call.data)
        rgb_color = _resolve_manual_color(call.data)

        await _cancel_playbacks(
            hass,
            light_entity_ids=config.light_entity_ids,
        )

        await _transition_lights(
            hass,
            light_entity_ids=config.light_entity_ids,
            rgb_color=rgb_color,
            transition=_resolve_transition_duration(call.data, config),
            brightness_pct=call.data.get(ATTR_BRIGHTNESS_PCT),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAY_IMAGE_PALETTE,
        handle_play_image_palette,
        schema=PLAY_IMAGE_PALETTE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_PALETTE_PLAYBACK,
        handle_stop_palette_playback,
        schema=STOP_PALETTE_PLAYBACK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_TRANSITION_TO_COLOR,
        handle_transition_to_color,
        schema=TRANSITION_TO_COLOR_SCHEMA,
    )


async def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister services when the last config entry is removed."""

    await _cancel_playbacks(hass)
    hass.services.async_remove(DOMAIN, SERVICE_PLAY_IMAGE_PALETTE)
    hass.services.async_remove(DOMAIN, SERVICE_STOP_PALETTE_PLAYBACK)
    hass.services.async_remove(DOMAIN, SERVICE_TRANSITION_TO_COLOR)


async def async_cancel_entry_playbacks(hass: HomeAssistant, entry_id: str) -> None:
    """Cancel any active playback for a config entry."""

    await _cancel_playbacks(hass, entry_id=entry_id)


async def _run_palette_playback(
    hass: HomeAssistant,
    *,
    config: ResolvedConfig,
    colors: list[tuple[int, int, int]],
    brightness_pct: int | None,
) -> None:
    """Run one palette playback, optionally forever."""

    while True:
        for color in colors:
            await _play_color(
                hass,
                light_entity_ids=config.light_entity_ids,
                rgb_color=color,
                color_duration=config.color_duration,
                transition_duration=config.transition_duration,
                hue_shift_degrees=config.hue_shift_degrees,
                brightness_pct=brightness_pct,
            )
        if not config.loop_forever:
            return


def _resolve_config(hass: HomeAssistant, service_data: Mapping[str, Any]) -> ResolvedConfig:
    """Resolve config-entry-backed defaults plus service overrides."""

    entry = _resolve_entry(hass, service_data.get(ATTR_ENTRY_ID))
    data = {**entry.data, **entry.options}

    light_entity_ids = service_data.get(CONF_LIGHT_ENTITY_IDS) or data.get(CONF_LIGHT_ENTITY_IDS)
    if not light_entity_ids:
        raise vol.Invalid("No target lights configured")

    return ResolvedConfig(
        entry_id=entry.entry_id,
        image_entity_id=service_data.get(CONF_IMAGE_ENTITY_ID) or data.get(CONF_IMAGE_ENTITY_ID),
        light_entity_ids=list(light_entity_ids),
        color_duration=float(
            service_data.get(
                CONF_COLOR_DURATION,
                data.get(
                    CONF_COLOR_DURATION,
                    data.get(CONF_STEP_TRANSITION, DEFAULT_COLOR_DURATION),
                ),
            )
        ),
        transition_duration=float(
            service_data.get(
                CONF_TRANSITION_DURATION,
                data.get(
                    CONF_TRANSITION_DURATION,
                    data.get(CONF_INITIAL_TRANSITION, DEFAULT_TRANSITION_DURATION),
                ),
            )
        ),
        loop_forever=bool(service_data.get(CONF_LOOP_FOREVER, data.get(CONF_LOOP_FOREVER, DEFAULT_LOOP_FOREVER))),
        hue_shift_degrees=float(
            service_data.get(
                CONF_HUE_SHIFT_DEGREES,
                data.get(CONF_HUE_SHIFT_DEGREES, DEFAULT_HUE_SHIFT_DEGREES),
            )
        ),
        max_colors=int(service_data.get(CONF_MAX_COLORS, data.get(CONF_MAX_COLORS, DEFAULT_MAX_COLORS))),
        min_brightness=int(
            service_data.get(CONF_MIN_BRIGHTNESS, data.get(CONF_MIN_BRIGHTNESS, DEFAULT_MIN_BRIGHTNESS))
        ),
        saturation_boost=float(
            service_data.get(CONF_SATURATION_BOOST, data.get(CONF_SATURATION_BOOST, DEFAULT_SATURATION_BOOST))
        ),
    )


def _resolve_entry(hass: HomeAssistant, entry_id: str | None) -> ConfigEntry:
    """Return the selected or first available config entry."""

    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise vol.Invalid("No VinylScan config entry found")

    if entry_id is None:
        return entries[0]

    for entry in entries:
        if entry.entry_id == entry_id:
            return entry

    raise vol.Invalid(f"Unknown config entry: {entry_id}")


async def _resolve_image_url(hass: HomeAssistant, image_entity_id: str | None) -> str:
    """Resolve the image URL from an entity state."""

    if not image_entity_id:
        raise vol.Invalid("No image entity configured and no image_url provided")

    state = hass.states.get(image_entity_id)
    if state is None or state.state in UNKNOWN_STATES:
        raise vol.Invalid(f"Image entity '{image_entity_id}' has no usable URL")

    return state.state


async def _download_image(hass: HomeAssistant, image_url: str) -> bytes:
    """Download the source image."""

    session = async_get_clientsession(hass)

    try:
        async with session.get(image_url, timeout=20) as response:
            response.raise_for_status()
            return await response.read()
    except (TimeoutError, ClientError) as err:
        raise vol.Invalid(f"Failed to download image from '{image_url}'") from err


async def _play_color(
    hass: HomeAssistant,
    *,
    light_entity_ids: list[str],
    rgb_color: tuple[int, int, int],
    color_duration: float,
    transition_duration: float,
    hue_shift_degrees: float,
    brightness_pct: int | None,
) -> None:
    """Play one color, optionally with a subtle hue-shift animation."""

    variants = _build_color_variants(rgb_color, hue_shift_degrees)
    segment_duration = color_duration / len(variants)
    segment_transition = min(transition_duration, segment_duration)

    for variant in variants:
        await _transition_lights(
            hass,
            light_entity_ids=light_entity_ids,
            rgb_color=variant,
            transition=segment_transition,
            brightness_pct=brightness_pct,
        )
        await asyncio.sleep(segment_duration)


async def _transition_lights(
    hass: HomeAssistant,
    *,
    light_entity_ids: list[str],
    rgb_color: tuple[int, int, int],
    transition: float,
    brightness_pct: int | None,
) -> None:
    """Call light.turn_on for the selected lights."""

    registration = _find_playback_by_lights(hass, light_entity_ids)
    if registration is not None:
        registration.expected_rgb_color = rgb_color
        registration.internal_command_count += 1

    service_data: dict[str, Any] = {
        CONF_ENTITY_ID: light_entity_ids,
        ATTR_RGB_COLOR: list(rgb_color),
        "transition": transition,
    }
    if brightness_pct is not None:
        service_data[ATTR_BRIGHTNESS_PCT] = brightness_pct

    try:
        await hass.services.async_call("light", "turn_on", service_data, blocking=True)
    finally:
        if registration is not None:
            registration.internal_command_count = max(0, registration.internal_command_count - 1)


async def _cancel_playbacks(
    hass: HomeAssistant,
    *,
    entry_id: str | None = None,
    light_entity_ids: list[str] | None = None,
) -> None:
    """Cancel active palette playback tasks matching the filters."""

    playbacks = _get_playback_registry(hass)
    to_cancel: list[PlaybackRegistration] = []

    for registration in playbacks.values():
        if entry_id is not None and registration.entry_id != entry_id:
            continue
        if light_entity_ids is not None and _playback_key(registration.light_entity_ids) != _playback_key(light_entity_ids):
            continue
        to_cancel.append(registration)

    if not to_cancel:
        return

    for registration in to_cancel:
        registration.task.cancel()

    await asyncio.gather(*(registration.task for registration in to_cancel), return_exceptions=True)


def _get_playback_registry(hass: HomeAssistant) -> dict[str, PlaybackRegistration]:
    """Return the in-memory playback registry."""

    return hass.data.setdefault(DOMAIN, {}).setdefault(DATA_PLAYBACKS, {})


def _register_playback(
    hass: HomeAssistant,
    entry_id: str,
    light_entity_ids: list[str],
    task: asyncio.Task[None],
) -> None:
    """Register a playback task and clean it up when it finishes."""

    key = _playback_key(light_entity_ids)
    registry = _get_playback_registry(hass)
    registry[key] = PlaybackRegistration(
        entry_id=entry_id,
        light_entity_ids=list(light_entity_ids),
        task=task,
    )
    registration = registry[key]
    _attach_playback_listeners(hass, registration)

    def _cleanup(done_task: asyncio.Task[None]) -> None:
        current = registry.get(key)
        if current is not None and current.task is done_task:
            registry.pop(key, None)

        _detach_playback_listeners(registration)

        if done_task.cancelled():
            return

        exception = done_task.exception()
        if exception is not None:
            _LOGGER.exception("Palette playback failed", exc_info=exception)

    task.add_done_callback(_cleanup)


def _attach_playback_listeners(hass: HomeAssistant, registration: PlaybackRegistration) -> None:
    """Attach listeners that stop playback when lights are externally changed."""

    @callback
    def _handle_state_change(event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        if new_state.state == STATE_OFF:
            hass.async_create_task(_cancel_playbacks(hass, light_entity_ids=registration.light_entity_ids))
            return

        if registration.internal_command_count > 0 or registration.expected_rgb_color is None:
            return

        actual_rgb = _state_rgb_color(new_state)
        if actual_rgb is None:
            return

        if _rgb_distance(actual_rgb, registration.expected_rgb_color) > 24:
            hass.async_create_task(_cancel_playbacks(hass, light_entity_ids=registration.light_entity_ids))

    @callback
    def _handle_service_call(event) -> None:
        if registration.internal_command_count > 0:
            return

        if event.data.get(ATTR_DOMAIN) != "light":
            return

        service = event.data.get(ATTR_SERVICE)
        if service not in {SERVICE_TURN_ON, SERVICE_TURN_OFF}:
            return

        service_data = event.data.get("service_data") or {}
        target_entity_ids = _normalize_entity_ids(service_data.get(CONF_ENTITY_ID))
        if not target_entity_ids:
            return

        if set(target_entity_ids).intersection(registration.light_entity_ids):
            hass.async_create_task(_cancel_playbacks(hass, light_entity_ids=registration.light_entity_ids))

    registration.unsubscribe_state_listener = async_track_state_change_event(
        hass,
        registration.light_entity_ids,
        _handle_state_change,
    )
    registration.unsubscribe_service_listener = hass.bus.async_listen(
        EVENT_CALL_SERVICE,
        _handle_service_call,
    )


def _detach_playback_listeners(registration: PlaybackRegistration) -> None:
    """Detach listeners for a playback registration."""

    if registration.unsubscribe_state_listener is not None:
        registration.unsubscribe_state_listener()
        registration.unsubscribe_state_listener = None

    if registration.unsubscribe_service_listener is not None:
        registration.unsubscribe_service_listener()
        registration.unsubscribe_service_listener = None


def _build_color_variants(
    rgb_color: tuple[int, int, int],
    hue_shift_degrees: float,
) -> list[tuple[int, int, int]]:
    """Build the animation variants for one color."""

    if hue_shift_degrees <= 0:
        return [rgb_color]

    return [
        rgb_color,
        shift_hue(rgb_color, hue_shift_degrees, value_multiplier=0.82),
        shift_hue(rgb_color, -hue_shift_degrees, value_multiplier=0.82),
    ]


def _resolve_transition_duration(service_data: Mapping[str, Any], config: ResolvedConfig) -> float:
    """Resolve the transition duration for manual color transitions."""

    return float(
        service_data.get(
            CONF_TRANSITION_DURATION,
            service_data.get(CONF_INITIAL_TRANSITION, config.transition_duration),
        )
    )


def _resolve_manual_color(service_data: Mapping[str, Any]) -> tuple[int, int, int]:
    """Resolve a color from either RGB or hex input."""

    if ATTR_RGB_COLOR in service_data:
        rgb = service_data[ATTR_RGB_COLOR]
        return int(rgb[0]), int(rgb[1]), int(rgb[2])

    if ATTR_HEX_COLOR in service_data:
        value = service_data[ATTR_HEX_COLOR].strip().lstrip("#")
        if len(value) != 6:
            raise vol.Invalid("hex_color must be in RRGGBB format")
        return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))

    raise vol.Invalid("Either rgb_color or hex_color is required")


def _playback_key(light_entity_ids: list[str]) -> str:
    """Return the registry key for a light target set."""

    return "|".join(sorted(light_entity_ids))


def _find_playback_by_lights(hass: HomeAssistant, light_entity_ids: list[str]) -> PlaybackRegistration | None:
    """Return the playback registration for the specified lights."""

    return _get_playback_registry(hass).get(_playback_key(light_entity_ids))


def _normalize_entity_ids(entity_ids: Any) -> list[str]:
    """Normalize entity_id service data to a list."""

    if entity_ids is None:
        return []
    if isinstance(entity_ids, str):
        return [entity_ids]
    return [entity_id for entity_id in entity_ids if isinstance(entity_id, str)]


def _state_rgb_color(state) -> tuple[int, int, int] | None:
    """Extract an RGB color from a light state when possible."""

    rgb_color = state.attributes.get(ATTR_RGB_COLOR)
    if rgb_color is not None and len(rgb_color) >= 3:
        return int(rgb_color[0]), int(rgb_color[1]), int(rgb_color[2])

    hs_color = state.attributes.get("hs_color")
    if hs_color is not None and len(hs_color) >= 2:
        rgb = color_util.color_hs_to_RGB(float(hs_color[0]), float(hs_color[1]))
        return int(rgb[0]), int(rgb[1]), int(rgb[2])

    return None


def _rgb_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    """Return Euclidean distance between two RGB colors."""

    return sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))
