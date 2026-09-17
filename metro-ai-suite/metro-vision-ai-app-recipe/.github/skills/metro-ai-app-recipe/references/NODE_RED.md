# Node-RED reference

- `./src/node-red:/data`, run as `user: root` (writes flows.json). Entrypoint chain: `/data/install_package.sh && /usr/src/node-red/entrypoint.sh`.
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

`+` matches ONE FULL `/`-delimited level; it cannot swallow past `_`. DLSPS publishes `{{DETECTIONS_TOPIC_PREFIX}}_<N>/<pipeline>`; `<prefix>_+` is rejected and `<prefix>_+/#` never matches. **Subscribe to `#` and filter in the function node:**
```js
const m = (msg.topic || '').match(/^{{DETECTIONS_TOPIC_PREFIX}}_(\d+)/);
if (!m) return null;                        // drops own stats/alerts echoes
const sourceId = m[1];
```

Set `mqtt in` **`datatype: "auto"`** (not `json`): it also receives scalar `stats/*`; `json` parse-errors on numbers and drops flow. `auto` yields Buffer/string.

## Flow shape (`count <op> N in Ts`, `<op>` ∈ `>`,`>=`,`<`,`<=`)

Portable function node. **`DEFAULT_RULE` parses to an operator + threshold** (`^count([<>]=?)(\d+)\s+in\s+(\d+)s$`) — the flow MUST honour the parsed operator, not assume `>`. Substitute concrete `{{RULE_OP}}`, `{{RULE_N}}`, `{{RULE_WINDOW_S}}` when writing `flows.json`.

0. **Coerce payload first.** `datatype: "auto"` means detection payload is **Buffer or string**, NOT parsed; otherwise `msg.payload.metadata` is `undefined` and counts stay 0:
   ```js
   let p = msg.payload;
   if (Buffer.isBuffer(p)) p = p.toString();
   if (typeof p === 'string') { try { p = JSON.parse(p); } catch (e) { return null; } }
   ```
1. Parse payload. **DLSPS 2026.1.0 nests detections at `p.metadata.gva_meta[]`**, not `.objects[]`. Probe:
   ```js
   const meta = p.metadata || {};
   const dets = meta.gva_meta || meta.objects || p.objects || [];
   ```
2. **Per-detection class is `det.tensor[0].label_id` / `det.tensor[0].label`** — NOT `det.label_id` or `det.detection.label_id` (always `undefined`, dropping filters). Filter by `tensor[0].label_id ∈ {{CLASS_FILTER_IDS}}` OR `tensor[0].label === '{{OBJECT}}'` (labelless — see `{{LABEL_RULE_NOTE}}`):
   ```js
   const t = (det.tensor && det.tensor[0]) || {};
   if (t.label === '{{OBJECT}}' || {{CLASS_FILTER_IDS}}.indexOf(t.label_id) !== -1) count++;
   ```
3. `sourceId = msg.topic.split('_')[1].split('/')[0]`.
4. Sliding window per source in `flow.context()`; drop entries older than T.
5. `windowMax = max(count over window)` per source.
6. Evaluate the parsed operator `{{RULE_OP}}` against threshold `{{RULE_N}}`.
   Define a comparator once:
   ```js
   function cmp(v, n, op) {
     switch (op) { case '>': return v > n; case '>=': return v >= n;
                   case '<': return v < n; case '<=': return v <= n; }
     return false;
   }
   ```
   - `RULE_SCOPE=per-source`: for `>`/`>=` alert if **any** source `cmp(windowMax, N)`;
     for `<`/`<=` alert if **any** source `cmp(windowMin, N)` (use per-source
     `windowMin = min(count over window)` so a single starved source trips it).
   - `RULE_SCOPE=aggregate`: let `agg = sum(latest count per source)`; alert if
     `cmp(agg, N)`. Example — `count<1 in 15s aggregate` (PPE: no PPE seen across
     all cameras) → `agg = Σ latest per source`, fire when `agg < 1` (i.e. `=== 0`).
   > For `<`/`<=` rules, initialise counts so an empty/never-seen window counts as
   > its true value (0), otherwise a low-count alert never arms.
7. Emit alert on OFF→ON rise; increment `stats/alert_total`.

## Published topics (scalars where noted)

Grafana MQTT plots only scalars — JSON yields empty time-series.

- `{{COUNT_TOPIC}}` — scalar total across sources
- `{{COUNT_TOPIC}}/<sourceId>` — scalar per source
- `{{ALERT_TOPIC}}` — JSON `{ts, sourceId?, count, rule}`
- `stats/alert_active` (0/1), `stats/alert_total` (monotonic)
