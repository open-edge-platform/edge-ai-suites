# System Requirements


| Requirement                                                                  | Notes                                                                 |
|------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| Linux with Docker Engine ≥ 24 and `docker compose` v2                        | Rootless Docker works if `/dev/dri` is accessible.                    |
| Intel Arc iGPU (Meteor Lake / Lunar Lake / Arrow Lake) or discrete Arc GPU   | Container inherits the host driver via `/dev/dri` passthrough.        |
| Host groups `render` and `video` exist                                       | The Makefile auto-detects the GIDs.                                   |
| ≈ 15 GB free disk space                                                      | 6 GB image, 2 GB dataset + cache, remainder for training checkpoints. |

Verify iGPU visibility on the host before starting:

```bash
ls -l /dev/dri/renderD*
getent group render
getent group video
```


## Corporate proxy setup

If you are behind a corporate proxy, configure it before running `make up`.
Both image build and runtime model-weight downloads require proxy access.

Two equivalent approaches are supported.

1. Option A (recommended, persistent): configure `.env`

   ```bash
   cp .env.example .env
   # then edit .env and set HTTP_PROXY, HTTPS_PROXY, NO_PROXY
   ```

2. Option B: export in shell

   ```bash
   export HTTP_PROXY=http://proxy.your-corp.com:912
   export HTTPS_PROXY=http://proxy.your-corp.com:912
   export NO_PROXY=localhost,127.0.0.1,.your-corp.com,surgical-pipeline,surgical-backend,surgical-ui
   ```

    `docker-compose.yaml` forwards these values to `docker build` (as build args) and to
    the running containers (as environment variables), so `apt`, `pip`, `wget`, `curl`, and
    Ultralytics all honour them. `make up` also runs a preflight check and warns if you
    appear to be on an Intel corporate network but neither `.env` nor exported variables
    provide a proxy.

   Notes:
   - Include internal service names in `NO_PROXY` so container-to-container traffic
     (backend → pipeline) is not routed through the proxy.
   - Docker daemon also needs a proxy configuration to pull the base image.
     If `docker pull ubuntu:24.04` works, you are fine. Otherwise configure
     `~/.docker/config.json` or `/etc/systemd/system/docker.service.d/http-proxy.conf`
     per your IT policy.
   - Quick connectivity check before building:

     ```bash
     curl -sS -o /dev/null -w "%{http_code}\n" https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt
     # expect: 200 or 302
     ```

