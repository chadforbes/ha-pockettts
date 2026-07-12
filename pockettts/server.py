#!/usr/bin/env python3
"""Lightweight Pocket TTS HTTP server backed by sherpa-onnx (ONNX Runtime).

No PyTorch. Uses only the sherpa-onnx wheel + numpy + the Python standard
library. Serves a small web UI (for the Home Assistant ingress panel) and a
JSON ``/tts`` endpoint that returns a WAV file.
"""

from __future__ import annotations

import io
import json
import os
import tarfile
import threading
import urllib.request
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import numpy as np
import sherpa_onnx

MODEL_NAME = "sherpa-onnx-pocket-tts-int8-2026-01-26"
MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
    f"{MODEL_NAME}.tar.bz2"
)
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
MODEL_DIR = DATA_DIR / MODEL_NAME

NUM_STEPS = int(os.environ.get("NUM_STEPS", "5"))
NUM_THREADS = int(os.environ.get("NUM_THREADS", "2"))
PORT = int(os.environ.get("PORT", "8000"))
DEFAULT_VOICE_SPEC = os.environ.get("VOICE_WAV", "").strip()

# Folders scanned for user voice .wav files (mounted read-only). Drop a .wav in
# any of these on your Home Assistant host and it becomes a selectable voice.
VOICE_DIRS = [
    Path(os.environ.get("VOICES_DIR", "/share/pockettts")),
    Path("/media/pockettts"),
]

_generate_lock = threading.Lock()


def log(message: str) -> None:
    print(f"[pockettts] {message}", flush=True)


def ensure_model() -> None:
    """Download and extract the ONNX model on first run (cached in /data)."""
    if MODEL_DIR.is_dir():
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    archive = DATA_DIR / f"{MODEL_NAME}.tar.bz2"
    log(f"Downloading model from {MODEL_URL} (first run only)...")
    urllib.request.urlretrieve(MODEL_URL, archive)  # noqa: S310 - fixed URL
    log("Extracting model...")
    with tarfile.open(archive, "r:bz2") as tar:
        tar.extractall(DATA_DIR)
    archive.unlink(missing_ok=True)
    log("Model ready.")


def build_tts() -> "sherpa_onnx.OfflineTts":
    config = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            pocket=sherpa_onnx.OfflineTtsPocketModelConfig(
                lm_flow=str(MODEL_DIR / "lm_flow.int8.onnx"),
                lm_main=str(MODEL_DIR / "lm_main.int8.onnx"),
                encoder=str(MODEL_DIR / "encoder.onnx"),
                decoder=str(MODEL_DIR / "decoder.int8.onnx"),
                text_conditioner=str(MODEL_DIR / "text_conditioner.onnx"),
                vocab_json=str(MODEL_DIR / "vocab.json"),
                token_scores_json=str(MODEL_DIR / "token_scores.json"),
            ),
            num_threads=NUM_THREADS,
            provider="cpu",
        )
    )
    if not config.validate():
        raise SystemExit("Invalid sherpa-onnx TTS configuration")
    return sherpa_onnx.OfflineTts(config)


def load_reference(path: Path, target_sr: int) -> np.ndarray:
    """Load a WAV file as mono float32 resampled to target_sr."""
    with wave.open(str(path), "rb") as w:
        frames = w.readframes(w.getnframes())
        sample_rate = w.getframerate()
        channels = w.getnchannels()
        width = w.getsampwidth()

    if width == 2:
        data = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 4:
        data = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648.0
    else:  # 8-bit unsigned
        data = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128) / 128.0

    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)

    if sample_rate != target_sr and len(data) > 1:
        new_len = int(round(len(data) * target_sr / sample_rate))
        data = np.interp(
            np.linspace(0, len(data) - 1, new_len),
            np.arange(len(data)),
            data,
        ).astype(np.float32)

    return np.ascontiguousarray(data, dtype=np.float32)


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
    """Discovers voice .wav files and caches their reference audio."""

    def __init__(self, sample_rate: int) -> None:
        self._sample_rate = sample_rate
        self._cache: dict[str, tuple[float, np.ndarray]] = {}

    def catalog(self) -> dict[str, Path]:
        """Return {voice_name: path}; user voices override bundled ones."""
        voices: dict[str, Path] = {}
        for directory in (MODEL_DIR / "test_wavs", *VOICE_DIRS):
            if directory.is_dir():
                for wav in sorted(directory.iterdir()):
                    if wav.is_file() and wav.suffix.lower() == ".wav":
                        voices[wav.stem] = wav
        # Allow a configured path that lives outside those folders.
        if DEFAULT_VOICE_SPEC:
            for candidate in (
                Path(DEFAULT_VOICE_SPEC),
                Path("/share") / DEFAULT_VOICE_SPEC,
            ):
                if candidate.is_file():
                    voices[candidate.stem] = candidate
                    break
        return voices

    def names(self) -> list[str]:
        return sorted(self.catalog())

    def default(self) -> str:
        voices = self.catalog()
        if DEFAULT_VOICE_SPEC and Path(DEFAULT_VOICE_SPEC).stem in voices:
            return Path(DEFAULT_VOICE_SPEC).stem
        if "bria" in voices:
            return "bria"
        return next(iter(sorted(voices)), "")

    def reference(self, name: str) -> np.ndarray:
        voices = self.catalog()
        path = voices.get(name) or voices.get(self.default())
        if path is None:
            raise RuntimeError("No voices available")
        mtime = path.stat().st_mtime
        cached = self._cache.get(name)
        if cached and cached[0] == mtime:
            return cached[1]
        ref = load_reference(path, self._sample_rate)
        self._cache[name] = (mtime, ref)
        return ref


ensure_model()
log("Loading Pocket TTS model (sherpa-onnx)...")
TTS = build_tts()
VOICES = VoiceManager(TTS.sample_rate)
for directory in VOICE_DIRS:
    log(f"Voice folder {directory}: {'found' if directory.is_dir() else 'not present'}")
log(f"Available voices: {', '.join(VOICES.names()) or '(none)'}")
log(f"Default voice: {VOICES.default() or '(none)'}")
log("Pocket TTS is ready.")


def synthesize(text: str, voice: str | None = None) -> bytes:
    name = (voice or "").strip() or VOICES.default()
    gen = sherpa_onnx.GenerationConfig()
    gen.reference_audio = VOICES.reference(name)
    gen.reference_sample_rate = TTS.sample_rate
    gen.num_steps = NUM_STEPS
    with _generate_lock:
        audio = TTS.generate(text, gen)
    if len(audio.samples) == 0:
        raise RuntimeError("Pocket TTS produced no audio")
    return encode_wav(np.asarray(audio.samples, dtype=np.float32), audio.sample_rate)


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
