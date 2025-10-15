#!/bin/bash
# This script is used to get status of all/specific pipeline instances in the dlstreamer-pipeline-server
# ------------------------------------------------------------------
# 1. Based on argument, get status of all or specific pipeline instance(s)
# ------------------------------------------------------------------

# Default values
SCRIPT_DIR=$(dirname $(readlink -f "$0"))
PIPELINE_ROOT="user_defined_pipelines" # Default root directory for pipelines

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

get_status_instance() {
    local instance_id="$1"
    echo "Getting status of pipeline instance with ID: $instance_id"
    # Use curl to get the status of the pipeline instance
    response=$(curl -s -k -w "\n%{http_code}" https://$HOST_IP/api/pipelines/$instance_id/status)

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
    response=$(curl -s -k -w "\n%{http_code}" https://$HOST_IP/api/pipelines/status)
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

err() {
    echo "ERROR: $*" >&2
}

usage() {
    echo "Usage: $0 [--all] [ -i | --id <instance_id> ] [-h | --help]"
    echo "Options:"
    echo "  --all                           Get status of all pipelines instances (default)"
    echo "  -i, --id <instance_id>          Get status of a specified pipeline instance(s)"
    echo "  -h, --help                      Show this help message"
}

main() {

    # If no arguments provided, fetch status of all pipeline instances
    if [[ -z "$1" ]]; then
        get_status_all
        return
    fi

    case "$1" in
    --all)
        echo "Fetching status for all pipeline instances"
        get_status_all
        ;;
    -i | --id)
        # TODO support multiple instance ids
        # Check if the next argument is provided and not empty, and loop through all instance_ids
        shift
        if [[ -z "$1" ]]; then
            err "--id requires a non-empty argument."
            usage
            exit 1
        else
            # loop over all instance ids
            ids="$@"
            init
            for id in $ids; do
                # get status of the pipeline instance with the given id
                echo "Stopping pipeline instance with ID: $id"
                get_status_instance "$id"
            done
        fi
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
}

main "$@"
