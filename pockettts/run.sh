#!/usr/bin/with-contenv bashio
# Start the Pocket TTS server (official FP32 pocket-tts library).
# It serves the web UI (ingress panel) and the HTTP API on port 8000.

export LANGUAGE="$(bashio::config 'language')"
export TEMPERATURE="$(bashio::config 'temperature')"
export EOS_THRESHOLD="$(bashio::config 'eos_threshold')"
export NUM_THREADS="$(bashio::config 'num_threads')"
export PORT="8000"

# Persist the downloaded model between restarts (the add-on /data volume).
export HF_HOME="/data/hf"
mkdir -p "${HF_HOME}"

# Hugging Face token (needed to download the gated voice-cloning weights used
# for custom voices / .safetensors profiles).
if bashio::config.has_value 'hf_token'; then
  export HF_TOKEN="$(bashio::config 'hf_token')"
  export HUGGING_FACE_HUB_TOKEN="${HF_TOKEN}"
fi

if bashio::config.has_value 'voice'; then
  export VOICE="$(bashio::config 'voice')"
fi

bashio::log.info "Starting Pocket TTS (FP32, language=${LANGUAGE})..."
bashio::log.info "First launch downloads the model, which can take a few minutes."

exec /opt/venv/bin/python /server.py
