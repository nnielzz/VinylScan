"""The VinylScan integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_PLAYBACKS, DOMAIN
from .services import async_cancel_entry_playbacks, async_register_services, async_unregister_services


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the VinylScan integration."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_PLAYBACKS, {})
    await async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VinylScan from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_PLAYBACKS, {})
    await async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a VinylScan config entry."""

    await async_cancel_entry_playbacks(hass, entry.entry_id)
    if len(hass.config_entries.async_entries(DOMAIN)) <= 1:
        await async_unregister_services(hass)
    return True
