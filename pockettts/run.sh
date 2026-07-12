#!/usr/bin/with-contenv bashio
# Start the lightweight Pocket TTS server (sherpa-onnx / ONNX Runtime).
# It serves the web UI (ingress panel) and the HTTP API on port 8000.

export NUM_STEPS="$(bashio::config 'num_steps')"
export NUM_THREADS="$(bashio::config 'num_threads')"
export DATA_DIR="/data"
export PORT="8000"

if bashio::config.has_value 'voice'; then
  export VOICE_WAV="$(bashio::config 'voice')"
fi

bashio::log.info "Starting Pocket TTS (sherpa-onnx, num_steps=${NUM_STEPS})..."
bashio::log.info "First launch downloads the ONNX model, which can take a few minutes."

exec /opt/venv/bin/python /server.py
