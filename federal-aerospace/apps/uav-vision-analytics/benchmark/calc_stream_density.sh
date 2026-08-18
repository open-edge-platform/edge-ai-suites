#!/bin/bash
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# Ensure ~/.local/bin (jq wrapper) is in PATH
export PATH="$HOME/.local/bin:$PATH"
# calc_stream_density.sh — UAV Vision Analytics Pipeline Benchmark
#
# Modes:
#   stream-density : Exponential + bisect search to find max streams sustaining
#                    target FPS.
#   nstreams       : Run fixed stream counts per pipeline; measure throughput.
#   --all-devices  : Run density search sequentially for all specified pipelines
#                    (CPU + GPU + NPU) and print a unified claim-statement table.
#
# HW Metrics Integration (metrics-manager):
#   Polls intel/metrics-manager at METRICS_URL (default: http://localhost:9090).
#   Tries SSE endpoint (/metrics/stream) FIRST, falls back to REST
#   (/api/v1/metrics/latest). Metrics are collected only while are in RUNNING
#   state (not during GPU warmup / pipeline init).
#   Results are appended to kpi.txt as hw_<metric> avg/min/max lines.

# ═══════════════════════════════════════════════════════════════════════════════
#  Statistical utility functions (AWK)
# ═══════════════════════════════════════════════════════════════════════════════
awk_utils='
  function calc_median(values ,n,v_sorted) {
    if (length(values)==0) return 0
    n=asort(values,v_sorted,"@val_num_asc")
    return v_sorted[(n%2 == 0)?n/2:(n+1)/2]
  }
  function calc_percentile(values,p, v_sorted,i,ii) {
    if (length(values)==0) return 0
    i=asort(values,v_sorted,"@val_num_asc")*p
    ii=int(i)
    return v_sorted[i>ii?ii+1:(ii==0?1:ii)]
  }
  function calc_median_if_matched(vt,m,vl ,i,tmp,ct) {
    ct=0
    split("",tmp)
    for (i in vt) if (vt[i]==m) tmp[++ct]=vl[i]
    return calc_median(tmp)
  }
  function calc_max_if_matched(vt,m,vl ,i,tmp,ct) {
    max=0
    for (i in vt) if (vt[i]==m && vl[i]>max) max=vl[i]
    return max
  }
  function calc_sum(values, m,i,nv) {
    m=0
    for (i in values)
      m=m+values[i]
    return m
  }
  function calc_avg(values, m,i,nv) {
    nv=length(values)
    return (nv>0?calc_sum(values)/nv:0)
  }
  function calc_min(values, m,i) {
    m=length(values)>0?values[1]:0
    for (i in values)
      if (values[i]<m) m=values[i]
    return m
  }
  function calc_max(values, m,i) {
    m=0
    for (i in values)
      if (values[i]>m) m=values[i]
    return m
  }
  function calc_stdev(values, nv,i,mean,sum_sq_diff,variance) {
    nv=length(values)
    if (nv<=1) return 0
    mean = calc_avg(values)
    sum_sq_diff = 0
    for (i=1;i<=nv;i++)
      sum_sq_diff+=(values[i]-mean)^2
    return sqrt(sum_sq_diff/(nv-1))
  }
'

# ═══════════════════════════════════════════════════════════════════════════════
#  HW Metrics Configuration
#  Override via environment variables or the -m / -M CLI flags.
# ═══════════════════════════════════════════════════════════════════════════════
METRICS_URL="${METRICS_URL:-http://localhost:9090}"
METRICS_INTERVAL="${METRICS_INTERVAL:-2}"   # seconds between polls
HW_MONITOR_ENABLED=true                     # set false to skip entirely
HW_POLL_PID=""                              # PID of background poller subshell
HW_SAMPLE_FILE=""                           # path to current hw_samples.log
_HW_STREAM_PY="/tmp/hw_stream_$$.py"       # temp Python3 SSE streamer script

# Ensure the background poller is killed if the script exits for any reason
function _cleanup_hw_monitor() {
  if [ -n "$HW_POLL_PID" ] && kill -0 "$HW_POLL_PID" 2>/dev/null; then
    kill "$HW_POLL_PID" 2>/dev/null
    wait "$HW_POLL_PID" 2>/dev/null
  fi
  HW_POLL_PID=""
  rm -f "$_HW_STREAM_PY"
}
trap _cleanup_hw_monitor EXIT INT TERM

# ───────────────────────────────────────────────────────────────────────────────
#  _check_metrics_manager
#  Tries SSE first (primary), REST second (fallback).
# ───────────────────────────────────────────────────────────────────────────────
function _check_metrics_manager() {
  local resp

  # SSE primary check — any response from the event-stream means it's up
  resp=$(curl -s --connect-timeout 3 --max-time 4 -N \
    "${METRICS_URL}/metrics/stream" 2>/dev/null | head -1)
  [ -n "$resp" ] && return 0

  # REST fallback check
  resp=$(curl -s --connect-timeout 3 --max-time 5 \
    "${METRICS_URL}/api/v1/metrics/latest" 2>/dev/null)
  echo "$resp" | grep -q '"metrics"' && return 0

  return 1
}

# ───────────────────────────────────────────────────────────────────────────────
#  start_hw_monitor <outdir>
#
#  Starts a Python3 SSE streamer that writes snapshots continuously to
#  <outdir>/hw_samples.log.
# ───────────────────────────────────────────────────────────────────────────────
function start_hw_monitor() {
  local outdir=$1
  HW_SAMPLE_FILE="${outdir}/hw_samples.log"
  rm -f "$HW_SAMPLE_FILE"
  HW_POLL_PID=""

  if ! $HW_MONITOR_ENABLED; then
    return 0
  fi

  if ! _check_metrics_manager; then
    echo ">>>>> [HW Monitor] metrics-manager not reachable at ${METRICS_URL}." >&2
    HW_MONITOR_ENABLED=false
    return 1
  fi

  echo ">>>>> [HW Monitor] Started → ${HW_SAMPLE_FILE}" >&2

  # Python3 SSE streamer: events arrive as fast as metrics-manager sends them,
  # killed cleanly via kill $HW_POLL_PID.
  cat > "$_HW_STREAM_PY" << 'PYEOF'
import sys, json, urllib.request, time
outfile, base_url, interval = sys.argv[1], sys.argv[2].rstrip("/"), float(sys.argv[3])
sse_url  = base_url + "/metrics/stream"
rest_url = base_url + "/api/v1/metrics/latest"

def _key(name, labels):
    tag = labels.get("type") or labels.get("engine") or labels.get("domain") or ""
    return (name + "__" + tag) if tag else name

def _write(mlist, f):
    for m in mlist:
        name = m.get("name", "")
        val  = m.get("value")
        if val is None or not name:
            continue
        labels = m.get("labels", {})
        if labels.get("gpu_id") not in (None, "0"):
            continue
        f.write(_key(name, labels) + "=" + str(val) + "\n")
    f.write("---\n")
    f.flush()

def _sse(f):
    req = urllib.request.urlopen(sse_url)
    for raw in req:
        line = raw.decode("utf-8", errors="replace").strip()
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                ml = data.get("metrics", [])
                if isinstance(ml, list):
                    _write(ml, f)
            except Exception:
                pass

def _rest(f):
    while True:
        try:
            with urllib.request.urlopen(rest_url, timeout=5) as r:
                md = json.loads(r.read()).get("metrics", {})
                ml = []
                for k, e in md.items():
                    if not isinstance(e, dict):
                        continue
                    v = e.get("fields", {}).get("value")
                    if v is None:
                        continue
                    ml.append({"name": e.get("name", k.split("{")[0]),
                                "labels": e.get("tags", {}), "value": v})
                _write(ml, f)
        except Exception:
            pass
        time.sleep(interval)

with open(outfile, "a") as f:
    try:
        _sse(f)
    except Exception:
        _rest(f)
PYEOF
  python3 -u "$_HW_STREAM_PY" "$HW_SAMPLE_FILE" "$METRICS_URL" "$METRICS_INTERVAL" &
  HW_POLL_PID=$!
  return 0
}

