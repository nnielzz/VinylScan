"""Constants for the VinylScan integration."""

from __future__ import annotations

DOMAIN = "vinylscan"

CONF_COLOR_DURATION = "color_duration"
CONF_HUE_SHIFT_DEGREES = "hue_shift_degrees"
CONF_IMAGE_ENTITY_ID = "image_entity_id"
CONF_INITIAL_TRANSITION = "initial_transition"
CONF_LIGHT_ENTITY_IDS = "light_entity_ids"
CONF_LOOP_FOREVER = "loop_forever"
CONF_MAX_COLORS = "max_colors"
CONF_MIN_BRIGHTNESS = "min_brightness"
CONF_NAME = "name"
CONF_SATURATION_BOOST = "saturation_boost"
CONF_STEP_TRANSITION = "step_transition"
CONF_TRANSITION_DURATION = "transition_duration"

DATA_PLAYBACKS = "playbacks"

DEFAULT_COLOR_DURATION = 6.0
DEFAULT_HUE_SHIFT_DEGREES = 0.0
DEFAULT_INITIAL_TRANSITION = 4.0
DEFAULT_LOOP_FOREVER = False
DEFAULT_MAX_COLORS = 5
DEFAULT_MIN_BRIGHTNESS = 26
DEFAULT_NAME = "VinylScan Palette"
DEFAULT_SATURATION_BOOST = 1.35
DEFAULT_STEP_TRANSITION = 6.0
DEFAULT_TRANSITION_DURATION = 3.0

SERVICE_PLAY_IMAGE_PALETTE = "play_image_palette"
SERVICE_STOP_PALETTE_PLAYBACK = "stop_palette_playback"
SERVICE_TRANSITION_TO_COLOR = "transition_to_color"

ATTR_BRIGHTNESS_PCT = "brightness_pct"
ATTR_ENTRY_ID = "entry_id"
ATTR_HEX_COLOR = "hex_color"
ATTR_IMAGE_URL = "image_url"
ATTR_RGB_COLOR = "rgb_color"

UNKNOWN_STATES = {"unknown", "unavailable", ""}
