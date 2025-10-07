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

delete_pipeline_instance() {
    local instance_id="$1"
    echo "Stopping pipeline instance with ID: $instance_id"
    # Use curl to delete the pipeline instance
    response=$(curl -s -k -w "\n%{http_code}" -X DELETE https://$HOST_IP/api/pipelines/$instance_id)

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
    response=$(curl -s -k -w "\n%{http_code}" https://$HOST_IP/api/pipelines/status)
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
    # initialize the sample app, load env
    init
    # check if dlstreamer-pipeline-server is running
    get_status
    # get loaded pipelines
    stop_pipeline_instances "$@"
}

get_status() {
    response=$(curl -s -k -w "\n%{http_code}" https://$HOST_IP/api/pipelines/status)
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
    echo "Usage: $0 [--all] [ -i | --id <instance_id> ] [-h | --help]"
    echo "Options:"
    echo "  --all                           Stop all running pipelines instances (default)"
    echo "  -i, --id <instance_id>          Stop a pipeline instance"
    echo "  -h, --help                      Show this help message"
}

main() {

    # If no arguments provided, stop all pipeline instances
    if [[ -z "$1" ]]; then
        echo "No pipelines specified. Stopping all pipeline instances"
        stop_pipelines
        return
    fi

    case "$1" in
    --all)
        echo "Stopping all pipeline instances"
        stop_pipelines
        ;;
    -i | --id)
        # TODO support multiple instance ids
        # Check if the next argument is provided and not empty, and loop through all pipelines and launch them
        shift
        if [[ -z "$1" ]]; then
            err "--id requires a non-empty argument."
            usage
            exit 1
        else
            # stop the pipeline instance with the given id
            init
            delete_pipeline_instance "$1"
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