# ───────────────────────────────────────────────────────────────────────────────
#  stop_hw_monitor
#  Stops the background poller. Call after the measurement window ends,
#  before stopping pipelines.
# ───────────────────────────────────────────────────────────────────────────────
function stop_hw_monitor() {
  if [ -n "$HW_POLL_PID" ] && kill -0 "$HW_POLL_PID" 2>/dev/null; then
    kill "$HW_POLL_PID" 2>/dev/null
    wait "$HW_POLL_PID" 2>/dev/null
  fi
  HW_POLL_PID=""
}

# ───────────────────────────────────────────────────────────────────────────────
#  get_hw_metrics_summary <sample_file>
#
#  Reads <sample_file> (key=value lines separated by "---" per snapshot) and
#  prints aggregated avg/min/max for every HW metric to stdout.
#
#  Metrics reported:
#    CPU    : cpu_util_pct, cpu_usage_user, cpu_usage_system,
#             cpu_freq_mhz, mem_used_percent, cpu_temperature
#    GPU    : gpu_compute_util_pct (CCS — OpenVINO AI inference)
#             gpu_video_util_pct   (VCS — H.264 hardware decode)
#             gpu_render_util_pct  (RCS — 3D render)
#             gpu_enhance_util_pct (VECS — video enhance)
#             gpu_util_combined    (max(CCS,VCS) per sample, then averaged)
#             gpu_freq_mhz
#    Power  : rapl_psys_w  (full platform incl. dGPU + DRAM)
#             rapl_pkg_w   (SoC: CPU + iGPU)
#             rapl_core_w  (CPU cores only)
#             rapl_uncore_w
#             gpu_power_w  (qmassa gpu_cur_power)
#             pkg_power_w  (qmassa pkg_cur_power)
#    NPU    : npu_utilization, npu_frequency, npu_power,
#             npu_temperature, npu_memory_mb, npu_bandwidth
# ───────────────────────────────────────────────────────────────────────────────
function get_hw_metrics_summary() {
  local sample_file=$1

  if [ ! -f "$sample_file" ] || [ ! -s "$sample_file" ]; then
    echo "hw_sample_count: 0"
    return
  fi

  gawk '
  BEGIN {
    lbl["cpu_usage_idle"]                        = "cpu_util_pct"
    lbl["cpu_usage_user"]                        = "cpu_usage_user"
    lbl["cpu_usage_system"]                      = "cpu_usage_system"
    lbl["cpu_frequency_avg_frequency"]           = "cpu_freq_mhz"
    lbl["temp_temp"]                             = "cpu_temperature"
    lbl["mem_used_percent"]                      = "mem_used_percent"
    lbl["gpu_engine_usage_usage__ccs"]           = "gpu_compute_util_pct"
    lbl["gpu_engine_usage_usage__compute"]       = "gpu_compute_util_pct"
    lbl["gpu_engine_usage_usage__vcs"]           = "gpu_video_util_pct"
    lbl["gpu_engine_usage_usage__video"]         = "gpu_video_util_pct"
    lbl["gpu_engine_usage_usage__rcs"]           = "gpu_render_util_pct"
    lbl["gpu_engine_usage_usage__render"]        = "gpu_render_util_pct"
    lbl["gpu_engine_usage_usage__vecs"]          = "gpu_enhance_util_pct"
    lbl["gpu_engine_usage_usage__video-enhance"] = "gpu_enhance_util_pct"
    lbl["gpu_frequency__cur_freq"]               = "gpu_freq_mhz"
    lbl["gpu_power__gpu_cur_power"]              = "gpu_power_w"
    lbl["gpu_power__pkg_cur_power"]              = "pkg_power_w"
    lbl["rapl_power_w__psys"]                    = "rapl_psys_w"
    lbl["rapl_power_w__pkg"]                     = "rapl_pkg_w"
    lbl["rapl_power_w__core"]                    = "rapl_core_w"
    lbl["rapl_power_w__uncore"]                  = "rapl_uncore_w"
    lbl["npu_utilization"]                       = "npu_utilization"
    lbl["npu_frequency"]                         = "npu_frequency"
    lbl["npu_power"]                             = "npu_power"
    lbl["npu_temperature"]                       = "npu_temperature"
    lbl["npu_memory_mb"]                         = "npu_memory_mb"
    lbl["npu_bandwidth"]                         = "npu_bandwidth"

    scale["cpu_frequency_avg_frequency"] = 0.001   # kHz -> MHz
    GPU_POWER_CAP = 500.0

    sample_ct    = 0
    gpu_comb_sum = 0
    gpu_comb_cnt = 0
    gpu_comb_min = 0
    gpu_comb_max = 0
    cur_ccs      = ""
    cur_vcs      = ""
  }

  /^---$/ {
    if (cur_ccs != "" || cur_vcs != "") {
      ccs_v    = (cur_ccs != "") ? (cur_ccs + 0) : 0
      vcs_v    = (cur_vcs != "") ? (cur_vcs + 0) : 0
      combined = (ccs_v > vcs_v) ? ccs_v : vcs_v
      if (gpu_comb_cnt == 0) {
        gpu_comb_min = combined
        gpu_comb_max = combined
      } else {
        if (combined < gpu_comb_min) gpu_comb_min = combined
        if (combined > gpu_comb_max) gpu_comb_max = combined
      }
      gpu_comb_sum += combined
      gpu_comb_cnt++
    }
    cur_ccs = ""; cur_vcs = ""
    sample_ct++
    next
  }

  /=/ {
    eq  = index($0, "=")
    if (eq <= 1) next
    key = substr($0, 1, eq - 1)
    val = substr($0, eq + 1) * 1.0
    if (!(key in lbl)) next
    if (key == "gpu_power__gpu_cur_power" || key == "gpu_power__pkg_cur_power") {
      if (val <= 0 || val >= GPU_POWER_CAP) next
    }
    if (key == "gpu_engine_usage_usage__ccs"  || key == "gpu_engine_usage_usage__compute") cur_ccs = val
    if (key == "gpu_engine_usage_usage__vcs"  || key == "gpu_engine_usage_usage__video")   cur_vcs = val
    if (!(key in cnt)) { cnt[key]=0; raw_sum[key]=0; raw_min[key]=val; raw_max[key]=val }
    cnt[key]++
    raw_sum[key] += val
    if (val < raw_min[key]) raw_min[key] = val
    if (val > raw_max[key]) raw_max[key] = val
  }

  END {
    print "hw_sample_count: " sample_ct
    if (sample_ct == 0) exit
    split("", printed)
    for (key in cnt) {
      if (!(key in lbl)) continue
      friendly = lbl[key]
      if (friendly in printed) continue
      n = cnt[key]
      if (n == 0) continue
      s = (key in scale) ? scale[key] : 1.0
      if (key == "cpu_usage_idle") {
        avg_v = 100.0 - (raw_sum[key] / n)
        min_v = 100.0 - raw_max[key]
        max_v = 100.0 - raw_min[key]
      } else {
        avg_v = (raw_sum[key] / n) * s
        min_v = raw_min[key] * s
        max_v = raw_max[key] * s
      }
      printf "hw_%s avg: %.3f\n", friendly, avg_v
      printf "hw_%s min: %.3f\n", friendly, min_v
      printf "hw_%s max: %.3f\n", friendly, max_v
      printed[friendly] = 1
    }
    if (gpu_comb_cnt > 0) {
      printf "hw_gpu_util_combined avg: %.3f\n", gpu_comb_sum / gpu_comb_cnt
      printf "hw_gpu_util_combined min: %.3f\n", gpu_comb_min
      printf "hw_gpu_util_combined max: %.3f\n", gpu_comb_max
    }
  }
  ' "$sample_file"
}

