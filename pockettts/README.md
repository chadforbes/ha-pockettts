# Pocket TTS

Runs [Pocket TTS](https://github.com/kyutai-labs/pocket-tts) locally on your
Home Assistant host — a CPU-only text-to-speech engine.

Uses the official **full-precision (FP32)** `pocket-tts` for the best quality.
Adds a sidebar panel for generating speech, with built-in voices, cloning from
a reference `.wav`/`.mp3`, or loading a pre-made `.safetensors` voice profile.
No external server, GPU or cloud required.

The model downloads automatically on first start. See [DOCS.md](DOCS.md) for
details.
