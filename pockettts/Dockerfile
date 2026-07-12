ARG BUILD_FROM
FROM $BUILD_FROM

ARG BUILD_VERSION
ARG BUILD_ARCH

LABEL \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="addon" \
  io.hass.arch="${BUILD_ARCH}"

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

# Lean runtime: sherpa-onnx (bundles ONNX Runtime) + numpy. No PyTorch.
RUN \
  apt-get update \
  && apt-get install -y --no-install-recommends \
       python3 \
       python3-venv \
       libgomp1 \
       ca-certificates \
  && python3 -m venv /opt/venv \
  && /opt/venv/bin/pip install --upgrade pip \
  && /opt/venv/bin/pip install sherpa-onnx numpy \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* /root/.cache /tmp/*

COPY server.py /server.py
COPY run.sh /run.sh

RUN chmod +x /run.sh

CMD ["/run.sh"]