# ═══════════════════════════════════════════════════════════════════════════════
#  Pipeline runner functions
# ═══════════════════════════════════════════════════════════════════════════════

DLSPS_NODE_IP="${DLSPS_NODE_IP:-localhost}"
DLSPS_PORT="${DLSPS_PORT:-8081}"
DLSPS_BASE_URL="http://${DLSPS_NODE_IP}:${DLSPS_PORT}"

function get_pipeline_status() {
    curl -s "${DLSPS_BASE_URL}/pipelines/status" "$@"
}

function check_and_loop_video() {
  local payload=$1
  local source_uri=$(echo "$payload" | jq -r '.source.uri // empty')

  if [ -z "$source_uri" ]; then
    return 0
  fi

  local filename=$(basename "$source_uri")

  if [[ "$filename" =~ _looped\.mp4$ ]]; then
    local base_filename="${filename%_looped.mp4}.mp4"
    local base_file=""
    local search_paths=(
      "./loitering-detection/src/dlstreamer-pipeline-server/videos"
      "./smart-parking/src/dlstreamer-pipeline-server/videos"
    )

    for search_path in "${search_paths[@]}"; do
      if [ -f "$search_path/$base_filename" ]; then
        base_file="$search_path/$base_filename"
        break
      fi
    done

    if [ -z "$base_file" ]; then
      echo "Error: Base video file not found: $base_filename" >&2
      return 1
    fi

    local output_file="$(dirname "$base_file")/$filename"

    if [ -f "$output_file" ]; then
      echo "Looped video already exists: $output_file" >&2
      return 0
    fi

    if ! command -v ffmpeg &> /dev/null; then
      echo "Error: ffmpeg is required to create looped video but is not installed." >&2
      return 1
    fi

    echo "Creating looped video: $output_file from $base_file" >&2
    ffmpeg -stream_loop 10 -i "$base_file" \
      -c copy -movflags +faststart \
      "$output_file" -y 2>&1 | grep -v "frame=" >&2

    if [ $? -ne 0 ]; then
      echo "Error: Failed to create looped video." >&2
      return 1
    fi
    echo "Successfully created looped video: $output_file" >&2
  fi

  return 0
}

# Keep track of pipeline IDs created in the current run
# Used to filter get_pipeline_status so old history is ignored
CURRENT_RUN_IDS=()

