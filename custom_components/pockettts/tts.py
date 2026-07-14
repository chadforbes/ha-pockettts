"""Text-to-speech support for Pocket TTS."""

from __future__ import annotations

import logging

import aiohttp

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PocketTTSConfigEntry
from .const import (
    DEFAULT_LANGUAGE,
    DEFAULT_NAME,
    DOMAIN,
    REQUEST_TIMEOUT,
    SUPPORTED_LANGUAGES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PocketTTSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pocket TTS entity from a config entry."""
    async_add_entities([PocketTTSEntity(config_entry)])


class PocketTTSEntity(TextToSpeechEntity):
    """The Pocket TTS entity."""

    def __init__(self, config_entry: PocketTTSConfigEntry) -> None:
        """Initialize the entity."""
        self._host: str = config_entry.data[CONF_HOST]
        self._port: int = config_entry.data[CONF_PORT]
        self._voices: list[Voice] = []
        self._attr_name = config_entry.title or DEFAULT_NAME
        self._attr_unique_id = config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=config_entry.title or DEFAULT_NAME,
            manufacturer="Kyutai",
            model="Pocket TTS",
        )

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return DEFAULT_LANGUAGE

    @property
    def supported_languages(self) -> list[str]:
        """Return the list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def supported_options(self) -> list[str]:
        """Return the list of supported options."""
        return [ATTR_VOICE]

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return the voices discovered on the Pocket TTS server."""
        return self._voices or None

    async def async_added_to_hass(self) -> None:
        """Fetch the available voices from the server when added."""
        await super().async_added_to_hass()
        session = async_get_clientsession(self.hass)
        url = f"http://{self._host}:{self._port}/voices"
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug("Could not fetch Pocket TTS voices: %s", err)
            return
        self._voices = [
            Voice(voice_id=name, name=name) for name in data.get("voices", [])
        ]

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict
    ) -> TtsAudioType:
        """Load TTS audio from the Pocket TTS server."""
        session = async_get_clientsession(self.hass)
        url = f"http://{self._host}:{self._port}/tts"

        payload: dict[str, str] = {"text": message}
        if voice := options.get(ATTR_VOICE):
            payload["voice"] = voice

        try:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                resp.raise_for_status()
                audio = await resp.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("Error requesting audio from Pocket TTS: %s", err)
            return None, None

        return "wav", audio
