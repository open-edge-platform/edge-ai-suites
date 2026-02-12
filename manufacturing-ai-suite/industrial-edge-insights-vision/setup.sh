#!/bin/bash
# Download artifacts for a specific sample application 
#   by calling respective app's setup.sh script

SCRIPT_DIR=$(dirname $(readlink -f "$0"))
CONFIG_FILE="$SCRIPT_DIR/config.yml"      # Config file path for multiple instances

err() {
    echo "ERROR: $1" >&2
}

init() { 
    if [[ -f "$CONFIG_FILE" ]]; then
    # Multi-instance setup
    # Parse config.yml to set up all instances
        awk '
        /^[a-zA-Z_][a-zA-Z0-9_-]*:/ {
            sample_app = $1
            gsub(/:/, "", sample_app)
            print sample_app
        }
        ' "$CONFIG_FILE" | sort -u | while read -r sample_app; do
            APP_DIR="$SCRIPT_DIR/apps/$sample_app"
            set_permissions "$APP_DIR"
        done
        echo "Parsing config file: $CONFIG_FILE"

        # Initialize counters and arrays for summary
        local instance_count=0
        local instance_names=()
        local sample_app_names=()
        
        while IFS='|' read -r sample_app instance_name env_vars; do
            if init_instance "$sample_app" "$instance_name" "$env_vars"; then
                ((instance_count++))
                instance_names+=("$instance_name")
                # Add to sample_app_names if not already present
                if [[ ! " ${sample_app_names[@]} " =~ " ${sample_app} " ]]; then
                    sample_app_names+=("$sample_app")
                fi
            else
                err "Failed to initialize instance $sample_app/$instance_name"
            fi
        done < <(parse_config_yml)
        
        # Validate at least one instance was initialized
        if [[ $instance_count -eq 0 ]]; then
            err "No instances were initialized from config file. Check config.yml format."
            exit 1
        fi
        
        # Print summary
        echo "Setup Summary for multi instances:"
        echo "  Number of Sample Apps: ${#sample_app_names[@]}"
        echo "  Number of Instances in config.yml: $instance_count"
        echo "All instances setup completed"
    else
        # Single instance setup
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
            set_permissions "$APP_DIR"
        fi
        
        # check if SAMPLE_APP directory exists
        if [[ ! -d "$APP_DIR" ]]; then
            err "SAMPLE_APP directory $APP_DIR does not exist."
            exit 1
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
        vars = ""
    }
    # Skip empty lines and comments
    /^[[:space:]]*$/ { next }
    /^[[:space:]]*#/ { next }
    
    # Level 1: SAMPLE_APP (no leading spaces, ends with colon)
    /^[a-zA-Z_][a-zA-Z0-9_-]*:/ {
        if (sample_app != "" && instance_name != "" && vars != "") {
            print sample_app "|" instance_name "|" vars
        }
        sample_app = $1
        gsub(/:/, "", sample_app)
        instance_name = ""
        vars = ""
        next
    }
    
    # Level 2: INSTANCE_NAME (2 spaces indent, ends with colon)
    /^  [a-zA-Z_][a-zA-Z0-9_-]*:/ {
        if (instance_name != "" && vars != "") {
            print sample_app "|" instance_name "|" vars
        }
        instance_name = $1
        gsub(/^[[:space:]]+/, "", instance_name)
        gsub(/:/, "", instance_name)
        vars = ""
        next
    }
    
    # Level 3: Key-Value pairs (4 spaces indent)
    /^    [a-zA-Z_][a-zA-Z0-9_-]*:/ {
        key = $1
        gsub(/:/, "", key)
        gsub(/^[[:space:]]+/, "", key)
        value = $2
        gsub(/^[[:space:]]+/, "", value)
        if (vars != "") {
            vars = vars "," key "=" value
        } else {
            vars = key "=" value
        }
    }
    
    END {
        if (sample_app != "" && instance_name != "" && vars != "") {
            print sample_app "|" instance_name "|" vars
        }
    }
    ' "$CONFIG_FILE"
}

