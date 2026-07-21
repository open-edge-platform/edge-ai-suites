# Dockerfile – metrics-collector for the Smart Kiosk Assistant.
#
# Uses intel/retail-benchmark as the base image, which ships:
#   supervisord      – process manager that starts all collectors
#   qmassa           – Intel GPU utilization (writes qmassa1-*-tool-generated.json)
#   Intel NPU tool   – NPU utilization (writes npu_usage.csv)
#   Intel PCM        – CPU package power (writes pcm.csv)
#   sar / free       – CPU and memory (managed by supervisord.conf)
#
# pciutils is added for lspci (used by /platform-info to detect iGPU/NPU names).

FROM intel/retail-benchmark:3.3.2

ARG HTTP_PROXY

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        pciutils \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir fastapi uvicorn

# Override supervisord.conf to add stdout_logfile_maxbytes=0 on every program,
# which disables log rotation for non-seekable streams (Docker stdout/stderr pipes)
# and eliminates the harmless but noisy "OSError: [Errno 29] Illegal seek" errors.
RUN sed -i '/^stdout_logfile=\/dev\/stdout/a stdout_logfile_maxbytes=0' /supervisord.conf

WORKDIR /app

COPY app.py      ./app.py
COPY metrics.py  ./metrics.py
COPY api/        ./api/
COPY start.sh    /start.sh

RUN chmod +x /start.sh

EXPOSE 9000

# start.sh starts supervisord (base-image collectors) then runs app.py.
CMD ["/start.sh"]
