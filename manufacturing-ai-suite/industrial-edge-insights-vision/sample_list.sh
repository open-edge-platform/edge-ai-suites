#!/bin/bash
# This script is used to list all loaded pipelines in the dlstreamer-pipeline-server
# ------------------------------------------------------------------
# 1. Check if DLSPS server is reachable- status API
# 2. List all loaded pipelines
# ------------------------------------------------------------------

# Default values
SCRIPT_DIR=$(dirname $(readlink -f "$0"))
PIPELINE_ROOT="user_defined_pipelines" # Default root directory for pipelines
PIPELINE="all"                         # Default to running all pipelines
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

list_pipelines() {
    if [[ -f "$CONFIG_FILE" && -n "$INSTANCE_NAME" ]]; then
        get_sample_app
        # if deployment type is helm, then set ENV_PATH as SCRIPT_DIR/helm/temp_apps/SAMPLE_APP/INSTANCE_NAME/.env
        if [[ "$DEPLOYMENT_TYPE" == "helm" ]]; then
            ENV_PATH="$SCRIPT_DIR/helm/temp_apps/$SAMPLE_APP/$INSTANCE_NAME/.env"
        else
            ENV_PATH="$SCRIPT_DIR/temp_apps/$SAMPLE_APP/$INSTANCE_NAME/.env"
        fi
        init
        # check if dlstreamer-pipeline-server is running
        get_status
        # get the loaded pipelines
        get_loaded_pipelines
        return

    # if config.yml exists and INSTANCE_NAME is not set
    # Process all instances from config.yml
    elif [[ -f "$CONFIG_FILE" && -z "$INSTANCE_NAME" ]]; then
        while IFS='|' read -r sample_app instance_name; do
            echo ""
            echo "-------------------------------------------"
            echo "Status of: $instance_name (SAMPLE_APP: $sample_app)"
            echo "-------------------------------------------"
            
            if [[ "$DEPLOYMENT_TYPE" == "helm" ]]; then
                ENV_PATH="$SCRIPT_DIR/helm/temp_apps/$sample_app/$instance_name/.env"
            else
                ENV_PATH="$SCRIPT_DIR/temp_apps/$sample_app/$instance_name/.env"
            fi
            init
            
            # check if dlstreamer-pipeline-server is running
            get_status
            # get the loaded pipelines
            get_loaded_pipelines
            
        done < <(parse_config_yml)
        return
    # if config.yml does not exist
    # load .env from SCRIPT_DIR
    else
        ENV_PATH="$SCRIPT_DIR/.env"
        init
        # check if dlstreamer-pipeline-server is running
        get_status
        # get the loaded pipelines
        get_loaded_pipelines
        return
    fi

}

get_loaded_pipelines() {
    echo "Getting list of loaded pipelines..."
    response=$(curl -s -k -w "\n%{http_code}" https://$CURL_HOST_IP/api/pipelines)
    # Split response and status
    body=$(echo "$response" | sed '$d')
    status=$(echo "$response" | tail -n1)
    # Check if the status is 200 OK
    if [[ "$status" -ne 200 ]]; then
        err "Failed to get pipelines from dlstreamer-pipeline-server. HTTP Status Code: $status"
        exit 1
    else
        echo "Loaded pipelines:"
        echo "$body"
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

get_status() {
    response=$(curl -s -k -w "\n%{http_code}" https://$CURL_HOST_IP/api/pipelines/status)
    # Split response and status
    body=$(echo "$response" | sed '$d')
    status=$(echo "$response" | tail -n1)
    # echo $status
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
    echo "Usage: $0 [helm] [-h | --help]"
    echo "Arguments:"
    echo "  helm                            For Helm deployment (adds :30443 port to HOST_IP for curl commands)"
    echo "Options:"
    echo "  -i, --instance <instance_name>  Specify the instance name to get the status of a specific instance from config.yml"
    echo "  -h, --help                      Show this help message"
}

main() {

    # Parse arguments
    # Include a flag -i for instance_name such that if config.yml is present then it can be used to get status of specific instance inside the while loop
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
        helm)
            DEPLOYMENT_TYPE="helm"
            shift
            ;;
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

    # List all loaded pipelines
    list_pipelines
}

main "$@"