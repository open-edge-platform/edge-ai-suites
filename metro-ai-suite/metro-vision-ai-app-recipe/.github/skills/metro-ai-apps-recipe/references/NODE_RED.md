# Node-RED reference

- `./src/node-red:/data`, run as `user: root` (writes flows.json).
  Entrypoint chain: `/data/install_package.sh && /usr/src/node-red/entrypoint.sh`.
- `install_package.sh`:
  ```sh
  #!/bin/sh
  set -e
  cd /usr/src/node-red
  for pkg in node-red-dashboard node-red-contrib-aggregator; do
    [ -d node_modules/$pkg ] || npm install --no-audit --no-fund $pkg
  done
  ```
- config-node id must NOT equal its type. Use `broker1`, not `mqtt-broker`.
- `no_proxy=grafana,broker,node-red,nginx,localhost,127.0.0.1`.

## MQTT wildcard constraint

`+` matches ONE FULL level (`/`-delimited) — it cannot swallow characters
past `_`. Since DLSPS publishes to
`{{DETECTIONS_TOPIC_PREFIX}}_<N>/<pipeline>`, `<prefix>_+` is rejected
outright and `<prefix>_+/#` never matches. **Subscribe to `#` and filter
in the function node:**
```js
const m = (msg.topic || '').match(/^{{DETECTIONS_TOPIC_PREFIX}}_(\d+)/);
if (!m) return null;                        // drops own stats/alerts echoes
const sourceId = m[1];
```

## Flow shape (`count>N in Ts`)

Implemented as function node for portability.

1. Parse payload. **DLSPS 2026.1.0 nests detections at
   `msg.payload.metadata.gva_meta[]`**, not `.objects[]`. Probe:
   ```js
   const meta = msg.payload.metadata || {};
   const dets = meta.gva_meta || meta.objects || msg.payload.objects || [];
   ```
2. Filter by `label_id ∈ {{CLASS_FILTER_IDS}}` (or labelless — see
   `{{LABEL_RULE_NOTE}}`).
3. `sourceId = msg.topic.split('_')[1].split('/')[0]`.
4. Sliding window per source in `flow.context()`; drop entries older than T.
5. `windowMax = max(count over window)` per source.
6. `RULE_SCOPE=per-source`: alert if any `windowMax > N`.
   `RULE_SCOPE=aggregate`: alert if `sum(latest per source) > N`.
7. Emit alert on OFF→ON rise; increment `stats/alert_total`.

## Published topics (scalars where noted)

Grafana MQTT datasource plots scalars only — JSON here silently produces
empty time-series.

- `{{COUNT_TOPIC}}` — scalar total across sources
- `{{COUNT_TOPIC}}/<sourceId>` — scalar per source
- `{{ALERT_TOPIC}}` — JSON `{ts, sourceId?, count, rule}`
- `stats/alert_active` (0/1), `stats/alert_total` (monotonic)