# Get status filtered to only pipelines from the CURRENT run
# Falls back to full status if no IDs tracked yet
function get_current_pipeline_status() {
  local full_status
  full_status=$(get_pipeline_status)
  if [ ${#CURRENT_RUN_IDS[@]} -eq 0 ]; then
    echo "$full_status"
    return
  fi
  # Build jq filter: select only IDs we started
  local id_filter
  id_filter=$(printf '"%s",' "${CURRENT_RUN_IDS[@]}")
  id_filter="[${id_filter%,}]"
  echo "$full_status" | jq --argjson ids "$id_filter" '[.[] | select(.id as $i | $ids | index($i) != null)]' 2>/dev/null || echo "$full_status"
}

# Generate all per-stream payloads in one jq process.
# This avoids launching jq repeatedly inside the stream POST loop.
function generate_stream_payloads() {
        # Make RTSP path, metadata file, topic, and peer-id unique per stream.
        # DLSPS errors if two pipelines share the same RTSP frame path.
  local payload_data=$1
  local pipeline_name=$2
  local count=$3
  local run_ts=$4
  local mode=${5:-density}

  jq -c \
    --arg pipeline "$pipeline_name" \
    --arg run_ts "$run_ts" \
    --arg mode "$mode" \
    --argjson count "$count" ' 
      range(1; $count + 1) as $x
      | .
      | if .destination then
          if $mode == "density" then
            .destination.metadata.topic = ("object_detection_" + $pipeline + "_" + ($x|tostring))
            | .destination.metadata.path = ("/tmp/bm_" + $pipeline + "_" + $run_ts + "_" + ($x|tostring) + ".jsonl")
            | .destination.frame."peer-id" = ("object_detection_" + $pipeline + "_" + ($x|tostring))
            | .destination.frame.path = ("bm-" + $run_ts + "-s" + ($x|tostring))
          else
            .destination.metadata.topic = ($pipeline + "_" + $run_ts + "_" + ($x|tostring))
            | .destination.frame."peer-id" = ($pipeline + "_" + $run_ts + "_" + ($x|tostring))
            | .destination.frame.path = ("bm-" + $run_ts + "-" + ($pipeline[0:3]) + "-s" + ($x|tostring))
          end
        else . end
      | .parameters["detection-properties"]["model-instance-id"] =
          (if $mode == "density"
           then "inst_benchmark_" + $pipeline + "_stream_" + ($x|tostring)
           else "inst_bm_" + $pipeline + "_" + $run_ts + "_" + ($x|tostring)
           end)
    ' <<< "$payload_data"
}

# Post one already-generated payload and track its returned pipeline ID.
function post_pipeline() {
    # Capture the returned pipeline ID (response is a bare UUID string)
  # Capture the returned pipeline ID (response is a bare UUID string)
  local pipeline_name=$1
  local current_payload=$2
  local label=$3
  local response http_code response_body pid

  response=$(curl -k -s -w "\nHTTP_CODE:%{http_code}" \
    "${DLSPS_BASE_URL}/pipelines/user_defined_pipelines/${pipeline_name}" \
    -X POST -H "Content-Type: application/json" -d "$current_payload")

  http_code=${response##*$'\n'HTTP_CODE:}
  response_body=${response%$'\n'HTTP_CODE:*}

  if [ "$http_code" != "200" ] && [ "$http_code" != "201" ]; then
    echo "Error: Pipeline $label creation failed with HTTP $http_code" >&2
    echo "Response: $response_body" >&2
    return 1
  fi

  pid=$(tr -d '"[:space:]' <<< "$response_body")
  if [ -n "$pid" ]; then
    CURRENT_RUN_IDS+=("$pid")
    echo "  Started pipeline $label → ID: $pid" >&2
  fi
}

function run_pipelines() {
  local num_pipelines=$1
  local payload_data=$2
  local pipeline_name=$3

  # Reset tracked IDs for this run
  CURRENT_RUN_IDS=()
  # Unique timestamp for this specific run invocation — ensures RTSP paths never
  # conflict with paths from previous runs (DLSPS keeps ABORTED paths registered)
  local RUN_TS
  RUN_TS=$(date +%s%N | tail -c 8)

  echo >&2
  echo ">>>>> Initialization: Starting $num_pipelines pipeline(s) of type '$pipeline_name'..." >&2

  # Generate all stream payloads once; only the POST loop remains per-stream.
  local current_payload x=0
  while IFS= read -r current_payload; do
    x=$((x + 1))

    # Make RTSP path, metadata file, topic, and peer-id unique per stream.
    # DLSPS errors if two pipelines share the same RTSP frame path.
    # ── Unique model-instance-id per stream ────────────────────────────────
    # The pipeline template uses a shared model-instance-id (instcpu0/instgpu0/instnpu0).
    # Running N concurrent streams all with the same ID causes stream 2+ to ERROR.
    # Override via detection-properties so each stream gets its own model instance.
    post_pipeline "$pipeline_name" "$current_payload" "$x" || return 1
    sleep 0.5
  done < <(generate_stream_payloads "$payload_data" "$pipeline_name" "$num_pipelines" "$RUN_TS" density)

  [ "$x" -eq "$num_pipelines" ] || {
    echo "Error: Failed to generate all $num_pipelines stream payloads." >&2
    return 1
  }

  echo -n ">>>>> Waiting for pipelines to initialize..." >&2
  local running_count=0
  local attempts=0
  while [ "$running_count" -lt "$num_pipelines" ] && [ "$attempts" -lt 90 ]; do
    local status_output
    status_output=$(get_current_pipeline_status)
    running_count=$(echo "$status_output" | jq '[.[] | select(.state=="RUNNING" or .state=="ABORTED" or .state=="COMPLETED" or .state=="ERROR")] | length' 2>/dev/null || echo 0)
    echo -n "." >&2
    attempts=$((attempts + 1))
    sleep 2
  done

  local _nr _ne
  _nr=$(get_current_pipeline_status | jq '[.[] | select(.state=="RUNNING")] | length' 2>/dev/null || echo 0)
  _ne=$(get_current_pipeline_status | jq '[.[] | select(.state=="ERROR")] | length' 2>/dev/null || echo 0)
  if [ "$_nr" -eq 0 ]; then
    echo " Error: All $num_pipelines pipeline(s) failed to start (ERROR state)." >&2
    return 1
  fi
  [ "$_ne" -gt 0 ] && echo " Warning: $_ne pipeline(s) in ERROR, $_nr actually running." >&2 || echo " All $num_pipelines pipeline(s) ready." >&2
  return 0
}

function stop_all_pipelines() {
  echo >&2
  echo ">>>>> Attempting to stop all running pipelines." >&2

  local pipelines_str
  pipelines_str=$(get_current_pipeline_status | jq -r '[.[] | select(.state=="RUNNING" or .state=="QUEUED" or .state=="STARTING" or .state=="ERROR") | .id] | join(",")')

  if [ $? -ne 0 ]; then
    echo -e "\nError: Failed to get pipeline status." >&2
    return 1
  fi

  if [ -z "$pipelines_str" ]; then
    echo "No running pipelines found." >&2
    return 0
  fi

  IFS=',' read -ra pipelines <<< "$pipelines_str"
  echo "Found ${#pipelines[@]} running pipelines to stop." >&2

  for pipeline_id in "${pipelines[@]}"; do
    curl -s --location -X DELETE "${DLSPS_BASE_URL}/pipelines/${pipeline_id}" >/dev/null &
  done

  wait
  echo "All stop requests sent." >&2
  unset IFS

  echo -n ">>>>> Waiting for all pipelines to stop..." >&2
  local running=true
  while $running; do
    echo -n "." >&2
    local status
    status=$(get_current_pipeline_status | jq '.[] | .state' | grep "RUNNING")
    if [[ -z "$status" ]]; then
      running=false
    else
      sleep 3
    fi
  done
  echo " done." >&2
  echo >&2
  return 0
}

# ───────────────────────────────────────────────────────────────────────────────
#  run_and_analyze_workload <num_streams> <pipeline_name> <payload_file>
#
#  HW metrics integration:
#    1. start_hw_monitor called after run_pipelines returns (all streams
#       RUNNING)
#    2. stop_hw_monitor called after FPS window, before pipeline teardown
#    3. get_hw_metrics_summary appended to kpi.txt after FPS stats
# ───────────────────────────────────────────────────────────────────────────────
function run_and_analyze_workload() {
    local num_streams=$1
    local pipeline_name_arg=$2
    local payload_file=$3

    rm -rf "benchmark-$num_streams" && mkdir -p "benchmark-$num_streams"

    local payload_body
    payload_body=$(jq -r --arg name "$pipeline_name_arg" '.[] | select(.pipeline == $name) | .payload' "$payload_file")

    if [ -z "$payload_body" ]; then
        echo "Error: Pipeline '$pipeline_name_arg' not found in $payload_file" >&2
        return 1
    fi

    check_and_loop_video "$payload_body"
    if [ $? -ne 0 ]; then
      echo "Error: Video preparation failed." >&2
      return 1
    fi

    run_pipelines "$num_streams" "$payload_body" "$pipeline_name_arg"
    if [ $? -ne 0 ]; then
      echo "Failed to start pipelines. Aborting." >&2
      return 1
    fi

    # ── HW METRICS: Start monitor (pipelines RUNNING) ────
    start_hw_monitor "benchmark-$num_streams"

    echo ">>>>> Monitoring FPS for $MAX_DURATION seconds..." >&2
    local start_time=$SECONDS
    while (( SECONDS - start_time < MAX_DURATION )); do
        local elapsed_time=$((SECONDS - start_time))
        echo -ne "Monitoring... ${elapsed_time}s / ${MAX_DURATION}s\r" >&2
        get_current_pipeline_status >> "benchmark-$num_streams/sample.logs" 2>/dev/null
        sleep 1
    done
    echo -ne "\n" >&2

    # ── HW METRICS: Stop monitor before pipeline teardown ───────
    stop_hw_monitor

    stop_all_pipelines

    gawk -v ns=$num_streams -v percentile=${THROUGHPUT_PERCENTILE:-0.9} "$awk_utils"'
    /^\[/ {
      split("",fps_running)
      ns_running=0
    }
    /"avg_fps":/ {
      fps=$2*1
    }
    /"state": "(RUNNING|ABORTED|COMPLETED)"/ {
      fps_running[++ns_running]=fps
    }
    /^\]/ && ns_running==ns {
      for (i=1;i<=ns;i++)
        throughput[i][++throughput_ct[i]]=fps_running[i]
    }
    END {
      ns=length(throughput)
      if (ns>0) {
        ns1=0
        for (i=1;i<=ns;i++) {
          throughput_p[i]=calc_percentile(throughput[i],percentile)
          if (throughput_p[i]>0) {
            throughput_std[i]=calc_stdev(throughput[i])
            print "throughput #"i": "throughput_p[i]
            ns1++
          }
        }
        print "throughput median: "calc_median(throughput_p)
        print "throughput average: "calc_avg(throughput_p)
        print "throughput stdev: "calc_max(throughput_std)
        print "throughput cumulative: "calc_sum(throughput_p)
        mm=(ns1<ns)?0:calc_min(throughput_p)
        print "throughput min: "mm
      }
    }
  ' "benchmark-$num_streams/sample.logs" > "benchmark-$num_streams/kpi.txt"

    # ── HW METRICS: Append hw metrics summary to kpi.txt ───────────────────
    if $HW_MONITOR_ENABLED && [ -f "benchmark-$num_streams/hw_samples.log" ]; then
      echo "---hw-metrics---" >> "benchmark-$num_streams/kpi.txt"
      get_hw_metrics_summary "benchmark-$num_streams/hw_samples.log" \
        >> "benchmark-$num_streams/kpi.txt"
    fi
}

function run_workload_with_retries() {
  local num_streams=$1
  local pipeline_name_arg=$2
  local payload_file=$3
  local throughput=0
  local throughput_max=0
  local retry_ct=0
  while [ $retry_ct -lt ${RETRY_TIMES:-1} ]; do
    echo "Invoking workload with $num_streams streams...try#$retry_ct" >&2
    if run_and_analyze_workload "$num_streams" "$pipeline_name_arg" "$payload_file" >/dev/null 2>&1; then
      grep -E '^(throughput|hw_sample_count)' "benchmark-$num_streams/kpi.txt" | \
        sed "s|^|stream-density#$num_streams: |" >&2
      throughput=$(grep -m1 -F 'throughput min:' "benchmark-$num_streams/kpi.txt" | cut -f2 -d: | tr -d ' ')
      if echo "${throughput:-0} $target_fps" | gawk '{exit($1>=$2?0:1)}'; then
        echo "$throughput"
        return 0
      fi
      if echo "${throughput:-0} $throughput_max" | gawk '{exit($1>$2?0:1)}'; then
        throughput_max=$throughput
        rm -rf "benchmark-$num_streams.max"
        mv -f "benchmark-$num_streams" "benchmark-$num_streams.max"
      fi
    fi
    let retry_ct++
  done
  if [ -d "benchmark-$num_streams.max" ]; then
    rm -rf "benchmark-$num_streams"
    mv -f "benchmark-$num_streams.max" "benchmark-$num_streams"
  fi
  echo "$throughput_max"
}

# ───────────────────────────────────────────────────────────────────────────────
#  run_concurrent_workload <pipelines_csv> <nstreams_csv> <payload_file>
#
#  Runs multiple pipeline types simultaneously (nstreams mode).
# ───────────────────────────────────────────────────────────────────────────────
function run_concurrent_workload() {
  local pipelines_csv=$1
  local nstreams_csv=$2
  local payload_file=$3

  IFS=',' read -ra pipeline_names <<< "$pipelines_csv"
  IFS=',' read -ra nstreams_list  <<< "$nstreams_csv"

  CURRENT_RUN_IDS=()
  local total_streams=0
  for n in "${nstreams_list[@]}"; do
    total_streams=$((total_streams + n))
  done

  local outdir="benchmark-multi"
  rm -rf "$outdir" && mkdir -p "$outdir"

  local RUN_TS
  RUN_TS=$(date +%s%N | tail -c 8)

  for i in "${!pipeline_names[@]}"; do
    local pname="${pipeline_names[$i]}"
    local nstreams="${nstreams_list[$i]}"

    local payload_body
    payload_body=$(jq -r --arg name "$pname" '.[] | select(.pipeline == $name) | .payload' "$payload_file")
    if [ -z "$payload_body" ]; then
      echo "Error: Pipeline '$pname' not found in $payload_file" >&2
      return 1
    fi

    check_and_loop_video "$payload_body"
    if [ $? -ne 0 ]; then
      echo "Error: Video preparation failed for '$pname'." >&2
      return 1
    fi

    echo >&2
    echo -n ">>>>> Starting $nstreams stream(s) for pipeline '$pname'..." >&2
    local current_payload x=0
    while IFS= read -r current_payload; do
      x=$((x + 1))
      post_pipeline "$pname" "$current_payload" "$x" || return 1
      sleep 0.5
    done < <(generate_stream_payloads "$payload_body" "$pname" "$nstreams" "$RUN_TS" nstreams)

    [ "$x" -eq "$nstreams" ] || {
      echo "Error: Failed to generate all $nstreams stream payloads for '$pname'." >&2
      return 1
    }
    echo " done." >&2
  done

  echo -n ">>>>> Waiting for all $total_streams pipeline(s) to reach RUNNING state..." >&2
  local running_count=0
  local attempts=0
  while [ "$running_count" -lt "$total_streams" ] && [ "$attempts" -lt 120 ]; do
    running_count=$(get_current_pipeline_status | jq '[.[] | select(.state=="RUNNING" or .state=="ABORTED" or .state=="COMPLETED" or .state=="ERROR")] | length' 2>/dev/null || echo 0)
    echo -n "." >&2
    attempts=$((attempts + 1))
    sleep 2
  done

  local _nr _ne
  _nr=$(get_current_pipeline_status | jq '[.[] | select(.state=="RUNNING")] | length' 2>/dev/null || echo 0)
  _ne=$(get_current_pipeline_status | jq '[.[] | select(.state=="ERROR")] | length' 2>/dev/null || echo 0)
  if [ "$_nr" -eq 0 ]; then
    echo " Error: No pipelines running (all $total_streams ERRORed)." >&2
    return 1
  fi
  [ "$_ne" -gt 0 ] && echo " $_nr/$total_streams pipeline(s) running ($_ne in ERROR — hardware capacity exceeded)." >&2 || echo " All $total_streams pipeline(s) running." >&2

  # ── HW METRICS: Start monitor ─────
  start_hw_monitor "$outdir"

  echo ">>>>> Monitoring all $total_streams nstreams-mode stream(s) for $MAX_DURATION seconds..." >&2
  local start_time=$SECONDS
  while (( SECONDS - start_time < MAX_DURATION )); do
    local elapsed_time=$((SECONDS - start_time))
    echo -ne "Monitoring... ${elapsed_time}s / ${MAX_DURATION}s\r" >&2
    get_current_pipeline_status >> "$outdir/sample.logs" 2>/dev/null
    sleep 1
  done
  echo -ne "\n" >&2

  # ── HW METRICS: Stop monitor before pipeline teardown ────
  stop_hw_monitor

  stop_all_pipelines

  gawk -v ns=$total_streams -v percentile="${THROUGHPUT_PERCENTILE:-0.9}" "$awk_utils"'
  /^\[/ { split("",fps_running); ns_running=0 }
  /"avg_fps":/ { fps=$2*1 }
  /"state": "(RUNNING|ABORTED|COMPLETED)"/ { fps_running[++ns_running]=fps }
  /^\]/ && ns_running==ns {
    for (i=1;i<=ns;i++) throughput[i][++throughput_ct[i]]=fps_running[i]
  }
  END {
    ns=length(throughput)
    if (ns>0) {
      ns1=0
      for (i=1;i<=ns;i++) {
        throughput_p[i]=calc_percentile(throughput[i],percentile)
        if (throughput_p[i]>0) { throughput_std[i]=calc_stdev(throughput[i]); print "throughput #"i": "throughput_p[i]; ns1++ }
      }
      print "throughput median: "calc_median(throughput_p)
      print "throughput average: "calc_avg(throughput_p)
      print "throughput stdev: "calc_max(throughput_std)
      print "throughput cumulative: "calc_sum(throughput_p)
      mm=(ns1<ns)?0:calc_min(throughput_p)
      print "throughput min: "mm
    }
  }
  ' "$outdir/sample.logs" > "$outdir/kpi.txt"

  # ── HW METRICS: Append hw metrics summary to kpi.txt ────
  if $HW_MONITOR_ENABLED && [ -f "$outdir/hw_samples.log" ]; then
    echo "---hw-metrics---" >> "$outdir/kpi.txt"
    get_hw_metrics_summary "$outdir/hw_samples.log" >> "$outdir/kpi.txt"
  fi
}

# ═══════════════════════════════════════════════════════════════════════════════
#  _density_search_expbisect <pipeline_name> <payload_file>
#
#  Automatic exponential + bisect stream-density search.
#
#  Algorithm:
#    Phase 1 — Exponential doubling:
#      Test N = 1, 2, 4, 8, 16, ... until FPS drops below floor OR N >= maxn.
#      If -l is supplied, the exponential phase starts from that lower bound.
#    Phase 2 — Bisect:
#      Binary-search between last-passing N (lo) and first-failing N (hi)
#      until hi - lo <= 1 → lo is the max sustainable stream count.
#
#  Sets globals (used by --all-devices summary table):
#    DENSITY_RESULT_N      — max sustainable stream count found
#    DENSITY_RESULT_FPS    — fps/stream at DENSITY_RESULT_N
#    DENSITY_RESULT_CPU    — avg cpu_util_pct at DENSITY_RESULT_N (or N/A)
#    DENSITY_RESULT_GPU    — avg gpu_util_combined at DENSITY_RESULT_N (or N/A)
#    DENSITY_RESULT_NPU    — avg npu_utilization at DENSITY_RESULT_N (or N/A)
#    DENSITY_RESULT_PKG    — avg pkg_power_w at DENSITY_RESULT_N (or N/A)
#
#  Best result is also copied to: benchmark-density-<pipeline_name>/
# ═══════════════════════════════════════════════════════════════════════════════
function _density_search_expbisect() {
  local pipeline_name=$1
  local payload_file=$2
  local floor="${target_fps:-14.95}"
  local maxn="${upper_bound:-24}"

  # Reset output globals
  DENSITY_RESULT_N=0
  DENSITY_RESULT_FPS=0
  DENSITY_RESULT_CPU="N/A"
  DENSITY_RESULT_GPU="N/A"
  DENSITY_RESULT_NPU="N/A"
  DENSITY_RESULT_PKG="N/A"

  echo >&2
  echo ">>>>> Density search (exp+bisect): $pipeline_name" >&2
  echo "      floor=${floor} fps   max=${maxn} streams   window=${MAX_DURATION}s" >&2

  local n=${lower_bound:-1} lo=$(( ${lower_bound:-1} - 1 )) hi=-1 best_n=0 best_fps=0 exp=true

  while true; do
    # Clamp to upper bound
    [ $n -gt $maxn ] && n=$maxn

    echo ">>>>> [density]   Testing N=${n} streams for '${pipeline_name}'..." >&2
    local fps
    fps=$(run_workload_with_retries "$n" "$pipeline_name" "$payload_file")

    local passed=false
    if echo "${fps:-0} ${floor}" | gawk '{exit($1>=$2?0:1)}'; then
      passed=true
    fi

    if $passed; then
      echo ">>>>> [density]   N=${n} → ${fps} fps/stream  (floor=${floor}) — ✓" >&2
      best_n=$n
      best_fps=$fps
      lo=$n
    else
      echo ">>>>> [density]   N=${n} → ${fps} fps/stream  (floor=${floor}) — ✗" >&2
      hi=$n
    fi

    if $exp; then
      # ── Exponential phase ─────────
      if $passed; then
        if [ $n -ge $maxn ]; then
          break   # hit upper bound and still passing → done
        fi
        n=$((n * 2))   # double
      else
        if [ $n -eq "$lower_bound" ]; then
          break   # Starting N fails → nothing sustainable at the requested lower bound.
        fi
        # Switch to bisect phase: lo = last passing, hi = first failing
        exp=false
        n=$(( (lo + hi + 1) / 2 ))
      fi
    else
      # ── Bisect phase ───────
      [ $lo -ge $((hi - 1)) ] && break   # converged
      n=$(( (lo + hi + 1) / 2 ))
    fi
  done

  DENSITY_RESULT_N=$best_n
  DENSITY_RESULT_FPS=$best_fps

  echo >&2
  echo ">>>>> Density result: max sustainable = ${best_n} streams @ ${best_fps} fps/stream" >&2

  # Extract utilization metrics from best run's kpi.txt
  if [ $best_n -gt 0 ] && [ -f "benchmark-${best_n}/kpi.txt" ]; then
    local cu gu nu
    cu=$(grep -m1 'hw_cpu_util_pct avg:' "benchmark-${best_n}/kpi.txt" 2>/dev/null | awk '{print $NF}')
    gu=$(grep -m1 'hw_gpu_util_combined avg:' "benchmark-${best_n}/kpi.txt" 2>/dev/null | awk '{print $NF}')
    nu=$(grep -m1 'hw_npu_utilization avg:' "benchmark-${best_n}/kpi.txt" 2>/dev/null | awk '{print $NF}')
    pw=$(grep -m1 'hw_pkg_power_w avg:' "benchmark-${best_n}/kpi.txt" 2>/dev/null | awk '{print $NF}')
    [ -n "$cu" ] && DENSITY_RESULT_CPU="$cu"
    [ -n "$gu" ] && DENSITY_RESULT_GPU="$gu"
    [ -n "$nu" ] && DENSITY_RESULT_NPU="$nu"
    [ -n "$pw" ] && DENSITY_RESULT_PKG="$pw"

    # Copy best result to a named output directory; clean intermediate numbered dirs
    local outdir="benchmark-density-${pipeline_name}"
    rm -rf "$outdir"
    cp -r "benchmark-${best_n}" "$outdir"
    echo ">>>>> [density]   KPI saved → ${outdir}/kpi.txt" >&2
    for _bd in benchmark-[0-9]*/; do [ -d "$_bd" ] && rm -rf "$_bd"; done
  fi
}

# ═══════════════════════════════════════════════════════════════════════════════
#  Main Script
# ═══════════════════════════════════════════════════════════════════════════════

function usage() {
    echo "Usage (stream-density — single pipeline, automatic exp+bisect):"
    echo "  $0 -p <pipeline_name> [-u <max_streams>] \\"
    echo "     [-t <target_fps>] [-i <window_sec>] [-c <percentile>]"
    echo
    echo "Usage (stream-density — all devices, sequential density per pipeline):"
    echo "  $0 --all-devices -p <cpu_pipeline> <gpu_pipeline> <npu_pipeline> \\"
    echo "     [-t <target_fps>] [-i <window_sec>] [-u <max_streams>]"
    echo "  Example: $0 --all-devices \\"
    echo "     -p drone_object_detection_cpu drone_object_detection_gpu drone_object_detection_npu"
    echo
    echo "Usage (nstreams — fixed stream count per pipeline, concurrent):"
    echo "  $0 -p <p1> [p2 ...] -nstreams <N1> [N2 ...] \\"
    echo "     [-t <target_fps>] [-i <window_sec>]"
    echo "  Example: $0 -p drone_object_detection_gpu drone_object_detection_npu -nstreams 2 7"
    echo
    echo "Arguments:"
    echo "  -p <name(s)>         Pipeline name(s) from benchmark_app_payload.json."
    echo "  -u <max_streams>     Upper bound for exp+bisect search (default: 24)."
    echo "  -l <lower_bound>     Starting stream count for exp+bisect search (default: 1)."
    echo "  -t <target_fps>      FPS floor for stream-density (default: 14.95)."
    echo "  -i <window_sec>      FPS monitoring window in seconds (default: 60)."
    echo "  -c <percentile>      Throughput percentile for KPI (default: 0.9 = p90)."
    echo "  --all-devices        Run density search for all -p pipelines sequentially"
    echo "                       and print a unified claim-statement summary table."
    echo "  -nstreams <N1> [N2 ...] Fixed stream count per pipeline (nstreams mode)."
    echo
    echo "HW Metrics (metrics-manager — no -m/-M needed for localhost:9090):"
    echo "  -m <url>             metrics-manager base URL (default: http://localhost:9090)."
    echo "  -M <seconds>         HW polling interval in seconds (default: 2)."
    echo "  --no-hw-metrics      Disable HW metrics collection entirely."
    echo
    echo "Environment variables (override defaults without CLI flags):"
    echo "  METRICS_URL          Same as -m."
    echo "  METRICS_INTERVAL     Same as -M."
    exit 1
}

# ── nstreams mode ───────────────────
if [[ " $* " == *" -nstreams "* ]]; then
  _multi_pipelines=()
  _multi_nstreams=()
  _multi_target_fps="14.95"
  MAX_DURATION=60
  THROUGHPUT_PERCENTILE="0.9"

  _idx=1
  while (( _idx <= $# )); do
    _arg="${!_idx}"
    case "$_arg" in
      -p)
        _idx=$((_idx + 1))
        while (( _idx <= $# )) && [[ "${!_idx}" != -* ]]; do
          _multi_pipelines+=("${!_idx}")
          _idx=$((_idx + 1))
        done ;;
      -nstreams)
        _idx=$((_idx + 1))
        while (( _idx <= $# )) && [[ "${!_idx}" != -* ]]; do
          _multi_nstreams+=("${!_idx}")
          _idx=$((_idx + 1))
        done ;;
      -t)  _idx=$((_idx + 1)); _multi_target_fps="${!_idx}"; _idx=$((_idx + 1)) ;;
      -i)  _idx=$((_idx + 1)); MAX_DURATION="${!_idx}";       _idx=$((_idx + 1)) ;;
      -c)  _idx=$((_idx + 1)); THROUGHPUT_PERCENTILE="${!_idx}"; _idx=$((_idx + 1)) ;;
      -m)  _idx=$((_idx + 1)); METRICS_URL="${!_idx}";        _idx=$((_idx + 1)) ;;
      -M)  _idx=$((_idx + 1)); METRICS_INTERVAL="${!_idx}";   _idx=$((_idx + 1)) ;;
      --no-hw-metrics) HW_MONITOR_ENABLED=false; _idx=$((_idx + 1)) ;;
      *)   _idx=$((_idx + 1)) ;;
    esac
  done

  if [ ${#_multi_pipelines[@]} -eq 0 ] || [ ${#_multi_nstreams[@]} -eq 0 ]; then
    echo "Error: -nstreams mode requires at least one -p name and one stream count." >&2
    usage
  fi
  if [ ${#_multi_pipelines[@]} -ne ${#_multi_nstreams[@]} ]; then
    echo "Error: Number of -p names (${#_multi_pipelines[@]}) must match number of -nstreams values (${#_multi_nstreams[@]})." >&2
    usage
  fi

  payload_file="${SCRIPT_DIR}/benchmark_app_payload.json"
  if [ ! -f "$payload_file" ]; then echo "Error: Payload file not found: $payload_file" >&2; exit 1; fi

  echo ">>>>> Performing pre-flight checks..." >&2
  if ! curl -s --fail "${DLSPS_BASE_URL}/pipelines/status" > /dev/null; then
    echo "Error: DLSPS not reachable at ${DLSPS_BASE_URL}" >&2; exit 1
  fi
  echo "DLSPS is reachable." >&2
  if $HW_MONITOR_ENABLED; then
    echo "HW metrics: ${METRICS_URL}" >&2
  fi

  stop_all_pipelines || exit 1

  _total_concurrent=0
  for _n in "${_multi_nstreams[@]}"; do _total_concurrent=$((_total_concurrent + _n)); done

  echo ">>>>> Starting nstreams-mode workload:" >&2
  for _i in "${!_multi_pipelines[@]}"; do
    echo "       ${_multi_pipelines[$_i]}: ${_multi_nstreams[$_i]} stream(s)" >&2
  done

  if run_concurrent_workload \
      "$(IFS=,; echo "${_multi_pipelines[*]}")" \
      "$(IFS=,; echo "${_multi_nstreams[*]}")" \
      "$payload_file"; then
    # Extract key metrics from kpi.txt for the summary table
    _fps_avg=$(grep -m1 'throughput average:' "benchmark-multi/kpi.txt" | awk '{print $NF}')
    _fps_cum=$(grep -m1 'throughput cumulative:' "benchmark-multi/kpi.txt" | awk '{print $NF}')
    _cpu=$(grep -m1 'hw_cpu_util_pct avg:' "benchmark-multi/kpi.txt" | awk '{print $NF}')
    _gpu=$(grep -m1 'hw_gpu_util_combined avg:' "benchmark-multi/kpi.txt" | awk '{print $NF}')
    _npu=$(grep -m1 'hw_npu_utilization avg:' "benchmark-multi/kpi.txt" | awk '{print $NF}')
    _pkg=$(grep -m1 'hw_pkg_power_w avg:' "benchmark-multi/kpi.txt" | awk '{print $NF}')
    _gpu_pw=$(grep -m1 'hw_gpu_power_w avg:' "benchmark-multi/kpi.txt" | awk '{print $NF}')
    _cpu_temp=$(grep -m1 'hw_cpu_temperature avg:' "benchmark-multi/kpi.txt" | awk '{print $NF}')
    _samples=$(grep -m1 'hw_sample_count:' "benchmark-multi/kpi.txt" | awk '{print $NF}')
    echo >&2
    echo "================================================================" >&2
    echo "  NSTREAMS RESULTS  (p90 window=${MAX_DURATION}s)" >&2
    echo "================================================================" >&2
    printf "  %-35s  %7s  %7s  %6s  %6s  %6s  %9s  %9s\n" \
      "Pipeline" "Streams" "FPS/s" "CPU%" "GPU%" "NPU%" "PkgPwr(W)" "GpuPwr(W)" >&2
    echo "  --------------------------------------------------------------------------" >&2
    for _i in "${!_multi_pipelines[@]}"; do
      printf "  %-35s  %7s  %7s  %6s  %6s  %6s  %9s  %9s\n" \
        "${_multi_pipelines[$_i]}" "${_multi_nstreams[$_i]}" "${_fps_avg:-N/A}" \
        "${_cpu:-N/A}" "${_gpu:-N/A}" "${_npu:-N/A}" "${_pkg:-N/A}" "${_gpu_pw:-N/A}" >&2
    done
    echo "  --------------------------------------------------------------------------" >&2
    printf "  Total FPS: %-8s  Samples: %-5s  CPU temp: %s°C\n" \
      "${_fps_cum:-N/A}" "${_samples:-N/A}" "${_cpu_temp:-N/A}" >&2
    echo "  KPI: benchmark-multi/kpi.txt" >&2
    echo "================================================================" >&2
  else
    echo "❌ FINAL RESULT: Nstreams-mode pipeline run failed." >&2
    exit 1
  fi
  exit 0
fi

# ── stream-density / --all-devices argument parsing ───────────────────────────
_density_pipelines=()
target_fps="14.95"
MAX_DURATION=60
THROUGHPUT_PERCENTILE="0.9"
lower_bound=1
upper_bound=24
ALL_DEVICES_MODE=false

_idx=1
while (( _idx <= $# )); do
  _arg="${!_idx}"
  case "$_arg" in
    -p)
      _idx=$((_idx + 1))
      while (( _idx <= $# )) && [[ "${!_idx}" != -* ]]; do
        _density_pipelines+=("${!_idx}")
        _idx=$((_idx + 1))
      done ;;
    --all-devices) ALL_DEVICES_MODE=true;         _idx=$((_idx + 1)) ;;
    --no-hw-metrics) HW_MONITOR_ENABLED=false;    _idx=$((_idx + 1)) ;;
    -l)  _idx=$((_idx + 1)); lower_bound="${!_idx}";     _idx=$((_idx + 1)) ;;
    -u)  _idx=$((_idx + 1)); upper_bound="${!_idx}";     _idx=$((_idx + 1)) ;;
    -t)  _idx=$((_idx + 1)); target_fps="${!_idx}";      _idx=$((_idx + 1)) ;;
    -i)  _idx=$((_idx + 1)); MAX_DURATION="${!_idx}";    _idx=$((_idx + 1)) ;;
    -c)  _idx=$((_idx + 1)); THROUGHPUT_PERCENTILE="${!_idx}"; _idx=$((_idx + 1)) ;;
    -m)  _idx=$((_idx + 1)); METRICS_URL="${!_idx}";     _idx=$((_idx + 1)) ;;
    -M)  _idx=$((_idx + 1)); METRICS_INTERVAL="${!_idx}"; _idx=$((_idx + 1)) ;;
    *)   _idx=$((_idx + 1)) ;;
  esac
