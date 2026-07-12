#!/usr/bin/env python3
"""Pocket TTS HTTP server backed by the official (FP32) pocket-tts library.

Serves a small web UI (for the Home Assistant ingress panel) and a JSON
``/tts`` endpoint that returns a WAV file. Voices can be built-in names, a
cloned reference file (.wav/.mp3/.flac/...), or a pre-exported .safetensors
voice profile.
"""

from __future__ import annotations

import io
import json
import os
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import numpy as np
import torch
from pocket_tts import TTSModel

LANGUAGE = os.environ.get("LANGUAGE", "english").strip() or "english"
TEMPERATURE = float(os.environ.get("TEMPERATURE", "0.7"))
EOS_THRESHOLD = float(os.environ.get("EOS_THRESHOLD", "-4.0"))
NUM_THREADS = int(os.environ.get("NUM_THREADS", "2"))
PORT = int(os.environ.get("PORT", "8000"))
DEFAULT_VOICE_SPEC = os.environ.get("VOICE", "").strip()

# Folders scanned for user voice files (mounted read-only). Drop a .wav/.mp3 or
# a pre-exported .safetensors profile in any of these and it becomes a voice.
VOICE_DIRS = [
    Path(os.environ.get("VOICES_DIR", "/share/pockettts")),
    Path("/media/pockettts"),
]
VOICE_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".safetensors"}

# Voices bundled with Pocket TTS (usable without providing any files).
BUILTIN_VOICES = [
    "alba", "anna", "azelma", "bill_boerst", "caro_davy", "charles", "cosette",
    "eponine", "eve", "fantine", "george", "jane", "jean", "javert", "marius",
    "mary", "michael", "paul", "peter_yearsley", "stuart_bell", "vera",
    "estelle", "giovanni", "lola", "juergen", "rafael",
]

_generate_lock = threading.Lock()


def log(message: str) -> None:
    print(f"[pockettts] {message}", flush=True)


def build_model() -> TTSModel:
    # NNPACK isn't available on some virtualized CPUs and spams warnings; the
    # normal fallback path works fine, so disable it quietly.
    try:
        torch.backends.nnpack.enabled = False
    except Exception:  # noqa: BLE001 - best-effort, ignore if unavailable
        pass
    torch.set_num_threads(max(1, NUM_THREADS))
    return TTSModel.load_model(
        language=LANGUAGE, temp=TEMPERATURE, eos_threshold=EOS_THRESHOLD
    )


def trim_silence(
    audio: np.ndarray, sample_rate: int, thresh: float = 0.02, pad_s: float = 0.15
) -> np.ndarray:
    """Trim leading/trailing near-silence so end-of-speech doesn't leave gaps."""
    mag = np.abs(audio)
    loud = np.where(mag > thresh * (mag.max() or 1.0))[0]
    if loud.size == 0:
        return audio
    pad = int(pad_s * sample_rate)
    return audio[max(0, loud[0] - pad) : min(len(audio), loud[-1] + pad)]


def encode_wav(samples: np.ndarray, sample_rate: int) -> bytes:
    pcm = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    return buffer.getvalue()


class VoiceManager:
    """Discovers voices (files + built-ins) and caches their model state."""

    def __init__(self, model: TTSModel) -> None:
        self._model = model
        self._states: dict[str, object] = {}

    def catalog(self) -> dict[str, str]:
        """Return {voice_name: spec}; a spec is a file path or a built-in name."""
        voices: dict[str, str] = {}
        for directory in VOICE_DIRS:
            if directory.is_dir():
                for item in sorted(directory.iterdir()):
                    if item.is_file() and item.suffix.lower() in VOICE_SUFFIXES:
                        voices[item.stem] = str(item)
        for name in BUILTIN_VOICES:
            voices.setdefault(name, name)
        if DEFAULT_VOICE_SPEC:
            for candidate in (
                Path(DEFAULT_VOICE_SPEC),
                Path("/share") / DEFAULT_VOICE_SPEC,
                Path("/media") / DEFAULT_VOICE_SPEC,
            ):
                if candidate.is_file():
                    voices[candidate.stem] = str(candidate)
                    break
        return voices

    def names(self) -> list[str]:
        return sorted(self.catalog())

    def default(self) -> str:
        voices = self.catalog()
        if DEFAULT_VOICE_SPEC and Path(DEFAULT_VOICE_SPEC).stem in voices:
            return Path(DEFAULT_VOICE_SPEC).stem
        if DEFAULT_VOICE_SPEC in voices:
            return DEFAULT_VOICE_SPEC
        if "alba" in voices:
            return "alba"
        return next(iter(sorted(voices)), "")

    def state(self, name: str):
        voices = self.catalog()
        key = name if name in voices else self.default()
        spec = voices.get(key)
        if spec is None:
            raise RuntimeError("No voices available")
        cached = self._states.get(key)
        if cached is not None:
            return cached
        state = self._model.get_state_for_audio_prompt(spec)
        self._states[key] = state
        return state


log(f"Loading Pocket TTS model (FP32, language={LANGUAGE})...")
log("First launch downloads the model, which can take a few minutes.")
MODEL = build_model()
VOICES = VoiceManager(MODEL)
for directory in VOICE_DIRS:
    log(f"Voice folder {directory}: {'found' if directory.is_dir() else 'not present'}")
