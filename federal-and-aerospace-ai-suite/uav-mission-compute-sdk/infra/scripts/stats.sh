#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# On-demand resource snapshot: per-container CPU/memory (docker stats, always
# works) plus host GPU/NPU/power (from InfluxDB, when the observability
# profile is up — it is by default via `make up-sim-camera`/`up-usb-camera`).
# Terminal-first alternative to opening Grafana; Grafana remains available
# separately for history/trends.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1

PROJECT="uav-mission-compute-sdk"

echo "── Container CPU / Memory ──────────────────────────────────────────────"
mapfile -t CIDS < <(docker ps --filter "label=com.docker.compose.project=${PROJECT}" -q)
if [ ${#CIDS[@]} -eq 0 ]; then
    echo "  No stack containers running. Start with 'make up-sim-camera' or 'make up-usb-camera'."
else
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" "${CIDS[@]}"
fi

echo
echo "── Host GPU / NPU / Power (not per-container — shared accelerators) ───"
# shellcheck disable=SC1091  # .env is a runtime-generated file, not a static input
[ -f .env ] && { set -a; source .env; set +a; }

if ! docker ps --format '{{.Names}}' | grep -qx influxdb; then
    echo "  Not available (observability profile isn't running)."
    echo "  Start it with: make up-sim-camera   (runs by default)"
elif [ -z "${INFLUXDB_TOKEN:-}" ] || [ -z "${INFLUXDB_ORG:-}" ]; then
    echo "  Not available (INFLUXDB_TOKEN/INFLUXDB_ORG missing from .env)."
else
    # Query InfluxDB's HTTP API directly (no extra deps) — annotations
    # suppressed so the CSV is just a header row + one data row.
    _flux_last() {
        local measurement="$1" field="$2" extra_filter="${3:-}"
        local flux="from(bucket:\"telemetry\") |> range(start:-30s) |> filter(fn:(r)=>r._measurement==\"${measurement}\" and r._field==\"${field}\" ${extra_filter}) |> last()"
        # JSON-escape backslashes/quotes — extra_filter carries raw Flux
        # string literals (e.g. r["engine"]=="rcs") that must not break the
        # JSON request body.
        local flux_json=${flux//\\/\\\\}
        flux_json=${flux_json//\"/\\\"}
        curl -s "http://127.0.0.1:8086/api/v2/query?org=${INFLUXDB_ORG}" \
            -H "Authorization: Token ${INFLUXDB_TOKEN}" \
            -H "Content-Type: application/json" \
            -H "Accept: application/csv" \
            -d "{\"query\":\"${flux_json}\",\"dialect\":{\"annotations\":[],\"header\":true}}" \
        | awk -F',' 'NR==1{for(i=1;i<=NF;i++) if($i=="_value") c=i} NR==2 && c{printf "%s", $c}'
    }
    gpu=$(_flux_last gpu_engine_usage usage 'and r["engine"]=="rcs"')
    npu=$(_flux_last npu utilization)
    pwr=$(_flux_last rapl_power power_w)
    printf "  iGPU Render : %s%%\n" "${gpu:-n/a}"
    printf "  NPU Util    : %s%%\n" "${npu:-n/a}"
    printf "  Package Pwr : %sW\n"  "${pwr:-n/a}"
fi

echo
echo "Tip: run 'watch -n 2 infra/scripts/stats.sh' for a live-refreshing view."
echo "Grafana (optional, history/trends): http://localhost:3000"
