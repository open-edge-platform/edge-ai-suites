#!/bin/bash
# This script is used to start pipelines in the dlstreamer-pipeline-server
# ------------------------------------------------------------------
# 1. Check if DLSPS server is reachable- status API
# 2. Check if payload.json(json array) exists
# 	a. If yes, loads them as a json array, as pipeline, payloads map
# 3. Based on argument, start all or pipeline(s)
# 	a. starting a pipeline
# 		i. fetch the payload(s) from the loaded pipeline-payload map
#         ii. call POST command to DLSPS with this payload
# ------------------------------------------------------------------

# Default values
SCRIPT_DIR=$(dirname $(readlink -f "$0"))
PIPELINE_ROOT="user_defined_pipelines" # Default root directory for pipelines
PIPELINE="all"                         # Default to running all pipelines
PAYLOAD_COPIES=1                       # Default to running a single copy of the payloads
DEPLOYMENT_TYPE=""                     # Default deployment type (empty for existing flow)
CONFIG_FILE="$SCRIPT_DIR/config.yml"   # Config file path for multiple instances

init() {
    # load environment variables from .env file if it exists
    if [[ -f "$ENV_PATH" ]]; then
        export $(grep -v -E '^\s*#' "$ENV_PATH" | sed -e 's/#.*$//' -e '/^\s*$/d' | xargs)
        echo "Environment variables loaded from $ENV_PATH"
    else
        err "No .env file found in $ENV_PATH"
        exit 1
    fi

    # check if SAMPLE_APP is set
    if [[ -z "$SAMPLE_APP" ]]; then
        err "SAMPLE_APP environment variable is not set."
        exit 1
    else
        echo "Running sample app: $SAMPLE_APP"
    fi
    # check if APP_DIR directory exists
    if [[ ! -d "$APP_DIR" ]]; then
        err "APP_DIR directory $APP_DIR does not exist."
        exit 1
    fi

    # Set the appropriate HOST_IP with port for curl commands based on deployment type
    # IF config.yml file exists, then set CURL_HOST_IP as HOST_IP:NGINX_HTTPS_PORT otherwise set CURL_HOST_IP as HOST_IP:30443 for helm deployment and HOST_IP for default 
    if [[ -f "$CONFIG_FILE" ]]; then
        if [[ "$DEPLOYMENT_TYPE" == "helm" ]]; then
            CURL_HOST_IP="${HOST_IP}:30443"
            echo "Using Helm deployment - curl commands will use: $CURL_HOST_IP"
        else
            CURL_HOST_IP="$HOST_IP:$NGINX_HTTPS_PORT"
            echo "Using default deployment - curl commands will use: $CURL_HOST_IP"
        fi
    else
        if [[ "$DEPLOYMENT_TYPE" == "helm" ]]; then
            CURL_HOST_IP="${HOST_IP}:30443"
            echo "Using Helm deployment - curl commands will use: $CURL_HOST_IP"
        else
            CURL_HOST_IP="$HOST_IP"
            echo "Using default deployment - curl commands will use: $CURL_HOST_IP"
        fi
    fi
}

# Function to parse config.yml and extract SAMPLE_APP, INSTANCE_NAME, and their key-value pairs
parse_config_yml() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        err "Config file $CONFIG_FILE not found."
        exit 1
    fi
    
    awk '
    BEGIN { 
        sample_app = ""
        instance_name = ""
    }
    /^[[:space:]]*$/ { next }
    /^[[:space:]]*#/ { next }
    
    /^[a-zA-Z_][a-zA-Z0-9_-]*:/ {
        sample_app = $1
        gsub(/:/, "", sample_app)
        next
    }
    
    /^  [a-zA-Z_][a-zA-Z0-9_-]*:/ {
        instance_name = $1
        gsub(/^[[:space:]]+/, "", instance_name)
        gsub(/:/, "", instance_name)
        if (sample_app != "" && instance_name != "") {
            print sample_app "|" instance_name
        }
    }
    ' "$CONFIG_FILE"
}