log(f"Available voices: {', '.join(VOICES.names()) or '(none)'}")
log(f"Default voice: {VOICES.default() or '(none)'}")
log("Pocket TTS is ready.")


def synthesize(text: str, voice: str | None = None) -> bytes:
    name = (voice or "").strip() or VOICES.default()
    state = VOICES.state(name)
    with _generate_lock:
        audio = MODEL.generate_audio(state, text)
    samples = np.asarray(audio.detach().cpu().numpy(), dtype=np.float32)
    samples = trim_silence(samples, MODEL.sample_rate)
    if samples.size == 0:
        raise RuntimeError("Pocket TTS produced no audio")
    return encode_wav(samples, MODEL.sample_rate)


def _warmup() -> None:
    """Prime the voice-embedding cache so the first real request is fast."""
    default = VOICES.default()
    if not default:
        return
    try:
        synthesize("Pocket TTS is ready.", default)
        log(f"Warmed up voice '{default}'.")
    except Exception as err:  # noqa: BLE001 - warm-up must never crash startup
        log(f"Warm-up skipped: {err}")


_warmup()


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Pocket TTS</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #f5f7fa; color: #1f2933; margin: 0; padding: 2rem; }
  .card { background: #fff; max-width: 36rem; margin: 0 auto; padding: 1.5rem;
          border-radius: 0.75rem; box-shadow: 0 1px 3px rgba(0,0,0,.1); }
  h1 { font-size: 1.3rem; margin-top: 0; }
  textarea { width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1;
             border-radius: .5rem; padding: .75rem; font: inherit; }
  button { margin-top: .75rem; padding: .6rem 1.2rem; border: 0; border-radius: .5rem;
           background: #2563eb; color: #fff; font: inherit; cursor: pointer; }
  button:disabled { background: #94a3b8; cursor: not-allowed; }
  audio { width: 100%; margin-top: 1rem; }
  .status { margin-top: .75rem; font-size: .9rem; color: #475569; }
  .label { display: block; margin-top: .75rem; font-size: .85rem; color: #475569; }
  select { width: 100%; box-sizing: border-box; padding: .5rem; margin-top: .25rem;
           border: 1px solid #cbd5e1; border-radius: .5rem; font: inherit; }
</style>
</head>
<body>
  <div class="card">
    <h1>Pocket TTS</h1>
    <textarea id="text" rows="4">Hello from Pocket TTS, running locally on Home Assistant.</textarea>
    <label class="label" for="voice">Voice</label>
    <select id="voice"></select>
    <button id="go">Generate audio</button>
    <div class="status" id="status"></div>
    <audio id="player" controls hidden></audio>
  </div>
<script>
const base = window.location.pathname.replace(/\\/+$/, '');
const go = document.getElementById('go');
const status = document.getElementById('status');
const player = document.getElementById('player');
const voice = document.getElementById('voice');

async function loadVoices() {
  try {
    const res = await fetch(base + '/voices');
    const data = await res.json();
    voice.innerHTML = '';
    (data.voices || []).forEach((name) => {
      const opt = document.createElement('option');
      opt.value = name; opt.textContent = name;
      if (name === data.default) opt.selected = true;
      voice.appendChild(opt);
    });
  } catch (e) {
    status.textContent = 'Could not load voices: ' + e.message;
  }
}

go.addEventListener('click', async () => {
  const text = document.getElementById('text').value.trim();
  if (!text) return;
  go.disabled = true; status.textContent = 'Generating...';
  try {
    const res = await fetch(base + '/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, voice: voice.value })
    });
    if (!res.ok) throw new Error('Server error ' + res.status);
    const blob = await res.blob();
    player.src = URL.createObjectURL(blob);
    player.hidden = false; player.play();
    status.textContent = '';
  } catch (e) {
    status.textContent = 'Error: ' + e.message;
  } finally {
    go.disabled = false;
  }
});

loadVoices();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args) -> None:  # noqa: D102 - silence default logging
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - required name
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(200, INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/health":
            self._send(200, b'{"status":"healthy"}', "application/json")
        elif path == "/voices":
            body = json.dumps(
                {"voices": VOICES.names(), "default": VOICES.default()}
            ).encode("utf-8")
            self._send(200, body, "application/json")
        else:
            self._send(404, b"Not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802 - required name
        path = self.path.split("?", 1)[0]
        if not path.endswith("/tts"):
            self._send(404, b"Not found", "text/plain")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        content_type = self.headers.get("Content-Type", "")

        text = ""
        voice = ""
        try:
            if "application/json" in content_type:
                payload = json.loads(raw.decode("utf-8"))
                text = str(payload.get("text", "")).strip()
                voice = str(payload.get("voice", "")).strip()
            else:
                fields = parse_qs(raw.decode("utf-8"))
                text = (fields.get("text", [""])[0]).strip()
                voice = (fields.get("voice", [""])[0]).strip()
        except (ValueError, UnicodeDecodeError):
            self._send(400, b'{"error":"invalid request"}', "application/json")
            return

        if not text:
            self._send(400, b'{"error":"text is required"}', "application/json")
            return

        try:
            audio = synthesize(text, voice)
        except Exception as err:  # noqa: BLE001 - report any synthesis failure
            log(f"Synthesis error: {err}")
            self._send(500, b'{"error":"synthesis failed"}', "application/json")
            return

        self._send(200, audio, "audio/wav")


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)  # noqa: S104 - ingress
    log(f"Listening on :{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
