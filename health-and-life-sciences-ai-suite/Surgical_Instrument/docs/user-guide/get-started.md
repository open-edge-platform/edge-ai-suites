# Get Started - Surgical Instrument

This is a deployment guide for the three-service Docker stack:
- `surgical-backend` (Flask 3 + Ultralytics + OpenVINO bootstrap)
- `surgical-pipeline` (GStreamer + DL Streamer runtime)
- `surgical-ui` (nginx + React SPA)

The UI is **health-gated on the backend**:
the browser tab will not answer until `surgical-backend` reports `/api/readiness → ready`.
On the first boot this time window is 20–35 minutes while YOLO11n trains on CVC-ColonDB on
the Intel® Arc™ iGPU. Subsequent boots take seconds because the trained IR is cached in
`./models/`.

---

## 1. Host prerequisites

| Requirement                                                                  | Notes                                                                 |
|------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| Linux with Docker Engine ≥ 24 and `docker compose` v2                        | Rootless Docker works if `/dev/dri` is accessible.                    |
| Intel Arc iGPU (Meteor Lake / Lunar Lake / Arrow Lake) or discrete Arc GPU   | Container inherits the host driver via `/dev/dri` passthrough.        |
| Host groups `render` and `video` exist                                       | The Makefile auto-detects the GIDs.                                   |
| ≈ 15 GB free disk                                                            | 6 GB image, 2 GB dataset + cache, remainder for training checkpoints. |

Verify iGPU visibility on the host before starting:

```bash
ls -l /dev/dri/renderD*
getent group render
getent group video
```



## 2. One-time: drop the CVC-ColonDB dataset

The bootstrap requires the dataset to start training.
Since the dataset is not redistributed with the app, you must download it directly from the
CVC lab (research use only).

1. Visit **https://pages.cvc.uab.es/CVC-Colon/index.php/databases/** and download the
   CVC-ColonDB archive after accepting the terms.
   Citation: *Bernal, Sánchez, Vilariño (2012) Pattern Recognition 45(9), 3166–3182*.
2. Place the archive or extracted folder in: ``Surgical_Instrument/datasets/CVC-ColonDB/raw/``.
   If you download `.rar`, extract it locally first, if it is `.zip`, `.tar`, `.tar.gz`, or
   `.tgz`, you do not need to extract it.

The bootstrap will now auto-detect images + masks on the first launch, convert binary
masks to YOLO bounding-box labels, split 70/15/15, and write `data.yaml`.

If you already have a trained IR, you can seed it into `models/` and skip the training
entirely:

```bash
make assets   # copies best.xml + best.bin from poc/st2_app if present
```

The presence of both `models/yolo11n_polyp/best_openvino_model/best.xml` **and**
`models/yolo11n_polyp/.trained_ok` short-circuits the bootstrap to `ready` in seconds.



## 3. Bring the stack up

First, discover the camera serial and the P-core set for your CPU:

```bash
make list-cameras   # prints Basler serial(s) -> SOURCE_ARG
make show-cores     # prints the P-core set    -> PIPELINE_GST_CORES
```

`make up` supports two image sources, controlled by the `REGISTRY` flag.

### 3a. Pull from registry (default)

`REGISTRY=true` (the default) pulls the prebuilt images at `TAG` (default `latest`) and
starts them with `RENDER_GID` / `VIDEO_GID` auto-detected from the host — no local build
needed.

```bash
# Live Basler camera (P-core pinned, free-running sink).
make up SOURCE_KIND=basler SOURCE_ARG=<SERIAL_NUMBER> \
        PIPELINE_GST_CORES=<P_CORES> PIPELINE_SINK_SYNC=false

# Default file source
make up
```

### 3b. Build from source

`REGISTRY=false` builds every image locally from its Dockerfile (backend = torch+xpu wheels +
OpenVINO + Ultralytics, UI = Vite build → nginx, pipeline = DL Streamer + gencamsrc).

```bash
# Live Basler camera, built from source
make up SOURCE_KIND=basler SOURCE_ARG=<SERIAL_NUMBER> \
        PIPELINE_GST_CORES=<P_CORES> PIPELINE_SINK_SYNC=false REGISTRY=false

# Default file source, built from source
make up REGISTRY=false
```

The `surgical-ui` service declares `depends_on: surgical-backend: condition: service_healthy`,
so it will not start listening on `:8080` until the backend passes its `/api/readiness`
HEALTHCHECK. The backend healthcheck uses a **45-minute `start_period`** to absorb first-boot
training.

### Follow first-boot progress

```bash
make logs
```

Expect to see the FSM walk through:

```
[boot] state=initializing
[boot] state=checking_cache
[boot] state=downloading_dataset      (skipped if raw/ already populated)
[boot] state=preparing_dataset
[boot] state=downloading_weights      (~5 MB yolo11n.pt)
[boot] state=training                 (~15-25 min, ~50 epochs)
[boot] state=exporting                (Ultralytics → OpenVINO IR)
[boot] state=ready
[server] READY
```

### Open the UI

Once the backend is healthy the UI starts and answers on `http://localhost:8080`
(override with `make up UI_HOST_PORT=9090`). `make up` and `make run` also print the LAN URL
(e.g. `http://10.223.23.206:8080`) so you can open it from another machine in the same network.

Use the left **Config** accordion to pick source (`file` or `basler`), source argument,
and device, then click **Start** to kick off inference.
The right-side KPI blocks begin populating within ~1 second.

See more info on [the UI](./index.md#user-interface).


## 4. Stop / clean up

If you want to stop or restart the app, you have the following options:

```bash
make down                 # stop + remove containers, keep volumes + IR
```

```bash
make clean                # also drop the surgical-cache named volume + built images
```

The trained IR model under `./models/` is a bind-mount and survives `make clean`.
Delete it manually to force a full re-train on next boot:

```bash
rm -rf models/yolo11n_polyp
```




## Common overrides

| Variable                   | Default | Meaning                                                       |
|----------------------------|---------|---------------------------------------------------------------|
| `UI_HOST_PORT`             | `8080`  | Only host-published port.                                     |
| `DETECTION_DEVICE`         | `xpu`   | Set to `cpu` on a host without an Arc iGPU.                   |
| `RENDER_GID` / `VIDEO_GID` | auto    | Override if the host has non-standard render/video group IDs. |

Example: run the whole stack CPU-only on port 9000:

```bash
make up UI_HOST_PORT=9000 DETECTION_DEVICE=cpu
```

