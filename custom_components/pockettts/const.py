"""Constants for the Pocket TTS integration."""

from __future__ import annotations

DOMAIN = "pockettts"

DEFAULT_NAME = "Pocket TTS"
# On Home Assistant OS the add-on's exposed port is reachable on the host, which
# resolves as homeassistant.local. Adjust if HA runs elsewhere.
DEFAULT_HOST = "homeassistant.local"
DEFAULT_PORT = 8000

# Request timeout in seconds. Pocket TTS runs on CPU and is faster than
# real-time, but long messages can still take a little while.
REQUEST_TIMEOUT = 120

# The lean ONNX model is English-only, but Assist pipelines use full locales.
# Advertise the common English locales so the engine matches any of them.
SUPPORTED_LANGUAGES = [
    "en",
    "en-US",
    "en-GB",
    "en-AU",
    "en-CA",
    "en-IE",
    "en-IN",
    "en-NZ",
    "en-ZA",
]
DEFAULT_LANGUAGE = "en-US"
