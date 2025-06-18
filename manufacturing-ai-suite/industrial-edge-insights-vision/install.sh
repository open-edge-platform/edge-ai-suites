#!/bin/bash
# Download artifacts for a specific sample application
#   by calling respective app's install.sh script

SCRIPT_DIR=$(dirname $(readlink -f "$0"))

err() {
    echo "ERROR: $1" >&2
}

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
    # check if SAMPLE_APP directory exists
    if [[ ! -d "$SAMPLE_APP" ]]; then
        err "SAMPLE_APP directory $SAMPLE_APP does not exist."
        exit 1
    fi

}


main() {
    # initialize the sample app, load env
    init
    # set permissions for the sample_*.sh scripts in current directory
    for script in "$SCRIPT_DIR"/sample_*.sh; do
        if [[ -f "$script" ]]; then
            echo "Setting executable permission for $script"
            chmod +x "$script"
        fi
    done
    # set permissions for the install.sh script
    chmod +x "$SAMPLE_APP/install.sh"
    # check if the install.sh script is executable

    # check if install.sh exists in the sample app directory
    if [[ -f "$SAMPLE_APP/install.sh" ]]; then
        echo "Running install script for $SAMPLE_APP"
        # run the install script
        bash "$SAMPLE_APP/install.sh"
    else
        err "No install.sh found in $SAMPLE_APP directory."
        exit 1
    fi
}

main
