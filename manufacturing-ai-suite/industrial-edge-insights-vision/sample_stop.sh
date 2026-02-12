#!/bin/bash
# This script is used to stop pipeline instances in the dlstreamer-pipeline-server
# ------------------------------------------------------------------
# 1. Check if DLSPS server is reachable- status API
# 2. Based on argument, stop all or specific pipeline instance
# ------------------------------------------------------------------

# Default values
SCRIPT_DIR=$(dirname $(readlink -f "$0"))
PIPELINE_ROOT="user_defined_pipelines" # Default root directory for pipelines
PIPELINE="all"                         # Default to running all pipelines
DEPLOYMENT_TYPE=""                     # Default deployment type (empty for existing flow)
CONFIG_FILE="$SCRIPT_DIR/config.yml"   # Config file path (For multiple instances)

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

    # Set the appropriate HOST_IP with port for curl commands based on deployment type and config file presence 
    if [[ -f "$CONFIG_FILE" ]]; then
        if [[ "$DEPLOYMENT_TYPE" == "helm" ]]; then
            CURL_HOST_IP="${HOST_IP}:$NGINX_HTTPS_PORT"
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


delete_pipeline_instance() {
    local instance_id="$1"
    echo "Stopping pipeline instance with ID: $instance_id"
    # Use curl to delete the pipeline instance
    response=$(curl -s -k -w "\n%{http_code}" -X DELETE https://$CURL_HOST_IP/api/pipelines/$instance_id)

    # Split response and status
    body=$(echo "$response" | sed '$d')
    status=$(echo "$response" | tail -n1)

    if [[ "$status" -ne 200 ]]; then
        err "Failed to stop pipeline instance with ID '$instance_id'. HTTP Status Code: $status"
        echo "Response body: $body"
        exit 1
    else
        echo "Pipeline instance with ID '$instance_id' stopped successfully. Response: $body"
    fi
}

stop_pipeline_instances() {
    # get instance_ids
    response=$(curl -s -k -w "\n%{http_code}" https://$CURL_HOST_IP/api/pipelines/status)
    # Split response and status
    body=$(echo "$response" | sed '$d')
    status=$(echo "$response" | tail -n1)

    # Check if the status is 200 OK
    if [[ "$status" -ne 200 ]]; then
        err "Failed to get instance list. HTTP Status Code: $status"
        exit 1
    else
        echo "Instance list fetched successfully. HTTP Status Code: $status"

        instance_count=$(echo "$body" | jq '[.[] | select(.state == "RUNNING")] | length')
        if [[ "$instance_count" -eq 0 ]]; then
            echo "No running pipeline instances found."
            exit 0
        else
            echo "Found $instance_count running pipeline instances."
            echo "$body" | jq -r '.[] | select(.state == "RUNNING") | .id' | while read -r running_instances; do
                # Loop through all instances and get the IDs of running instances
                delete_pipeline_instance "$running_instances"
            done
        fi
    fi
}

stop_pipelines() {
    if [[ -f "$CONFIG_FILE" && -n "$INSTANCE_NAME" ]]; then
        # if config.yml exists and INSTANCE_NAME is set
        get_sample_app
        # if deployment type is helm or default and set ENV_PATH accordingly
        if [[ "$DEPLOYMENT_TYPE" == "helm" ]]; then
            ENV_PATH="$SCRIPT_DIR/helm/temp_apps/$SAMPLE_APP/$INSTANCE_NAME/.env"
        else                
            ENV_PATH="$SCRIPT_DIR/temp_apps/$SAMPLE_APP/$INSTANCE_NAME/.env"
        fi
        init
        # check if dlstreamer-pipeline-server is running
        get_status
        
        # If specific INSTANCE_ID provided, stop only that one; otherwise stop all
        if [[ -n "$INSTANCE_ID" ]]; then
            delete_pipeline_instance "$INSTANCE_ID"
        else
            stop_pipeline_instances
        fi
        return
    
    elif [[ -f "$CONFIG_FILE" && -z "$INSTANCE_NAME" ]]; then
        # if config.yml exists and INSTANCE_NAME is NOT set
        while IFS='|' read -r sample_app instance_name; do
            echo ""
            echo "-------------------------------------------"
            echo "Processing instance: $instance_name (SAMPLE_APP: $sample_app)"
            echo "-------------------------------------------"
            
            if [[ "$DEPLOYMENT_TYPE" == "helm" ]]; then
                ENV_PATH="$SCRIPT_DIR/helm/temp_apps/$sample_app/$instance_name/.env"
            else
                ENV_PATH="$SCRIPT_DIR/temp_apps/$sample_app/$instance_name/.env"
            fi
            init  
            # check if dlstreamer-pipeline-server is running
            get_status
            # load the payload
            stop_pipeline_instances "$@"

        done < <(parse_config_yml)
        return

    # if config.yml does not exist
    # load .env from SCRIPT_DIR
    else
        ENV_PATH="$SCRIPT_DIR/.env"
        init
        # check if dlstreamer-pipeline-server is running
        get_status
        # If specific INSTANCE_ID provided, stop only that one; otherwise stop all
        if [[ -n "$INSTANCE_ID" ]]; then
            delete_pipeline_instance "$INSTANCE_ID"
        else
            stop_pipeline_instances
        fi
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
    echo "Usage: $0 [helm] [OPTIONS]"
    echo ""
    echo "Arguments:"
    echo "  helm                                      Use Helm deployment (adds :30443 port to HOST_IP)"
    echo ""
    echo "Options:"
    echo "  (no options)                              Stop all pipeline instances (default)"
    echo "  --all                                     Stop all pipeline instances"
    echo "  -i <instance_name|pipeline_id>            Stop by instance name (from config.yml) or pipeline ID"
    echo "  --instance <instance_name>                Stop all pipelines for given instance"
    echo "  -i <instance_name> --id <pipeline_id>     Stop specific pipeline ID on instance"
    echo "  --instance <instance_name> --id <id>      Stop specific pipeline ID on instance"
    echo "  --id <pipeline_id>                        Stop specific pipeline by ID"
    echo "  -h, --help                                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                        # Stop all instances"
    echo "  $0 -i pdd1                                # Stop all pipelines for pdd1 instance"
    echo "  $0 -i pdd1 --id abc-123                   # Stop pipeline abc-123 on pdd1"
    echo "  $0 --id abc-123                           # Stop pipeline abc-123 directly"
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

    # If no arguments provided, stop all pipeline instances
    if [[ -z "$1" ]]; then
        echo "No pipelines specified. Stopping all pipeline instances"
        stop_pipelines
        return
    fi

    # Parse arguments to determine instance_name and instance_id 
    # If both are empty, then stop all instances
    
    instance_name=""
    instance_id=""
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
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
                instance_id="$1"
                shift
                ;;
            --all)
                # Explicitly request stopping all instances
                instance_name=""
                instance_id=""
                shift
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
    # Set INSTANCE_NAME and INSTANCE_ID based on parsed values
    INSTANCE_NAME="$instance_name"
    INSTANCE_ID="$instance_id"
    stop_pipelines
}

main "$@"