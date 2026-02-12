#!/bin/bash
# This script is used to get status of all/specific pipeline instances in the dlstreamer-pipeline-server
# ------------------------------------------------------------------
# 1. Based on argument, get status of all or specific pipeline instance(s)
# ------------------------------------------------------------------

# Default values
SCRIPT_DIR=$(dirname $(readlink -f "$0"))
PIPELINE_ROOT="user_defined_pipelines" # Default root directory for pipelines
DEPLOYMENT_TYPE=""                     # Default deployment type (empty for existing flow)
CONFIG_FILE=$SCRIPT_DIR/config.yml     # Config file path for multiple instances

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


get_status_instance() {
    local instance_id="$1"
    echo "Getting status of pipeline instance with ID: $instance_id"
    # Use curl to get the status of the pipeline instance
    response=$(curl -s -k -w "\n%{http_code}" https://$CURL_HOST_IP/api/pipelines/$instance_id/status)

    # Split response and status
    body=$(echo "$response" | sed '$d')
    status=$(echo "$response" | tail -n1)

    if [[ "$status" -ne 200 ]]; then
        err "Failed to get status of pipeline instance with ID '$instance_id'. HTTP Status Code: $status"
        echo "Response body: $body"
        exit 0
    else
        echo "Response body: $body"
    fi
}


get_status_all() {
    init
    response=$(curl -s -k -w "\n%{http_code}" https://$CURL_HOST_IP/api/pipelines/status)
    # Split response and status
    body=$(echo "$response" | sed '$d')
    status=$(echo "$response" | tail -n1)
    if [[ "$status" -ne 200 ]]; then
        err "Failed to get status of dlstreamer-pipeline-server. HTTP Status Code: $status"
        exit 1
    else
        echo "$body"
    fi
}

# Function to get status based on flags
get_status_flag() {
    if [[ -f "$CONFIG_FILE" && -n "$INSTANCE_NAME" ]]; then
        get_sample_app
        ENV_PATH="$SCRIPT_DIR/temp_apps/$SAMPLE_APP/$INSTANCE_NAME/.env"
        # If instance_id is set, loop through each id and call get_status_instance
        if [[ -n "$INSTANCE_ID" ]]; then
            init
            for id in $INSTANCE_ID; do
                get_status_instance "$id"
            done
        else
            get_status_all
        fi
        return
    # else if INSTANCE_NAME is not set, but INSTANCE_ID is set
    elif [[ -n "$INSTANCE_ID" ]]; then
        ENV_PATH="$SCRIPT_DIR/.env"
        init
        for id in $INSTANCE_ID; do
            get_status_instance "$id"
        done
        return
    # else if neither INSTANCE_NAME nor INSTANCE_ID is set
    else
        # check if config.yml exists
        if [[ -f "$CONFIG_FILE" ]]; then
            echo "Config file found. Fetching status for all instances defined in $CONFIG_FILE"
            while IFS='|' read -r sample_app instance_name; do
                ENV_PATH="$SCRIPT_DIR/temp_apps/$sample_app/$instance_name/.env"
                echo "Processing instance: $instance_name from sample app: $sample_app"
                get_status_all
            done < <(parse_config_yml)
        else
            ENV_PATH="$SCRIPT_DIR/.env"
            get_status_all
        fi
    fi
}


err() {
    echo "ERROR: $*" >&2
}

usage() {
    echo "Usage: $0 [helm] [--all] [ -i | --id <instance_id> ] [-h | --help]"
    echo "Arguments:"
    echo "  helm                            For Helm deployment (adds :30443 port to HOST_IP for curl commands)"
    echo "Options:"
    echo "  --all                           Get status of all pipelines instances (default)"
    echo "  -i, --instance <instance_name>  Get status of pipeline instance(s) for a specified INSTANCE_NAME from config.yml"
    echo "  -i, --id <instance_id>          Get status of a specified pipeline instance(s)"
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

    # If no arguments provided, fetch status of all pipeline instances depending whether config.yml is present
    # If config.yml is present, fetch status of all instances defined in it where ENV_PATH=SCRIPT_DIR/temp_apps/SAMPLE_APP/INSTANCE_NAME/.env
    # else fetch status where ENV_PATH=SCRIPT_DIR/.env
    if [[ -z "$1" ]]; then
        echo "No arguments provided. Fetching status for all pipeline instances."
        get_status_flag
        exit 0
    fi
    # Variable to store instance name
    instance_name=""
    # Variable to store instance IDs
    instance_ids=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
        --all)
            echo "Fetching status for all pipeline instances"
            get_status_flag
            exit 0
            ;;
        -i | --instance)
            shift
            if [[ -z "$1" ]]; then
                err "-i/--instance requires a non-empty argument."
                usage
                exit 1
            fi
            instance_name="$1"
            shift
            ;;
        --id)
            shift
            if [[ -z "$1" ]]; then
                err "--id requires a non-empty argument."
                usage
                exit 1
            fi
            # Collect all instance IDs
            while [[ -n "$1" ]] && [[ "$1" != -* ]]; do
                instance_ids+=("$1")
                shift
            done
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

# Set INSTANCE_NAME and INSTANCE_ID for get_status_flag
INSTANCE_NAME="$instance_name"
# Convert array to space-separated string
if [[ ${#instance_ids[@]} -gt 0 ]]; then
    INSTANCE_ID="${instance_ids[*]}"
fi

get_status_flag
}

main "$@"