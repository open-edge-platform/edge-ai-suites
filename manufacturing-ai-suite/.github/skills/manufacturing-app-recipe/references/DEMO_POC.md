# Demo/PoC mode (`vision` mode, and `ts` mode's demo sub-path)

Two unrelated lightweight paths share this file — each produces one
single-component app proving a model/UDF runs on Intel hardware, with **no**
full Compose topology (no Telegraf/InfluxDB/Fusion Analytics/Grafana/Nginx/
SeaweedFS/MediaMTX/Coturn). `multimodal`/`vllm`/`agentic` modes never use this
file — they are production-only.

## `vision` mode

Ask which sub-path (no default — the two paths produce unrelated artifacts):

- **DL Streamer pipeline** — delegate to `dlstreamer-coding-agent` for a
  from-scratch GStreamer/DL Streamer pipeline.
- **REST-driven DLSPS instance** — delegate to `dlsps-user` (`docker compose
  up` the DLSPS image alone + one `POST /pipelines/{name}/{version}` call).

Model: reuse `{{DEFAULT_MODEL}}` if the invoking prompt named one, or any
other concrete, resolvable source (an existing local path, or an OMZ/Hugging
Face/explicit URL fetchable via `model-download-user`). **Never pick an
arbitrary classifier on the agent's own judgment** — this demo/PoC path is
still bound by SKILL.md's *Model availability — ask, don't fabricate* rule;
if no model is named and no resolvable source exists, stop and ask the user
instead of guessing one. Output: annotated
RTSP or a JSON-lines metadata file — no WebRTC/S3/MQTT stack required.

### `vision` mode — lightweight completion criteria

1. The chosen delegate skill's own container(s) start successfully.
2. One inference call round-trips end-to-end (a detection/classification
   result) with evidence quoted verbatim (log line or REST response body)
   in the final summary.
3. No literal `{{...}}` template variables remain in any generated file.
4. The final summary states plainly that this was a `vision`-mode demo/PoC
   app, not a full stack, and names the one command to bring it down.

## `ts` mode — demo sub-path

When Question 0b selects `demo`, **do not create an `apps/<name>/` folder,
do not touch the Makefile, and do not stand up the simulator/Grafana/Nginx
stack at all**. This path exists purely to prove a UDF/TICKscript pattern
works against an already-deployed (or freshly `docker compose up`'d) Time
Series Analytics Microservice — hand the entire task to
`time-series-analytics-user` and follow its procedure end-to-end:

1. Bring up the bare microservice (`time-series-analytics-user`'s own step 1
   — REPO or STANDALONE path, whichever applies).
2. Pick a pattern from its `references/patterns.md`.
3. Author the UDF + TICKscript from its templates.
4. Package and deploy via its `scripts/package_udf.sh` + REST calls.
5. Feed test points via `POST /input` and verify via container logs / MQTT
   capture, per that skill's own evidence bar.

### `ts` mode — demo sub-path completion criteria

1. The microservice container is running and reachable.
2. The UDF is deployed (`POST /udfs/package` + `POST /config` both return
   200 — quote the bodies).
3. One flagged point and one non-flagged point are demonstrated with quoted
   log/MQTT evidence, exactly as `time-series-analytics-user` requires.
4. No literal `{{...}}` template variables remain in any generated file.
5. The final summary states plainly that this was a `ts`-mode demo/PoC bare-UDF
   deployment, not a registered `apps/<name>/` sample app, and names the one
   command to bring the microservice down.
