#!/bin/bash

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

DLSPS_NODE_IP="localhost"

function get_pipeline_status() {
    curl -k -s "https://$DLSPS_NODE_IP/api/pipelines/status" "$@"
}

function check_and_loop_video() {
  local payload=$1
  local source_uri=$(echo "$payload" | jq -r '.source.uri // empty')
  
  if [ -z "$source_uri" ]; then
    return 0
  fi
  
  # Extract just the filename from the URI (handle file:// prefix and paths)
  local filename=$(basename "$source_uri")
  
  # Check if filename ends with _looped.mp4
  if [[ "$filename" =~ _looped\.mp4$ ]]; then
    # Extract base filename (remove _looped.mp4 suffix)
    local base_filename="${filename%_looped.mp4}.mp4"
    
    # Search for the base file in common video locations
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
      echo "Error: Base video file not found: $base_filename (searched in common locations)" >&2
      return 1
    fi
    
    # Determine output path (same directory as base file)
    local output_file="$(dirname "$base_file")/$filename"
    
    # Skip if looped file already exists
    if [ -f "$output_file" ]; then
      echo "Looped video already exists: $output_file" >&2
      return 0
    fi
    
    # Check if ffmpeg is available
    if ! command -v ffmpeg &> /dev/null; then
      echo "Error: ffmpeg is required to create looped video but is not installed." >&2
      return 1
    fi
    
    echo "Creating looped video: $output_file from $base_file" >&2
    
    # Create looped video with moov atom at the beginning for streaming
    # -stream_loop 10: loop the video 10 times
    # -c copy: copy codec without re-encoding
    # -movflags +faststart: move moov atom to the beginning for streaming
    ffmpeg -stream_loop 10 -i "$base_file" \
      -c copy \
      -movflags +faststart \
      "$output_file" -y 2>&1 | grep -v "frame=" >&2
    
    if [ $? -ne 0 ]; then
      echo "Error: Failed to create looped video." >&2
      return 1
    fi
    
    echo "Successfully created looped video: $output_file" >&2
  fi
  
  return 0
}

function run_pipelines() {
  local num_pipelines=$1
  local payload_data=$2
  local pipeline_name=$3

  echo >&2
  echo -n ">>>>> Initialization: Starting $num_pipelines pipeline(s) of type '$pipeline_name'..." >&2
  
  for (( x=1; x<=num_pipelines; x++ )); do

    current_payload=$payload_data

    if echo "$payload_data" | jq -e '.destination' > /dev/null; then
        current_payload=$(echo "$payload_data" | jq \
            --arg topic "object_detection_$x" \
            --arg peer_id "object_detection_$x" \
            '.destination.metadata.topic = $topic |
            .destination.frame."peer-id" = $peer_id
            '
        )
    fi

echo -e "\n\nDEBUG - Payload for stream $x:" >&2
    echo "$current_payload" | jq . >&2
    echo -e "\n" >&2

    response=$(curl -k -s -w "\nHTTP_CODE:%{http_code}" \
      "https://$DLSPS_NODE_IP/api/pipelines/user_defined_pipelines/${pipeline_name}" \
      -X POST -H "Content-Type: application/json" -d "$current_payload")
    
    http_code=$(echo "$response" | grep "HTTP_CODE:" | cut -d: -f2)
    response_body=$(echo "$response" | sed '/HTTP_CODE:/d')
    
    echo "DEBUG - HTTP Code: $http_code" >&2
    echo "DEBUG - Response: $response_body" >&2
    
    if [ "$http_code" != "200" ] && [ "$http_code" != "201" ]; then
      echo -e "\nError: Pipeline creation failed with HTTP $http_code" >&2
      echo "Response: $response_body" >&2
      return 1
    fi
    sleep 1 # Brief pause between requests
  done
    
  # Wait for all pipelines to be in RUNNING state
  echo -n ">>>>> Waiting for pipelines to initialize..." >&2
  local running_count=0
  local attempts=0
  while [ "$running_count" -lt "$num_pipelines" ] && [ "$attempts" -lt 60 ]; do
    status_output=$(get_pipeline_status)
    running_count=$(echo "$status_output" | jq '[.[] | select(.state=="RUNNING")] | length')
    
    echo -n "." >&2
    attempts=$((attempts + 1))
    sleep 2
  done
  
  if [ "$running_count" -ge "$num_pipelines" ]; then
    echo " All pipelines are running." >&2
    return 0
  else
    echo " Error: Not all pipelines entered RUNNING state." >&2
    get_pipeline_status | jq . >&2
    return 1
  fi
}

