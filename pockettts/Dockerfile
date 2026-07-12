ARG BUILD_FROM
FROM $BUILD_FROM

ARG BUILD_VERSION
ARG BUILD_ARCH

LABEL \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="addon" \
  io.hass.arch="${BUILD_ARCH}"

ENV HF_HOME=/data/hf \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

# Full-precision (FP32) runtime: CPU-only PyTorch + the official pocket-tts.
RUN \
  apt-get update \
  && apt-get install -y --no-install-recommends \
       python3 \
       python3-venv \
       libgomp1 \
       ca-certificates \
  && python3 -m venv /opt/venv \
  && /opt/venv/bin/pip install --upgrade pip \
  && /opt/venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch \
  && /opt/venv/bin/pip install pocket-tts \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* /root/.cache /tmp/*

COPY server.py /server.py
COPY run.sh /run.sh

RUN chmod +x /run.sh

CMD ["/run.sh"]
