"""The Pocket TTS integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.TTS]

type PocketTTSConfigEntry = ConfigEntry


async def async_setup_entry(
    hass: HomeAssistant, entry: PocketTTSConfigEntry
) -> bool:
    """Set up Pocket TTS from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PocketTTSConfigEntry
) -> bool:
    """Unload a Pocket TTS config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