function stop_all_pipelines() {
  echo >&2
  echo ">>>>> Attempting to stop all running pipelines." >&2
  
  local pipelines_str
  pipelines_str=$(get_pipeline_status | jq -r '[.[] | select(.state=="RUNNING") | .id] | join(",")')
  
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
    curl -k -s --location -X DELETE "https://$DLSPS_NODE_IP/api/pipelines/${pipeline_id}" &
  done
  
  wait
  echo "All stop requests sent." >&2
  unset IFS

  echo -n ">>>>> Waiting for all pipelines to stop..." >&2
  local running=true
  while $running; do
    echo -n "." >&2
    local status
    status=$(get_pipeline_status | jq '.[] | .state' | grep "RUNNING")
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

function run_and_analyze_workload() {
    local num_streams=$1
    local pipeline_name_arg=$2
    local payload_file=$3

    # NOTE: To convert to a full orchestrator, add 'docker compose up' here.
    rm -rf "benchmark-$num_streams" && mkdir -p "benchmark-$num_streams"

    local payload_body
    payload_body=$(jq -r --arg name "$pipeline_name_arg" '.[] | select(.pipeline == $name) | .payload' "$payload_file")

    if [ -z "$payload_body" ]; then
        echo "Error: Pipeline '$pipeline_name_arg' not found in $payload_file" >&2
        return 1
    fi

    # Check and create looped video if needed (only once per payload)
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

    echo ">>>>> Monitoring FPS for $MAX_DURATION seconds..." >&2
    local start_time=$SECONDS
    while (( SECONDS - start_time < MAX_DURATION )); do
        local elapsed_time=$((SECONDS - start_time))
        echo -ne "Monitoring... ${elapsed_time}s / ${MAX_DURATION}s\r" >&2
        get_pipeline_status >> "benchmark-$num_streams/sample.logs" 2>/dev/null
        sleep 1
    done
    echo -ne "\n" >&2

    stop_all_pipelines

    # NOTE: To convert to a full orchestrator, add 'docker compose down' here.
    gawk -v ns=$num_streams -v percentile=${THROUGHPUT_PERCENTILE:-0.9} "$awk_utils"'
    /^\[/ {
      split("",fps_running)
      ns_running=0
    }
    /"avg_fps":/ {
      fps=$2*1
    }
    /"state": "RUNNING"/ {
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
}

run_workload_with_retries () {
  local num_streams=$1
  local pipeline_name_arg=$2
  local payload_file=$3
  local throughput=0
  local throughput_max=0
  local retry_ct=0
  while [ $retry_ct -lt ${RETRY_TIMES:-1} ]; do
    echo "Invoking workload with $num_streams streams...try#$retry_ct" >&2
    if run_and_analyze_workload "$num_streams" "$pipeline_name_arg" "$payload_file" >/dev/null 2>&1; then
      sed "s|^|stream-density#$num_streams: |" "benchmark-$num_streams/kpi.txt" >&2
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

# --- Main Script ---

function usage() {
    echo "Usage: $0 -p <pipeline_name> -l <lower_bound> -u <upper_bound> [-t <target_fps>] [-i <interval>] [-c <throughput_percentile>]"
    echo
    echo "Arguments:"
    echo "  -p <pipeline_name>   : (Required) The name of the pipeline to benchmark (e.g., object_tracking_cpu)."
    echo "  -l <lower_bound>     : (Required) The starting lower bound for the number of streams."
    echo "  -u <upper_bound>     : (Required) The starting upper bound for the number of streams."
    echo "  -t <target_fps>      : Target FPS for stream-density mode (default: 14.95)."
    echo "  -i <interval>        : Monitoring duration in seconds for each test run (default: 60)."
    echo "  -c <throughput_percentile> : Throughput percentile for KPI calculation (default: 0.9)."
    exit 1
}

pipeline_name_arg=""
target_fps="14.95"
MAX_DURATION=60
THROUGHPUT_PERCENTILE="0.9"
lower_bound=""
upper_bound=""

while getopts "p:l:u:t:i:c:" opt; do
  case ${opt} in
    p ) pipeline_name_arg=$OPTARG ;;
    l ) lower_bound=$OPTARG ;;
    u ) upper_bound=$OPTARG ;;
    t ) target_fps=$OPTARG ;;
    i ) MAX_DURATION=$OPTARG ;;
    c ) THROUGHPUT_PERCENTILE=$OPTARG ;;
    \? ) usage ;;
  esac
