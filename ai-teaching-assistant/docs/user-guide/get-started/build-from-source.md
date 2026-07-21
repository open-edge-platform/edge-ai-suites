# Build From Source

Build Smart Kiosk Assistant from source. Use this path when you need a
code change in any of the kiosk services. To run the prebuilt images
from Docker Hub without rebuilding, see
[Run With Docker Compose](./run-container.md).

## Prerequisites

Verify the [System Requirements](./system-requirements.md).

## Clone and Prepare

The kiosk compose builds `audio-analyzer` and `text-to-speech` from the
upstream [edge-ai-libraries](https://github.com/open-edge-platform/edge-ai-libraries)
monorepo. The compose file references those sources at
`../edge-ai-libraries/microservices/{audio-analyzer,text-to-speech}`,
so the two repositories must sit side by side:

```text
<parent>/
├── voice-enabled-interactions/
│   └── smart-kiosk-assistant/   # run docker compose from here
└── edge-ai-libraries/
    └── microservices/
        ├── audio-analyzer/
        └── text-to-speech/
```

From whatever parent directory you keep source in:

```bash
git clone https://github.com/intel-retail/voice-enabled-interactions.git
cd voice-enabled-interactions/
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/open-edge-platform/edge-ai-libraries.git
git -C edge-ai-libraries sparse-checkout set \
  microservices/audio-analyzer microservices/text-to-speech

cd smart-kiosk-assistant/
```

The sparse checkout pulls only the two microservices the kiosk build
needs; everything else in `edge-ai-libraries` stays unchecked out. A
plain `git clone` of `edge-ai-libraries` also works if you do not mind
the extra files. Only the build flow needs `edge-ai-libraries` on disk
— the pull flow (see [Run With Docker Compose](./run-container.md)) does not.

## Build All Images With Compose

The top-level [docker-compose.yml](https://github.com/intel-retail/voice-enabled-interactions/blob/main/smart-kiosk-assistant/docker-compose.yml)
declares both `image:` and `build:` for each of the five services: `audio-analyzer`,
`text-to-speech`, `rag-service`, `kiosk-core`, and `kiosk-ui`. Both
`REGISTRY` and `RELEASE_TAG` are read from [.env](https://github.com/intel-retail/voice-enabled-interactions/blob/main/smart-kiosk-assistant/.env)
(defaults: `REGISTRY=intel`, committed `RELEASE_TAG` pins the current release).

`docker compose build` rebuilds each service from source and tags the
result as the same `${REGISTRY}/<svc>:${RELEASE_TAG}` reference used by
the pull flow, so subsequent `docker compose up` calls reuse the local
build until you `docker compose pull` again.

```bash
docker compose build
docker compose up -d
```

All five services run as UID/GID `1000:1000` (baked into each image),
and runtime data lives in named Docker volumes initialized with that
ownership, so no host UID/GID configuration is needed.

## Rebuild A Single Service

Rebuild only the service whose source you changed:

```bash
docker compose build audio-analyzer
docker compose up -d audio-analyzer
```

## Build A Single Service Image Directly

Each service can be built directly with `docker build`. From the
repository root:

```bash
# audio-analyzer
docker build -t intel/audio-analyzer:local \
  ../edge-ai-libraries/microservices/audio-analyzer

# text-to-speech
docker build -t intel/text-to-speech:local \
  ../edge-ai-libraries/microservices/text-to-speech

# rag-service
docker build -t intel/rag-service:local ./rag-service

# kiosk-core / kiosk-ui (same Dockerfile, different entrypoints)
docker build -t intel/kiosk-core:local .
docker build -t intel/kiosk-ui:local   .
```

The `kiosk-ui` container reuses the `kiosk-core` image and runs
`python3 gradio_app.py` as its command.

## Build a Python Environment (Standalone kiosk-core + UI)

`kiosk-core` and `kiosk-ui` can run directly on the host while the three
model-hosting services run in containers. Install host packages, then
create a virtual environment and install dependencies:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg alsa-utils libsndfile1

python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

See [Run On the Host](./run-standalone.md) for the launch commands.

## Verifying the Build

Once the stack is started, confirm every service is healthy:

```bash
curl --noproxy '*' http://127.0.0.1:8010/health   # audio-analyzer
curl --noproxy '*' http://127.0.0.1:8011/health   # text-to-speech
curl --noproxy '*' http://127.0.0.1:8020/health   # rag-service
curl --noproxy '*' http://127.0.0.1:8012/health   # kiosk-core
```

A `{"status": "ok"}` response from each endpoint confirms the build is
functional. Open `http://127.0.0.1:7860` to use the browser UI.
