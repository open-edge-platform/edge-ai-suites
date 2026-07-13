# Run In Docker

Use this path to run the service in an Intel OpenVINO runtime container
using the prebuilt image published on Docker Hub. The API is exposed on
port `8020`.

To rebuild the image from source instead of pulling, see the build flow
at the bottom of this page.

## Pull And Start

From the `rag-service/` directory:

```bash
docker compose pull
docker compose up -d
```

`docker compose pull` fetches `intel/rag-service:${RELEASE_TAG}` from
Docker Hub. `RELEASE_TAG` and `REGISTRY` are read from `.env`
(defaults: `REGISTRY=intel`, `RELEASE_TAG=latest`); the committed
`.env` pins the current release tag.

This publishes:

- API: `http://127.0.0.1:8020`

## Verify

```bash
curl --noproxy '*' http://127.0.0.1:8020/health
```

## Build From Source (Alternate Flow)

If you need a code change, rebuild the image instead of pulling:

```bash
docker compose build
docker compose up -d
```

The locally built image is tagged with the same
`${REGISTRY}/rag-service:${RELEASE_TAG}` reference, so subsequent
`docker compose up` calls reuse the local build until you `docker
compose pull` again.

## Notes

- The compose file passes `/dev/dri` and adds the `video` and `${RENDER_GID:-992}` groups so OpenVINO GPU can be used from the container.
- [config.yaml](../config.yaml) is the single source of truth; the same file drives standalone and container runs.
- Model cache and vector storage are persisted through bind mounts in `models/`, `storage/`, and `.cache/huggingface/`.