# Function to get SAMPLE_APP for a given INSTANCE_NAME from config.yml
get_sample_app() {
    if [[ -z "$INSTANCE_NAME" ]]; then
        err "INSTANCE_NAME not set"
        exit 1
    fi
    
    SAMPLE_APP=$(awk -v inst="$INSTANCE_NAME" '
    BEGIN { 
        sample_app = ""
        found = 0
    }
    /^[[:space:]]*$/ { next }
    /^[[:space:]]*#/ { next }
    
    /^[a-zA-Z_][a-zA-Z0-9_-]*:/ {
        sample_app = $1
        gsub(/:/, "", sample_app)
        next
    }
    
    /^  [a-zA-Z_][a-zA-Z0-9_-]*:/ {
        instance_name = $1
        gsub(/^[[:space:]]+/, "", instance_name)
        gsub(/:/, "", instance_name)
        if (instance_name == inst) {
            print sample_app
            found = 1
            exit
        }
    }
    
    END {
        if (!found) {
            exit 1
        }
    }
    ' "$CONFIG_FILE")
    
    if [[ $? -ne 0 || -z "$SAMPLE_APP" ]]; then
        err "INSTANCE_NAME '$INSTANCE_NAME' not found in $CONFIG_FILE"
        exit 1
    fi
    
    echo "Found SAMPLE_APP: $SAMPLE_APP for INSTANCE_NAME: $INSTANCE_NAME"
}


load_payload() {
    # Load all pipelines payload
    if [[ -n "$CUSTOM_PAYLOAD" ]]; then
        PAYLOAD_FILE="$CUSTOM_PAYLOAD"
    else
        PAYLOAD_FILE="$APP_DIR/payload.json"
    fi

    if [[ -f "$PAYLOAD_FILE" ]]; then
        echo "Loading payload from $PAYLOAD_FILE"
        if command -v jq &>/dev/null; then
            PAYLOAD=$(jq '.' "$PAYLOAD_FILE")
            # find the list of pipelines in the payload
            ALL_PIPELINES_IN_PAYLOAD=$(echo "$PAYLOAD" | jq 'group_by(.pipeline) | map({pipeline: .[0].pipeline, payloads: map(.payload)})')
            echo "Payload loaded successfully."
        else
            err "jq is not installed. Cannot parse JSON payload."
            exit 1
        fi
    else
        err "No payload file found at $PAYLOAD_FILE"
        exit 1
    fi
}

post_payload() {
    local PIPELINE="$1"
    local PAYLOAD="$2"
    # Post the payload to the REST server
    echo "Posting payload to REST server at https://$CURL_HOST_IP/api/pipelines/$PIPELINE_ROOT/$PIPELINE"
    # Use curl to post the payload
    response=$(curl -s -k -w "\n%{http_code}" https://$CURL_HOST_IP/api/pipelines/$PIPELINE_ROOT/$PIPELINE -X POST -H "Content-Type: application/json" -d "$PAYLOAD")

    # Split response and status
    body=$(echo "$response" | sed '$d')
    status=$(echo "$response" | tail -n1)
    if [[ "$status" -ne 200 ]]; then
        err "Failed to post payload for pipeline '$PIPELINE'. HTTP Status Code: $status"
        echo "Response body: $body"
        exit 1
    else
        echo "Payload for pipeline '$PIPELINE' posted successfully. Response: $body"
    fi
}

launch_pipeline() {
    # Function to fetch payload for a specific pipeline and post it.
    # If the pipeline has multiple payloads, it will post each one.
    # If PAYLOAD_COPIES is set, it will create copies of every payload and
    # increment the rtsp path or peer-id in the copied payload.
    local PIPELINE="$1"
    echo "Launching pipeline: $PIPELINE"
    # Extract the payload for the specific pipeline
    echo "Extracting payload for pipeline: $PIPELINE"

    # check if there are any payloads for the pipeline
    payload_count=$(echo "$ALL_PIPELINES_IN_PAYLOAD" | jq --arg name "$PIPELINE" '[.[] | select(.pipeline == $name) | .payloads[]] | length')

    if [[ "$payload_count" -eq 0 ]]; then
        err "No payloads found for pipeline: $PIPELINE"
        exit 1
    else
        echo "Found $payload_count payload(s) for pipeline: $PIPELINE"
        # fetch payloads for the pipeline and run each
        echo "$ALL_PIPELINES_IN_PAYLOAD" | jq -c --arg PIPELINE "$PIPELINE" '.[] | select(.pipeline == $PIPELINE) | .payloads[]' | while read -r payload; do
            # Use jq to format the payload
            echo "Payload for pipeline '$PIPELINE' $payload"
            # If PAYLOAD_COPIES is set, increment the rtsp path or peer-id in the payload those number of times
            if [[ -n "$PAYLOAD_COPIES" && "$PAYLOAD_COPIES" -gt 1 ]]; then
                echo "Running $PAYLOAD_COPIES copies of the payloads for pipeline '$PIPELINE'."
                for i in $(seq 0 $((PAYLOAD_COPIES - 1))); do
                    # Increment the frame path or peer-id in the payload
                    modified_payload=$(echo "$payload" | jq --arg i "$i" 'if .destination.frame.path then .destination.frame.path += $i elif .destination.frame["peer-id"] then .destination.frame["peer-id"] += $i else . end')
                    echo "Posting modified payload for pipeline '$PIPELINE': $modified_payload"
                    post_payload "$PIPELINE" "$modified_payload"
                done
            else
                post_payload "$PIPELINE" "$payload"
            fi
        done
    fi

}

# Function to launch pipelines based on arguments
launch_pipelines_from_args() {
    # If no arguments are provided, start only the first pipeline
    if [[ -z "$1" ]]; then
        first_pipeline=$(echo "$ALL_PIPELINES_IN_PAYLOAD" | jq -r '.[0].pipeline')
        echo "Starting first pipeline: $first_pipeline"
        launch_pipeline "$first_pipeline"
        return
    fi
    # Expect other arguments to be pipeline names
    # If the next argument is not an option (doesn't start with - or --), start all the subsequent arg as pipelines
    while [[ $# -gt 0 && "$1" != "--" ]]; do
        if [[ -n "$1" && ! "$1" =~ ^- ]]; then
            echo "Starting pipeline: $1"
            launch_pipeline "$1"
            # check for a id as response from POST curl with a timeout
            shift
        else
            err "Invalid argument '$1'. Expected a pipeline name."
            usage
            exit 1
        fi
    done
}

start_pipelines() {
    # initialize the sample app, load env
    # if config.yml exists and INSTANCE_NAME is set
    if [[ -f "$CONFIG_FILE" && -n "$INSTANCE_NAME" ]]; then
        get_sample_app
        ENV_PATH="$SCRIPT_DIR/temp_apps/$SAMPLE_APP/$INSTANCE_NAME/.env"
        init
        # check if dlstreamer-pipeline-server is running
        get_status
        # load the payload
        load_payload
        # Launch pipelines based on arguments
        launch_pipelines_from_args "$@"
        return

    # if config.yml exists and INSTANCE_NAME is not set
    # Process all instances from config.yml
    elif [[ -f "$CONFIG_FILE" && -z "$INSTANCE_NAME" ]]; then
        while IFS='|' read -r sample_app instance_name; do
            echo ""
            echo "------------------------------------------"
            echo "Processing instance: $instance_name from SAMPLE_APP: $sample_app"
            echo "------------------------------------------"
            
            ENV_PATH="$SCRIPT_DIR/temp_apps/$sample_app/$instance_name/.env"
            init
            # check if dlstreamer-pipeline-server is running
            get_status
            # load the payload
            load_payload
            # Launch pipelines based on arguments
            launch_pipelines_from_args "$@"
        done < <(parse_config_yml)
        return

    # if config.yml does not exist 
    # load .env from SCRIPT_DIR
    else
        ENV_PATH="$SCRIPT_DIR/.env"
        init
        # check if dlstreamer-pipeline-server is running
        get_status
        # load the payload
        load_payload
        # Launch pipelines based on arguments
        launch_pipelines_from_args "$@"
    fi
}

get_status() {
    response=$(curl -s -k -w "\n%{http_code}" https://$CURL_HOST_IP/api/pipelines/status)
    # Split response and status
    body=$(echo "$response" | sed '$d')
    status=$(echo "$response" | tail -n1)
    # Check if the status is 200 OK
    echo "Checking status of dlstreamer-pipeline-server..."
    if [[ "$status" -ne 200 ]]; then
        err "Failed to get status of dlstreamer-pipeline-server. HTTP Status Code: $status"
        exit 1
    else
        echo "Server reachable. HTTP Status Code: $status"
    fi
}

err() {
    echo "ERROR: $*" >&2
}

usage() {
    echo "Usage: $0 [helm] [--all] [-p | --pipeline <pipeline_name>] [ -n | --payload-copies ] [-h | --help]"
    echo "Arguments:"
    echo "  helm                            For Helm deployment (adds :30443 port to HOST_IP for curl commands)"
    echo "Options:"
    echo "  -i, --instance <instance_name>  Specify the instance name to use"
    echo "  --all                           Run all pipelines in the config (Default)"
    echo "  -p, --pipeline <pipeline_name>  Specify the pipeline to run"
    echo "  -n, --payload-copies            Run copies of the payloads for pipeline(s)."
    echo "                                  Any frame rtsp path or webrtc peer-id in payload will be incremented."
    echo "  -h, --help                      Show this help message"
}

main() {

    # Check for helm argument first and set DEPLOYMENT_TYPE
    args=("$@")
    for i in "${!args[@]}"; do
        if [[ "${args[i]}" == "helm" ]]; then
            DEPLOYMENT_TYPE="helm"
            # Remove helm from the args array
            unset 'args[i]'
            break
        fi
    done

    # Reconstruct the arguments from the modified array (removing empty elements)
    filtered_args=()
    for arg in "${args[@]}"; do
        [[ -n "$arg" ]] && filtered_args+=("$arg")
    done
    set -- "${filtered_args[@]}"

    # Check for -n in arg list and set PAYLOAD_COPIES, then remove it from args
    args=("$@")
    for i in "${!args[@]}"; do
        if [[ "${args[i]}" == "-n" || "${args[i]}" == "--payload-copies" ]]; then
            # If -n is found, check if the next argument is provided and not empty
            if [[ -z "${args[((i + 1))]}" ]]; then
                err "--payload-copies requires a non-empty argument."
                usage
                exit 1
            else
                PAYLOAD_COPIES="${args[((i + 1))]}"
                echo "Running $PAYLOAD_COPIES copies of the payloads."
                # Remove -n and the next argument from the args array
                unset 'args[i]'
                unset 'args[i+1]'
                break
            fi
        fi
    done

    # Reconstruct the arguments from the modified array
    set -- "${args[@]}"

    # no arguments provided, start only the first pipeline
    if [[ -z "$1" ]]; then
        echo "No pipeline specified. Starting the first pipeline."
        start_pipelines
        return
    fi

    # Parse remaining arguments for various scenarios
    # Handle -i/--instance, --payload, --all, -p/--pipeline combinations
    
    CUSTOM_PAYLOAD=""
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -i | --instance)
                shift
                if [[ -z "$1" || "$1" =~ ^- ]]; then
                    err "--instance requires a non-empty argument."
                    usage
                    exit 1
                fi
                INSTANCE_NAME="$1"
                echo "Instance name set to: $INSTANCE_NAME"
                shift
                ;;
            --payload)
                shift
                if [[ -z "$1" || "$1" =~ ^- ]]; then
                    err "--payload requires a file path argument."
                    usage
                    exit 1
                fi
                CUSTOM_PAYLOAD="$1"
                if [[ ! -f "$CUSTOM_PAYLOAD" ]]; then
                    err "Payload file not found: $CUSTOM_PAYLOAD"
                    exit 1
                fi
                echo "Custom payload file set to: $CUSTOM_PAYLOAD"
                shift
                ;;
            --all)
                echo "Starting all pipelines..."
                start_pipelines
                exit 0
                ;;
            -p | --pipeline)
                shift
                if [[ -z "$1" || "$1" =~ ^- ]]; then
                    err "--pipeline requires at least one pipeline name."
                    usage
                    exit 1
                fi
                # Collect all pipeline names until another option is hit or its the end
                pipelines=()
                while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do
                    pipelines+=("$1")
                    shift
                done
                echo "Starting specified pipeline(s)..."
                start_pipelines "${pipelines[@]}"
                exit 0
                ;;
            -h | --help)
                usage
                exit 0
                ;;
            *)
                err "Invalid option '$1'."
                usage
                exit 1
                ;;
        esac
    done
    start_pipelines
}

main "$@"