# Function to initialize a single instance
init_instance() {
    local SAMPLE_APP=$1
    local INSTANCE_NAME=$2
    local ENV_VARS=$3
    
    echo "Setting up: $SAMPLE_APP / $INSTANCE_NAME"
    
    
    # Create temp_apps/SAMPLE_APP/INSTANCE_NAME directory structure
    TEMP_APP_DIR="$SCRIPT_DIR/temp_apps/$SAMPLE_APP/$INSTANCE_NAME"
    if [[ ! -d "$TEMP_APP_DIR" ]]; then
        mkdir -p "$TEMP_APP_DIR"
        echo "Created directory: $TEMP_APP_DIR"
    else
        echo "Directory already exists: $TEMP_APP_DIR"
    fi
    
    # Check if source app directory exists
    SOURCE_APP_DIR="$SCRIPT_DIR/apps/$SAMPLE_APP"
    if [[ ! -d "$SOURCE_APP_DIR" ]]; then
        err "Source app directory $SOURCE_APP_DIR does not exist."
        return 1
    fi
    
    # Copy configs from apps/SAMPLE_APP/configs to temp_apps/SAMPLE_APP/INSTANCE_ID/configs
    if [[ -d "$SOURCE_APP_DIR/configs" ]]; then
        cp -r "$SOURCE_APP_DIR/configs" "$TEMP_APP_DIR/"
        echo "Copied configs from $SOURCE_APP_DIR/configs to $TEMP_APP_DIR/configs"
    else
        echo "Warning: No configs directory found in $SOURCE_APP_DIR"
    fi
    
    # Copy payload.json from apps/SAMPLE_APP/payload.json to temp_apps/SAMPLE_APP/INSTANCE_ID/payload.json
    if [[ -f "$SOURCE_APP_DIR/payload.json" ]]; then
        cp "$SOURCE_APP_DIR/payload.json" "$TEMP_APP_DIR/payload.json"
        echo "Copied payload.json to $TEMP_APP_DIR/payload.json"
    else
        echo "Warning: No payload.json found in $SOURCE_APP_DIR"
    fi

    # Copy base .env_<sample_app> file to instance directory
    if [[ -f "$SCRIPT_DIR/.env_$SAMPLE_APP" ]]; then
        cp "$SCRIPT_DIR/.env_$SAMPLE_APP" "$TEMP_APP_DIR/.env"
        echo "Copied .env_$SAMPLE_APP file to $TEMP_APP_DIR/.env"
    else
        # Throw error if base doesn't exist
        err "Base .env file not found at $SCRIPT_DIR/.env_$SAMPLE_APP"
        return 1
    fi
    
    # Append instance-specific environment variables to the .env file
    echo "" >> "$TEMP_APP_DIR/.env"
    echo "# Instance-specific variables for $SAMPLE_APP/$INSTANCE_NAME" >> "$TEMP_APP_DIR/.env"
    echo "INSTANCE_NAME=$INSTANCE_NAME" >> "$TEMP_APP_DIR/.env"
    
    # Parse and append the ENV_VARS
    IFS=',' read -ra VARS <<< "$ENV_VARS"
    # Update instance-specific environment variables to the TEMP_APP_DIR/.env file. append if not exist
    # loop through each variable and update or append
    for var in "${VARS[@]}"; do
        key=$(echo "$var" | cut -d'=' -f1)
        value=$(echo "$var" | cut -d'=' -f2-)
        if grep -q "^$key=" "$TEMP_APP_DIR/.env"; then
            sed -i "s|^$key=.*|$key=$value|" "$TEMP_APP_DIR/.env"
            echo "Updated $key in .env"
        else
            echo "$key=$value" >> "$TEMP_APP_DIR/.env"
            echo "Added $key to .env"
        fi
    done
    
    # Update APP_DIR in the instance .env file
    if grep -q "^APP_DIR=" "$TEMP_APP_DIR/.env"; then
        sed -i "s|^APP_DIR=.*|APP_DIR=$TEMP_APP_DIR|" "$TEMP_APP_DIR/.env"
    else
        echo "APP_DIR=$TEMP_APP_DIR" >> "$TEMP_APP_DIR/.env"
    fi
    
    echo "Instance .env file configured at $TEMP_APP_DIR/.env"
    
    # Export variables from the instance .env file
    export $(grep -v -E '^\s*#' "$TEMP_APP_DIR/.env" | sed -e 's/#.*$//' -e '/^\s*$/d' | xargs)
    
    # Run the setup script for this instance 
    if [[ -f "$SOURCE_APP_DIR/setup.sh" ]]; then
        echo "Running setup script for $SAMPLE_APP/$INSTANCE_NAME"
        chmod +x "$SOURCE_APP_DIR/setup.sh"
        bash "$SOURCE_APP_DIR/setup.sh"
    else
        err "No setup.sh found in $SOURCE_APP_DIR directory."
        return 1
    fi
    
    echo "Completed setup for $SAMPLE_APP/$INSTANCE_NAME"
    echo ""
}

# Helm-related functions (preserved for helm mode)
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
        # initialize the compose based sample app, load env from config.yml or .env
        init
    fi
}

set_permissions(){    
    APP_DIR=$1
        # set permissions for the sample_*.sh scripts in current directory
        for script in "$SCRIPT_DIR"/sample_*.sh; do
            if [[ -f "$script" ]]; then
                echo "Setting executable permission for $script"
                chmod +x "$script"
            fi
        done

        # set permissions for the setup.sh script
        echo "Setting executable permission for setup.sh in $APP_DIR"
        chmod +x "$APP_DIR/setup.sh"

        # set permission for run.sh
        echo "Setting executable permission for run.sh"
        chmod +x "$SCRIPT_DIR/run.sh"

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