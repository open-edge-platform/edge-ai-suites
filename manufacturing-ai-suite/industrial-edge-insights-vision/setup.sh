#!/bin/bash
# Download artifacts for a specific sample application
#   by calling respective app's setup.sh script

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
        # update APP_DIR in $SCRIPT_DIR/.env to $SAMPLE_APP
        if grep -q "^APP_DIR=" "$SCRIPT_DIR/.env"; then
            sed -i "s|^APP_DIR=.*|APP_DIR=$SCRIPT_DIR/apps/$SAMPLE_APP|" "$SCRIPT_DIR/.env"
        else
            # add APP_DIR to .env file in new line
            if [[ -s "$SCRIPT_DIR/.env" && $(tail -c1 "$SCRIPT_DIR/.env" | wc -l) -eq 0 ]]; then
                # Add a newline first
                echo "" >>"$SCRIPT_DIR/.env"
            fi
            echo "APP_DIR=$SCRIPT_DIR/apps/$SAMPLE_APP" >>"$SCRIPT_DIR/.env"
        fi
        APP_DIR="$SCRIPT_DIR/apps/$SAMPLE_APP"
    fi
    # check if SAMPLE_APP directory exists
    if [[ ! -d "$APP_DIR" ]]; then
        err "SAMPLE_APP directory $APP_DIR does not exist."
        exit 1
    fi

}

YAML_FILE="helm/values.yaml"
VARS_TO_EXPORT=("HOST_IP" "REST_SERVER_PORT" "SAMPLE_APP")

# Function to extract values from 'env:' section of YAML
get_env_value() {
    local key=$1
    awk -v k="$key" '
    # Enter env section
    $0 ~ /^env:/ {env=1; next}
    # If inside env section, check for key: value
    env && $1 == k ":" {
      # Remove quotes and trailing spaces
      val = $2
      gsub(/"/, "", val)
      print val
      exit
    }
    # Leave env section on dedent or next top-level key
    env && /^[^ ]/ {env=0}
  ' "$YAML_FILE"
}

update_env_file() {
    # check if the .env file exists, if not create it
    # and update it with values from the arg listed in VARS_TO_EXPORT
    if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
        touch "$SCRIPT_DIR/.env"
    fi
    # loop through the variables to export
    for var in "${VARS_TO_EXPORT[@]}"; do
        value=$(get_env_value "$var")
        if [[ -n "$value" ]]; then
            # check if the variable is already in the .env file
            if grep -q "^$var=" "$SCRIPT_DIR/.env"; then
                # update the variable in the .env file
                sed -i "s/^$var=.*/$var=$value/" "$SCRIPT_DIR/.env"
                echo "Updated $var in .env file"
            else
                # add the variable to the .env file
                echo "$var=$value" >>"$SCRIPT_DIR/.env"
                echo "Added $var to .env file"
            fi
        else
            echo "Variable $var not found in YAML"
        fi
    done

    # update APP_DIR in $SCRIPT_DIR/.env to $SAMPLE_APP
    if grep -q "^APP_DIR=" "$SCRIPT_DIR/.env"; then
        sed -i "s|^APP_DIR=.*|APP_DIR=$SCRIPT_DIR/helm/apps/$SAMPLE_APP|" "$SCRIPT_DIR/.env"
    else
        # add APP_DIR to .env file in new line
        if [[ -s "$SCRIPT_DIR/.env" && $(tail -c1 "$SCRIPT_DIR/.env" | wc -l) -eq 0 ]]; then
            # Add a newline first
            echo "" >>"$SCRIPT_DIR/.env"
        fi
        echo "APP_DIR=$SCRIPT_DIR/helm/apps/$SAMPLE_APP" >>"$SCRIPT_DIR/.env"
    fi
    echo "Environment variables updated in $SCRIPT_DIR/.env"

}

init_helm() {
    # load environment variables from helm/values.yaml if it exists inside SCRIPT_DIR
    if [[ -f "$SCRIPT_DIR/helm/values.yaml" ]]; then
        for var in "${VARS_TO_EXPORT[@]}"; do
            value=$(get_env_value "$var")
            if [[ -n "$value" ]]; then
                export "$var=$value"
                echo "Exported $var=$value"
                update_env_file
            else
                echo "Variable $var not found in YAML"
            fi
        done
        echo "Environment variables loaded from $SCRIPT_DIR/helm/values.yaml"
    else
        echo "$SCRIPT_DIR/helm/values.yml"
        err "No helm/values.yml file found in $SCRIPT_DIR"
        exit 1
    fi

    # Copy Chart_<app>.yaml as Chart.yaml
    CHART_SRC_FILE="$SCRIPT_DIR/helm/Chart-${SAMPLE_APP}.yaml"
    CHART_DEST_FILE="$SCRIPT_DIR/helm/Chart.yaml"

    if [[ -f "$CHART_SRC_FILE" ]]; then
        cp "$CHART_SRC_FILE" "$CHART_DEST_FILE"
        echo "Copied $CHART_SRC_FILE to $CHART_DEST_FILE"
    else
        err "Chart file $CHART_SRC_FILE not found."
        exit 1
    fi
}

main() {
    # check for helm argument
    if [[ "$1" == "helm" ]]; then
        echo "Setting up helm"
        # initialize the sample app for helm, load env from values.yml
        init_helm
        APP_DIR="$SCRIPT_DIR/helm/apps/$SAMPLE_APP"
        echo "Using helm directory: $APP_DIR"
        # check if helm/apps directory exists
        if [[ ! -d "$APP_DIR" ]]; then
            err "Helm apps directory $APP_DIR does not exist."
            exit 1
        fi
    else
        # initialize the compose based sample app, load env
        init
        APP_DIR="$SCRIPT_DIR/apps/$SAMPLE_APP"
    fi
    # set permissions for the sample_*.sh scripts in current directory
    for script in "$SCRIPT_DIR"/sample_*.sh; do
        if [[ -f "$script" ]]; then
            echo "Setting executable permission for $script"
            chmod +x "$script"
        fi
    done

    # set permissions for the setup.sh script
    chmod +x "$APP_DIR/setup.sh"

    # check if setup.sh exists in the sample app directory
    if [[ -f "$APP_DIR/setup.sh" ]]; then
        echo "Running install script for $APP_DIR"
        # run the install script
        bash "$APP_DIR/setup.sh"
    else
        err "No setup.sh found in $APP_DIR directory."
        exit 1
    fi
}

main "$@"
