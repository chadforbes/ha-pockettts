# Pocket TTS

Runs [Pocket TTS](https://github.com/kyutai-labs/pocket-tts) locally on your
Home Assistant host — a small, fast, CPU-only text-to-speech engine.

To stay lightweight it uses the ONNX build via
[`sherpa-onnx`](https://github.com/k2-fsa/sherpa-onnx) (no PyTorch). Adds a
sidebar panel for generating speech, with optional voice cloning from a
reference `.wav`. No external server, GPU or cloud required.

The model downloads automatically on first start. See [DOCS.md](DOCS.md) for
details.
