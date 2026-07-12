# Pocket TTS for Home Assistant

Two ways to use [Kyutai Pocket TTS](https://github.com/kyutai-labs/pocket-tts) —
a small, fast, CPU-only, local text-to-speech engine — with Home Assistant:

1. **Add-on** (`pockettts/`) — runs Pocket TTS **locally on the Home Assistant
   host** and shows its web UI as a sidebar panel. No external server needed.
2. **Integration** (`custom_components/pockettts/`) — a proper HA **TTS provider**
   so automations can speak through Pocket TTS with `tts.speak`.

---

## Add-on: local Pocket TTS server + panel

The add-on runs Pocket TTS inside a lean container. To avoid a heavy image it
uses the **ONNX** build via [`sherpa-onnx`](https://github.com/k2-fsa/sherpa-onnx)
(no PyTorch) — just Python, `sherpa-onnx` and numpy.

### Install

1. In Home Assistant go to **Settings → Add-ons → Add-on Store**.
2. Open the **⋮** menu (top-right) → **Repositories**.
3. Add this repository URL:
   `https://github.com/chadforbes/ha-pockettts`
4. Find **Pocket TTS** in the store, click **Install**, then **Start**.
5. (Optional) In the add-on's **Configuration** tab adjust `num_steps`,
   `num_threads`, or set a `voice` reference `.wav` for cloning.
6. Open the **Pocket TTS** panel from the sidebar. The first start downloads the
   ONNX model (a few minutes); it is cached in `/data` afterwards.

The add-on is built locally by the Home Assistant Supervisor from prebuilt
wheels (no compilation), so it installs quickly. **`amd64` and `aarch64` are
supported.**

---

## Integration: TTS provider for automations

### Install

**HACS (recommended):** add this repo as a custom repository (category
*Integration*), install **Pocket TTS**, then restart Home Assistant.

**Manual:** copy `custom_components/pockettts` into your
`config/custom_components` directory and restart.

### Configure

1. **Settings → Devices & Services → Add Integration → Pocket TTS**.
2. Enter the **host** and **port** of the Pocket TTS server. On Home Assistant
   OS, expose the add-on's port `8000` (add-on **Configuration → Network**) and
   use host `homeassistant.local`, port `8000`.

This creates a `tts.pocket_tts` entity that appears as a selectable
Text-to-speech engine throughout Home Assistant.

### Use it

**In automations / scripts:**

```yaml
action: tts.speak
target:
  entity_id: tts.pocket_tts
data:
  media_player_entity_id: media_player.living_room
  message: "Hello from Pocket TTS!"
```

**In an Assist voice pipeline:** go to **Settings → Voice assistants**, edit
your pipeline, and pick **Pocket TTS** under *Text-to-speech* (with the voice you
want). Your voice satellites will then reply using Pocket TTS.

> The lean ONNX model is **English-only**. The integration advertises English
> locales (en-US, en-GB, …) so it matches any English Assist pipeline.

---

## Voices

The ONNX build clones a voice from a reference recording. Drop your own `.wav`
files into `share/pockettts/` and they become selectable voices (named after the
file). Choose a voice from the add-on **panel**, set a default via the add-on's
`voice` option, or pick one per message from the integration:

```yaml
action: tts.speak
target:
  entity_id: tts.pocket_tts
data:
  media_player_entity_id: media_player.living_room
  message: "Hello from Pocket TTS!"
  options:
    voice: emma
```

See the add-on [DOCS.md](pockettts/DOCS.md) for details.

## Notes

- This is a community project and is not affiliated with Kyutai or the
  sherpa-onnx authors.
