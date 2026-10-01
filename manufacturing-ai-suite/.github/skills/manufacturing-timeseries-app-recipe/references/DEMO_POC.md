# Demo/PoC mode

When Question 0 selects `demo`, **do not create an `apps/<name>/` folder,
do not touch the Makefile, and do not stand up the simulator/Grafana/Nginx
stack at all**. This mode exists purely to prove a UDF/TICKscript pattern
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

## Completion criteria (demo mode only — production criteria 1–10 do NOT apply)

1. The microservice container is running and reachable.
2. The UDF is deployed (`POST /udfs/package` + `POST /config` both return
   200 — quote the bodies).
3. One flagged point and one non-flagged point are demonstrated with quoted
   log/MQTT evidence, exactly as `time-series-analytics-user` requires.
4. No literal `{{...}}` template variables remain in any generated file.
5. The final summary states plainly that this was a demo/PoC bare-UDF
   deployment, not a registered `apps/<name>/` sample app, and names the one
   command to bring the microservice down.
