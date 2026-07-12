# Pocket TTS Add-on

Runs [Kyutai Pocket TTS](https://github.com/kyutai-labs/pocket-tts) — a small,
**CPU-only** text-to-speech engine — directly on your Home Assistant host.
No external server, no GPU, no cloud.

This add-on runs the **official full-precision (FP32) `pocket-tts`** library for
the best possible quality. It serves a small web UI (the Home Assistant ingress
panel) and an HTTP API.

## Configuration

| Option | Description |
| --- | --- |
| `language` | Model language: `english` (default) or the preview `*_24l` variants (`french_24l`, `german_24l`, `portuguese_24l`, `italian_24l`, `spanish_24l`). |
| `temperature` | Sampling temperature. Default `0.7`. |
| `eos_threshold` | End-of-speech threshold. Default `-4.0`; raise it (e.g. `0.0`) only if a voice cuts off early. |
| `num_threads` | CPU threads used for inference. Default `2`. |
| `voice` | Name or path of the **default** voice. Leave empty to use `alba`. |

## Voices & adding your own

You can use a bundled voice, clone from an audio file, or load a pre-made
profile. Anything you drop into `share/pockettts/` becomes a selectable voice
(named after the file):

- **Built-in voices** — `alba`, `cosette`, `george`, `giovanni` (it), `lola`
  (es), `juergen` (de), `rafael` (pt), `estelle` (fr), and more. Just pick one.
- **Reference audio** — a clean `.wav`/`.mp3`/`.flac` recording of the target
  voice (short, mono is best). The voice is cloned from it.
- **`.safetensors` profile** — a voice profile exported with `export_model_state`
  (the fastest to load). Drop `myvoice.safetensors` in `share/pockettts/` and it
  appears as **`myvoice`**. This is ideal if you already generated a profile in
  another Pocket TTS project — it reuses the exact same voice with instant load.

Pick a voice three ways:

- **Panel:** choose from the *Voice* dropdown.
- **Default:** set the `voice` option to a name (e.g. `myvoice`).
- **Per message** (via the integration):

  ```yaml
  action: tts.speak
  target:
    entity_id: tts.pocket_tts
  data:
    media_player_entity_id: media_player.living_room
    message: "Dinner is ready."
    options:
      voice: myvoice
  ```

The server also exposes `GET /voices`, which returns the available voice names
and the current default.

## First launch

On the first start the add-on downloads the model from Hugging Face into the
persistent `/data` volume. This can take a few minutes; the panel may show
errors until it is ready. Restarts afterwards are fast. Cloning from a raw audio
file also takes a moment the first time (then it's cached); `.safetensors`
profiles load almost instantly.

## Requirements & footprint

- **Architectures:** `amd64` and `aarch64`.
- **RAM:** roughly 1–2 GB while synthesizing — this is the full PyTorch build,
  so the image and memory use are larger than an ONNX build.

## Using it from automations

The add-on exposes port `8000` (published by default). Install the companion
**Pocket TTS integration** (in the `custom_components` folder of this
repository) and point it at your Home Assistant host on port `8000` to use
`tts.speak`.