done

if ! [[ "$lower_bound" =~ ^[0-9]+$ && "$upper_bound" =~ ^[0-9]+$ ]] ||
   [ "$lower_bound" -lt 1 ] || [ "$lower_bound" -gt "$upper_bound" ]; then
  echo "Error: Invalid stream bounds: -l=$lower_bound -u=$upper_bound (require 1 <= -l <= -u)." >&2
  usage
fi

if [ ${#_density_pipelines[@]} -eq 0 ]; then
  echo "Error: At least one -p <pipeline_name> is required." >&2
  usage
fi

# Common setup
payload_file="${SCRIPT_DIR}/benchmark_app_payload.json"
if [ ! -f "$payload_file" ]; then echo "Error: Payload file not found: $payload_file" >&2; exit 1; fi

echo ">>>>> Performing pre-flight checks..." >&2
if ! curl -s --fail "${DLSPS_BASE_URL}/pipelines/status" > /dev/null; then
  echo "Error: DLSPS not reachable at ${DLSPS_BASE_URL}" >&2; exit 1
fi
echo "DLSPS is reachable." >&2
if $HW_MONITOR_ENABLED; then
  echo "HW metrics: ${METRICS_URL}" >&2
fi

stop_all_pipelines || exit 1

# ── --all-devices mode: sequential density per pipeline + claim table ──────────
if $ALL_DEVICES_MODE; then
  # Arrays to collect per-pipeline results
  _ad_names=()
  _ad_streams=()
  _ad_fps=()
  _ad_cpu=()
  _ad_gpu=()
  _ad_npu=()
  _ad_pkg=()

  for _pl in "${_density_pipelines[@]}"; do
    echo >&2
    echo "════════════════════════════════════════════════════════════════" >&2
    echo " Benchmarking: $_pl" >&2
    echo "════════════════════════════════════════════════════════════════" >&2

    _density_search_expbisect "$_pl" "$payload_file"

    _ad_names+=("$_pl")
    _ad_streams+=("$DENSITY_RESULT_N")
    _ad_fps+=("$DENSITY_RESULT_FPS")
    _ad_cpu+=("$DENSITY_RESULT_CPU")
    _ad_gpu+=("$DENSITY_RESULT_GPU")
    _ad_npu+=("$DENSITY_RESULT_NPU")
    _ad_pkg+=("$DENSITY_RESULT_PKG")

    # Brief cooldown between pipelines so hardware thermals settle
    echo ">>>>> Cooldown 10s before next pipeline..." >&2
    sleep 10
  done

  # ── Print unified summary table ────────────
  echo >&2
  echo "================================================================" >&2
  echo "  UAV VISION ANALYTICS — SUSTAINED STREAM DENSITY RESULTS" >&2
  printf "  FPS floor : %s   Window: %ss   Percentile: p%s\n" \
    "$target_fps" "$MAX_DURATION" "$(echo "$THROUGHPUT_PERCENTILE * 100" | bc | cut -d. -f1)" >&2
  echo "================================================================" >&2
  printf "%-45s  %7s  %7s  %8s  %8s  %8s  %10s\n" \
    "Pipeline" "Streams" "FPS@N" "CPU%" "GPU%" "NPU%" "PkgPwr(W)" >&2
  echo "------------------------------------------------------------------------" >&2

  for _i in "${!_ad_names[@]}"; do
    printf "%-45s  %7s  %7s  %8s  %8s  %8s  %10s\n" \
      "${_ad_names[$_i]}" \
      "${_ad_streams[$_i]}" \
      "${_ad_fps[$_i]}" \
      "${_ad_cpu[$_i]}" \
      "${_ad_gpu[$_i]}" \
      "${_ad_npu[$_i]}" \
      "${_ad_pkg[$_i]}" >&2
  done

  echo "================================================================" >&2
  echo >&2
  echo "KPI files:" >&2
  for _i in "${!_ad_names[@]}"; do
    _dev=$(echo "${_ad_names[$_i]}" | grep -oiE 'cpu|gpu|npu' | tail -1 | tr '[:lower:]' '[:upper:]')
    [ -z "$_dev" ] && _dev="DEV$((_i+1))"
    echo "  ${_dev}: benchmark-density-${_ad_names[$_i]}/kpi.txt" >&2
  done
  exit 0
fi

# ── Single-pipeline stream-density mode ────────
pipeline_name_arg="${_density_pipelines[0]}"

echo ">>>>> Single-pipeline density search: $pipeline_name_arg" >&2
echo "      FPS floor=${target_fps}   window=${MAX_DURATION}s   max_streams=${upper_bound}" >&2

_density_search_expbisect "$pipeline_name_arg" "$payload_file"

echo >&2
echo "======================================================" >&2
if [ "${DENSITY_RESULT_N:-0}" -gt 0 ]; then
  echo "✅ FINAL RESULT: Stream-Density Benchmark Completed!" >&2
  echo "   Pipeline     : $pipeline_name_arg" >&2
  echo "   Max streams  : $DENSITY_RESULT_N" >&2
  echo "   fps/stream   : $DENSITY_RESULT_FPS" >&2
  echo "   FPS floor    : $target_fps" >&2
  if $HW_MONITOR_ENABLED; then
    echo "   CPU util     : $DENSITY_RESULT_CPU %" >&2
    echo "   GPU util     : $DENSITY_RESULT_GPU %" >&2
    echo "   NPU util     : $DENSITY_RESULT_NPU %" >&2
    echo "   Pkg power    : $DENSITY_RESULT_PKG W" >&2
  fi
  echo "======================================================" >&2
  echo >&2
  echo "stream density: $DENSITY_RESULT_N"
  echo >&2
  echo "KPIs for optimal run ($DENSITY_RESULT_N streams):"
  cat "benchmark-density-${pipeline_name_arg}/kpi.txt" 2>/dev/null
else
  echo "❌ FINAL RESULT: Target FPS ${target_fps} not achievable at N=1 stream." >&2
  echo "======================================================" >&2
  exit 1
fi
