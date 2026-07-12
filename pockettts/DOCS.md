# Pocket TTS Add-on

Runs [Kyutai Pocket TTS](https://github.com/kyutai-labs/pocket-tts) — a small,
fast, **CPU-only** text-to-speech engine — directly on your Home Assistant host.
No external server, no GPU, no cloud.

To keep the container lean it uses the **ONNX** build of Pocket TTS through
[`sherpa-onnx`](https://github.com/k2-fsa/sherpa-onnx) instead of PyTorch. The
add-on serves a small web UI (the Home Assistant ingress panel) and an HTTP API.

## Configuration

| Option | Description |
| --- | --- |
| `num_steps` | Flow-matching steps per generation. Higher = slightly better quality, slower. Default `5`. |
| `num_threads` | CPU threads used for inference. Default `2`. |
| `voice` | Name (or path) of the **default** voice. Leave empty to use the built-in `bria` voice. |

## Voices & adding your own

Pocket TTS clones a voice from a short, clean reference recording. Any `.wav`
you drop into `share/pockettts/` on your Home Assistant host becomes a
selectable voice, listed alongside the bundled samples.

1. Record (or export) a short, clean mono `.wav` of the target voice.
2. Copy it to `share/pockettts/` — for example `share/pockettts/emma.wav`.
3. It appears immediately as the voice **`emma`** (the file name without
   `.wav`), no restart needed.

Pick a voice in three ways:

- **Panel:** choose it from the *Voice* dropdown.
- **Default:** set the `voice` option to a name (e.g. `emma`) to make it the
  default when none is specified.
- **Per message** (via the integration): pass it as a TTS option, e.g.

  ```yaml
  action: tts.speak
  target:
    entity_id: tts.pocket_tts
  data:
    media_player_entity_id: media_player.living_room
    message: "Dinner is ready."
    options:
      voice: emma
  ```

The server also exposes `GET /voices`, which returns the available voice names
and the current default.

## First launch

On the first start the add-on downloads the quantized (int8) ONNX model from the
sherpa-onnx releases into the persistent `/data` volume. This can take a few
minutes; the panel may show errors until it is ready. Restarts afterwards are
fast.

## Requirements & footprint

- **Architectures:** `amd64` and `aarch64`.
- **RAM:** a few hundred MB — much lighter than the PyTorch build.
- The image contains only Python, `sherpa-onnx` (which bundles ONNX Runtime) and
  numpy — no PyTorch, no CUDA, no build tools.

## Using it from automations

The add-on exposes port `8000` (optional — set a host port under the add-on's
**Network** section). Once exposed, install the companion **Pocket TTS
integration** (in the `custom_components` folder of this repository) and point it
at `http://<home-assistant-host>:8000` to use `tts.speak`.
