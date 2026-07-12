"""Constants for the Pocket TTS integration."""

from __future__ import annotations

DOMAIN = "pockettts"

DEFAULT_NAME = "Pocket TTS"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8000

# Request timeout in seconds. Pocket TTS runs on CPU and is faster than
# real-time, but long messages can still take a little while.
REQUEST_TIMEOUT = 120

# The add-on ships an English voice-cloning model. Voice selection is handled
# server-side (reference audio), so the integration just needs a language.
SUPPORTED_LANGUAGES = ["en"]
DEFAULT_LANGUAGE = "en"
