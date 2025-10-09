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

init() {
    # load environment variables from .env file if it exists
    if [[ -f "$SCRIPT_DIR/.env" ]]; then
        export $(grep -v -E '^\s*#' "$SCRIPT_DIR/.env" | sed -e 's/#.*$//' -e '/^\s*$/d' | xargs)
        echo "Environment variables loaded from $SCRIPT_DIR/.env"
    else
        err "No .env file found in $SCRIPT_DIR"
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

}

list_pipelines() {
    # initialize the sample app, load env
    init
    # check if dlstreamer-pipeline-server is running
    get_status
    # get loaded pipelines
    response=$(curl -s -k -w "\n%{http_code}" https://$HOST_IP/api/pipelines)
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

get_status() {
    response=$(curl -s -k -w "\n%{http_code}" https://$HOST_IP/api/pipelines/status)
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
    echo "Usage: $0 [-h | --help]"
    echo "Options:"
    echo "  -h, --help                      Show this help message"
}

main() {

    # If no arguments provided, list all loaded pipelines
    if [[ -z "$1" ]]; then
        list_pipelines
        return
    fi

    case "$1" in
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
}

main "$@"
