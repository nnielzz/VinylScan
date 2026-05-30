"""Config flow for the VinylScan integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_COLOR_DURATION,
    CONF_HUE_SHIFT_DEGREES,
    CONF_IMAGE_ENTITY_ID,
    CONF_INITIAL_TRANSITION,
    CONF_LIGHT_ENTITY_IDS,
    CONF_LOOP_FOREVER,
    CONF_MAX_COLORS,
    CONF_MIN_BRIGHTNESS,
    CONF_NAME,
    CONF_SATURATION_BOOST,
    CONF_STEP_TRANSITION,
    CONF_TRANSITION_DURATION,
    DEFAULT_COLOR_DURATION,
    DEFAULT_HUE_SHIFT_DEGREES,
    DEFAULT_LOOP_FOREVER,
    DEFAULT_MAX_COLORS,
    DEFAULT_MIN_BRIGHTNESS,
    DEFAULT_NAME,
    DEFAULT_SATURATION_BOOST,
    DEFAULT_TRANSITION_DURATION,
    DOMAIN,
)


def _default(defaults: dict[str, Any], key: str) -> Any:
    """Return a voluptuous default value only when present."""

    if key in defaults:
        return defaults[key]
    return vol.UNDEFINED


def _normalize_input(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize selector values before storing them in the config entry."""

    normalized = dict(data)
    normalized[CONF_MAX_COLORS] = int(normalized[CONF_MAX_COLORS])
    normalized[CONF_MIN_BRIGHTNESS] = int(normalized[CONF_MIN_BRIGHTNESS])
    normalized[CONF_COLOR_DURATION] = float(normalized[CONF_COLOR_DURATION])
    normalized[CONF_TRANSITION_DURATION] = float(normalized[CONF_TRANSITION_DURATION])
    normalized[CONF_LOOP_FOREVER] = bool(normalized[CONF_LOOP_FOREVER])
    normalized[CONF_HUE_SHIFT_DEGREES] = float(normalized[CONF_HUE_SHIFT_DEGREES])
    normalized[CONF_SATURATION_BOOST] = float(normalized[CONF_SATURATION_BOOST])
    normalized.pop(CONF_INITIAL_TRANSITION, None)
    normalized.pop(CONF_STEP_TRANSITION, None)
    return normalized


def _build_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Return the config schema used by the config and options flow."""

    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): selector.TextSelector(),
            vol.Required(CONF_IMAGE_ENTITY_ID, default=_default(defaults, CONF_IMAGE_ENTITY_ID)): selector.EntitySelector(
                selector.EntitySelectorConfig()
            ),
            vol.Required(
                CONF_LIGHT_ENTITY_IDS, default=defaults.get(CONF_LIGHT_ENTITY_IDS, [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="light",
                    multiple=True,
                )
            ),
            vol.Required(
                CONF_COLOR_DURATION,
                default=defaults.get(
                    CONF_COLOR_DURATION,
                    defaults.get(CONF_STEP_TRANSITION, DEFAULT_COLOR_DURATION),
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=120,
                    step=0.5,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_TRANSITION_DURATION,
                default=defaults.get(
                    CONF_TRANSITION_DURATION,
                    defaults.get(CONF_INITIAL_TRANSITION, DEFAULT_TRANSITION_DURATION),
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=120,
                    step=0.5,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_MAX_COLORS,
                default=defaults.get(CONF_MAX_COLORS, DEFAULT_MAX_COLORS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=10,
                    step=1,
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                CONF_MIN_BRIGHTNESS,
                default=defaults.get(CONF_MIN_BRIGHTNESS, DEFAULT_MIN_BRIGHTNESS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=180,
                    step=1,
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                CONF_LOOP_FOREVER,
                default=defaults.get(CONF_LOOP_FOREVER, DEFAULT_LOOP_FOREVER),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_HUE_SHIFT_DEGREES,
                default=defaults.get(CONF_HUE_SHIFT_DEGREES, DEFAULT_HUE_SHIFT_DEGREES),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=45,
                    step=0.5,
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                CONF_SATURATION_BOOST,
                default=defaults.get(CONF_SATURATION_BOOST, DEFAULT_SATURATION_BOOST),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1.0,
                    max=3.0,
                    step=0.05,
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
        }
    )


class VinylScanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VinylScan."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""

        if user_input is not None:
            normalized = _normalize_input(user_input)
            return self.async_create_entry(
                title=normalized[CONF_NAME],
                data=normalized,
            )

        return self.async_show_form(step_id="user", data_schema=_build_schema({}))

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow."""

        return VinylScanOptionsFlow(config_entry)


class VinylScanOptionsFlow(config_entries.OptionsFlow):
    """Handle VinylScan options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""

        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage the integration options."""

        if user_input is not None:
            return self.async_create_entry(title="", data=_normalize_input(user_input))

        defaults = {**self._config_entry.data, **self._config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_build_schema(defaults))
