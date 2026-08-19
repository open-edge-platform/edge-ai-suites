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

Set the `mqtt in` node's **`datatype: "auto"`** (not `json`): the same
node also receives the scalar `stats/*` echoes, and a `json` datatype
throws a parse error on those plain numbers and drops the flow. `auto`
delivers a Buffer/string that the function coerces (step 0 below).

## Flow shape (`count>N in Ts`)

Implemented as function node for portability.

0. **Coerce the payload first.** The `mqtt in` node uses `datatype: "auto"`
   (required — see the wildcard note above), which delivers the detection
   payload as a **Buffer or string**, NOT a parsed object. Without this
   step `msg.payload.metadata` is `undefined` and every count is 0:
   ```js
   let p = msg.payload;
   if (Buffer.isBuffer(p)) p = p.toString();
   if (typeof p === 'string') { try { p = JSON.parse(p); } catch (e) { return null; } }
   ```
1. Parse payload. **DLSPS 2026.1.0 nests detections at
   `p.metadata.gva_meta[]`**, not `.objects[]`. Probe:
   ```js
   const meta = p.metadata || {};
   const dets = meta.gva_meta || meta.objects || p.objects || [];
   ```
2. **Per-detection, the class lives at `det.tensor[0].label_id` /
   `det.tensor[0].label`** — NOT `det.label_id` or `det.detection.label_id`
   (those are always `undefined`, so filtering silently drops everything).
   Filter by `tensor[0].label_id ∈ {{CLASS_FILTER_IDS}}` OR
   `tensor[0].label === '{{OBJECT}}'` (labelless — see `{{LABEL_RULE_NOTE}}`):
   ```js
   const t = (det.tensor && det.tensor[0]) || {};
   if (t.label === '{{OBJECT}}' || {{CLASS_FILTER_IDS}}.indexOf(t.label_id) !== -1) count++;
   ```
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