done

if [ -z "$pipeline_name_arg" ] || [ -z "$lower_bound" ] || [ -z "$upper_bound" ]; then
    echo "Error: Pipeline name, lower bound, and upper bound are required." >&2
    usage
fi

# Path to the .env file
ENV_FILE="./.env"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found."
    exit 1
fi

# Extract SAMPLE_APP variable from .env file
SAMPLE_APP=$(grep -E "^SAMPLE_APP=" "$ENV_FILE" | cut -d '=' -f2 | tr -d '"' | tr -d "'")

# Check if SAMPLE_APP variable exists
if [ -z "$SAMPLE_APP" ]; then
    echo "Error: SAMPLE_APP variable not found in .env file." >&2
    exit 1
fi

payload_file="./${SAMPLE_APP}/benchmark_app_payload.json"

if [ ! -f "$payload_file" ]; then
    echo "Error: Benchmark payload file not found: $payload_file" >&2
    exit 1
fi

echo ">>>>> Performing pre-flight checks..." >&2
if ! curl -k -s --fail "https://$DLSPS_NODE_IP/api/pipelines/status" > /dev/null; then
    echo "Error: DL Streamer Pipeline Server is not running or not reachable at https://$DLSPS_NODE_IP" >&2
    exit 1
fi
echo "DLSPS is reachable." >&2

stop_all_pipelines
if [ $? -ne 0 ]; then
   exit 1
fi

records=""
ns=$lower_bound
tns=0
lns=$lower_bound
uns=$upper_bound

[[ "$@" = *"--trace"* && $lns -lt $uns ]] || echo "Start-Trace:"
while [ $((uns - lns)) -gt 1 ] || [[ "$records" != *" $lns:"* ]] || [[ "$records" != *" $uns:"* ]]; do
  if [[ "$records" = *" $ns:"* ]]; then
    throughput=${records##* $ns:}
    throughput=${throughput%% *}
  else
    throughput=$(run_workload_with_retries "$ns" "$pipeline_name_arg" "$payload_file")
  fi
  records="$records $ns:$throughput"

  echo "streams: $ns throughput: $throughput range: [$lns,$uns]"

  if echo "${throughput:-0} $target_fps" | gawk '{exit($1<$2?0:1)}'; then
    uns=$ns
    ns=$(echo "$lns $ns" | gawk '{n=int(($1+$2)/2);m=int($2/2);n=(n<m?m:n);print (n<1?1:n)}')
  else
    [ $ns -le $tns ] || tns=$ns
    lns=$ns
    ns=$(echo "$ns $uns" | gawk '{n=int(($1+$2)/2+0.5);m=$1*2;print (n>m?m:n)}')
  fi
done
tns=$lns

if [[ "$@" = *"--trace"* && $lns -lt $uns ]]; then
  echo "Start-Trace:"
  throughput=$(run_workload_with_retries "$tns" "$pipeline_name_arg" "$payload_file")
fi
echo "Stop-Trace:"

echo
echo "======================================================" >&2
if [ "$tns" -gt 0 ]; then
    echo "✅ FINAL RESULT: Stream-Density Benchmark Completed!" >&2
    # The primary result goes to stdout
    echo "stream density: $tns"
    echo "======================================================" >&2
    echo >&2
    echo "KPIs for the optimal configuration ($tns streams):" >&2
    # The KPI details go to stdout
    cat "benchmark-$tns/kpi.txt" 2> /dev/null
else
    echo "❌ FINAL RESULT: Target FPS Not Achievable in the given range." >&2
    echo "======================================================" >&2
fi
