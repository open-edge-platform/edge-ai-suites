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
VARS_TO_EXPORT=("HOST_IP" "REST_SERVER_PORT" "SAMPLE_APP" )

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
    if [[ ! -f "$ENV_PATH/.env" ]]; then
        touch "$ENV_PATH/.env"
    fi
    # loop through the variables to export
    for var in "${VARS_TO_EXPORT[@]}"; do
        value=$(get_env_value "$var")
        if [[ -n "$value" ]]; then
            # check if the variable is already in the .env file
            if grep -q "^$var=" "$ENV_PATH/.env"; then
                # update the variable in the .env file
                sed -i "s/^$var=.*/$var=$value/" "$ENV_PATH/.env"
                echo "Updated $var in .env file"
            else
                # add the variable to the .env file
                echo "$var=$value" >>"$ENV_PATH/.env"
                echo "Added $var to .env file"
            fi
        else
            echo "Variable $var not found in YAML"
        fi
    done

    # update APP_DIR in $ENV_PATH/.env to $SAMPLE_APP
    if grep -q "^APP_DIR=" "$ENV_PATH/.env"; then
        if [[ "$ENV_PATH" == *"/helm/temp_apps/"* ]]; then
            sed -i "s|^APP_DIR=.*|APP_DIR=$ENV_PATH|" "$ENV_PATH/.env"
        else
            sed -i "s|^APP_DIR=.*|APP_DIR=$ENV_PATH/helm/apps/$SAMPLE_APP|" "$ENV_PATH/.env"
        fi
    else
        # add APP_DIR to .env file in new line
        if [[ -s "$ENV_PATH/.env" && $(tail -c1 "$ENV_PATH/.env" | wc -l) -eq 0 ]]; then
            # Add a newline first
            echo "" >>"$ENV_PATH/.env"
        fi
        echo "APP_DIR=$ENV_PATH/helm/apps/$SAMPLE_APP" >>"$ENV_PATH/.env"
    fi
    echo "Environment variables updated in $ENV_PATH/.env"

}

init_instance_helm() {
    # With the existance of config.yml, this function is used to initialize each instance for helm mode
    local SAMPLE_APP=$1
    local INSTANCE_NAME=$2
    local ENV_VARS=$3
    echo "Setting up (helm): $SAMPLE_APP / $INSTANCE_NAME"
    # Create helm/temp_apps/SAMPLE_APP/INSTANCE_NAME directory structure
    TEMP_APP_DIR="$SCRIPT_DIR/helm/temp_apps/$SAMPLE_APP/$INSTANCE_NAME"
    if [[ ! -d "$TEMP_APP_DIR" ]]; then
        mkdir -p "$TEMP_APP_DIR"
        echo "Created directory: $TEMP_APP_DIR"
    else
        echo "Directory already exists: $TEMP_APP_DIR"
    fi
    # Check if source app directory exists
    SOURCE_APP_DIR="$SCRIPT_DIR/helm/apps/$SAMPLE_APP"
    if [[ ! -d "$SOURCE_APP_DIR" ]]; then
        err "Source app directory $SOURCE_APP_DIR does not exist."
        return 1
    fi
    # Copy configs from helm/apps/SAMPLE_APP/configs to helm/temp_apps/SAMPLE_APP/INSTANCE_ID/configs
    if [[ -d "$SOURCE_APP_DIR/configs" ]]; then
        cp -r "$SOURCE_APP_DIR/configs" "$TEMP_APP_DIR/"
        echo "Copied configs from $SOURCE_APP_DIR/configs to $TEMP_APP_DIR/configs"
    else
        echo "Warning: No configs directory found in $SOURCE_APP_DIR"
    fi
    # Copy payload.json from helm/apps/SAMPLE_APP/payload.json to helm/temp_apps/SAMPLE_APP/INSTANCE_ID/payload.json
    if [[ -f "$SOURCE_APP_DIR/payload.json" ]]; then
        cp "$SOURCE_APP_DIR/payload.json" "$TEMP_APP_DIR/payload.json"
        echo "Copied payload.json to $TEMP_APP_DIR/payload.json"
    else        
        echo "Warning: No payload.json found in $SOURCE_APP_DIR"
    fi  
    # Copy pipeline-server-config.json from helm/apps/SAMPLE_APP/pipeline-server-config.json to helm/temp_apps/SAMPLE_APP/INSTANCE_ID/pipeline-server-config.json
    if [[ -f "$SOURCE_APP_DIR/pipeline-server-config.json" ]]; then
        cp "$SOURCE_APP_DIR/pipeline-server-config.json" "$TEMP_APP_DIR/pipeline-server-config.json"
        echo "Copied pipeline-server-config.json to $TEMP_APP_DIR/pipeline-server-config.json"
    else        
        echo "Warning: No pipeline-server-config.json found in $SOURCE_APP_DIR"
    fi
    # Copy base values_<sample_app>.yaml file to instance directory as values.yaml
    if [[ -f "$SCRIPT_DIR/helm/values_$SAMPLE_APP.yaml" ]]; then
        cp "$SCRIPT_DIR/helm/values_$SAMPLE_APP.yaml" "$TEMP_APP_DIR/values.yaml"
        echo "Copied values_$SAMPLE_APP.yaml file to $TEMP_APP_DIR/values.yaml"
    else
        # Throw error if base doesn't exist
        err "Base values file not found at $SCRIPT_DIR/helm/values_$SAMPLE_APP.yaml"
        return 1
    fi
    
    # Set ENV_PATH to helm/temp_apps/SAMPLE_APP/INSTANCE_NAME
    ENV_PATH="$TEMP_APP_DIR"
    YAML_FILE="$TEMP_APP_DIR/values.yaml"
    # load environment variables from helm/temp_apps/SAMPLE_APP/INSTANCE_NAME/values.yaml
    # load environment variables from helm/temp_apps/SAMPLE_APP/INSTANCE_NAME/values.yaml if it exists inside SCRIPT_DIR/helm/temp_apps/SAMPLE_APP/INSTANCE_NAME/values.yaml
    # set ENV_PATH to SCRIPT_DIR
    # Update environment variables in the instance values.yaml file
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
    # Extract NGINX_HTTPS_PORT from config.yml ENV_VARS and add to .env file

    IFS=',' read -ra VARS <<< "$ENV_VARS"
    for var in "${VARS[@]}"; do
        key=$(echo "$var" | cut -d'=' -f1)
        value=$(echo "$var" | cut -d'=' -f2-)
        if [[ "$key" == "NGINX_HTTPS_PORT" ]]; then
            if grep -q "^NGINX_HTTPS_PORT=" "$TEMP_APP_DIR/.env"; then
                sed -i "s|^NGINX_HTTPS_PORT=.*|NGINX_HTTPS_PORT=$value|" "$TEMP_APP_DIR/.env"
                echo "Updated NGINX_HTTPS_PORT in .env"
            else
                echo "NGINX_HTTPS_PORT=$value" >> "$TEMP_APP_DIR/.env"
                echo "Added NGINX_HTTPS_PORT to .env"
            fi
            break
        fi
    done
    #call update_values_yaml_from_config to update values.yaml with ENV_VARS
    update_values_yaml_from_config "$ENV_VARS" "$TEMP_APP_DIR/values.yaml" "$INSTANCE_NAME"

    # Copy Chart_<sample_app>.yaml as Chart.yaml to the folder /helm/temp_apps/SAMPLE_APP/INSTANCE_NAME
    CHART_SRC_FILE="$SCRIPT_DIR/helm/Chart-${SAMPLE_APP}.yaml"
    CHART_DEST_FILE="$TEMP_APP_DIR/Chart.yaml"

    if [[ -f "$CHART_SRC_FILE" ]]; then
        cp "$CHART_SRC_FILE" "$CHART_DEST_FILE"
        echo "Copied $CHART_SRC_FILE to $CHART_DEST_FILE"
    else
        err "Chart file $CHART_SRC_FILE not found."
        return 1
    fi
    
    # Set permissions for the source app directory
    SOURCE_APP_DIR="$SCRIPT_DIR/helm/apps/$SAMPLE_APP"
    if [[ -d "$SOURCE_APP_DIR" ]]; then
        set_permissions "$SOURCE_APP_DIR"
    fi
}


update_values_yaml_from_config() {
    # This function updates the values.yaml file for the instance based on the variables in config.yml for that instance. 
    # It takes the ENV_VARS string, the path to the values.yaml file, and the instance name as arguments.
    local env_vars="$1"
    local values_file="$2"
    local instance_name="$3"
    
    [[ -f "$values_file" ]] || return 0
    
    # Update namespace to instance_name 
    if [[ -n "$instance_name" ]]; then
        awk -v ns="$instance_name" '
            /^namespace:/ { print "namespace: " ns; next }
            { print }
        ' "$values_file" > "${values_file}.tmp" && mv "${values_file}.tmp" "$values_file"
    fi
    
    # Parse port configuration from env_vars
    local s3="" coturn="" nhttp="" nhttps=""
    IFS=',' read -ra pairs <<< "$env_vars"
    for pair in "${pairs[@]}"; do
        local key="${pair%%=*}"
        local val="${pair#*=}"
        case "$key" in
            S3_STORAGE_PORT)  s3="$val" ;;
            COTURN_PORT)      coturn="$val" ;;
            NGINX_HTTP_PORT)  nhttp="$val" ;;
            NGINX_HTTPS_PORT) nhttps="$val" ;;
        esac
    done
    
    # Update values in YAML structure
    awk -v s3="$s3" -v nhttp="$nhttp" -v nhttps="$nhttps" -v coturn="$coturn" '
        function quote(v) { return "\"" v "\"" }
        
        BEGIN { section=""; subsec=""; service="" }
        
        # Reset context on top-level keys
        /^[^[:space:]]/ { section=""; subsec=""; service="" }
        
        # Track sections
        /^env:/    { section="env"; print; next }
        /^config:/ { section="config"; service=""; print; next }
        
        # Track services within config
        section == "config" && /^  nginx:/  { service="nginx"; subsec=""; print; next }
        section == "config" && /^  coturn:/ { service="coturn"; subsec=""; print; next }
        section == "config" && /^  [a-zA-Z_][a-zA-Z0-9_-]*:/ { service=""; subsec=""; print; next }
        
        # Track subsections within services
        section == "config" && service == "nginx"  && /^    int:/ { subsec="int"; print; next }
        section == "config" && service == "nginx"  && /^    ext:/ { subsec="ext"; print; next }
        section == "config" && service == "coturn" && /^    int:/ { subsec="int"; print; next }
        section == "config" && service == "coturn" && /^    ext:/ { subsec="ext"; print; next }
        
        # Update values in appropriate sections
        section == "env" && /^  S3_STORAGE_PORT:/ && s3 != "" {
            sub(/:.*/, ": " quote(s3)); print; next
        }
        section == "config" && service == "nginx" && subsec == "ext" && /^      http_port:/ && nhttp != "" {
            sub(/:.*/, ": " quote(nhttp)); print; next
        }
        section == "config" && service == "nginx" && subsec == "ext" && /^      https_port:/ && nhttps != "" {
            sub(/:.*/, ": " quote(nhttps)); print; next
        }
        section == "config" && service == "coturn" && subsec == "ext" && /^      coturn_tcp_port:/ && coturn != "" {
            sub(/:.*/, ": " quote(coturn)); print; next
        }
        section == "config" && service == "coturn" && subsec == "ext" && /^      coturn_udp_port:/ && coturn != "" {
            sub(/:.*/, ": " quote(coturn)); print; next
        }
        
        # Default: print line as-is
        { print }
    ' "$values_file" > "${values_file}.tmp" && mv "${values_file}.tmp" "$values_file"
}



init_helm() {
    # check if config.yml exists
    if [[ -f "$CONFIG_FILE" ]]; then
    # Multi-instance setup for helm
    # Parse config.yml to set up for all instances
    # Initialize counters and arrays for summary
        local instance_count=0
        local instance_names=()
        local sample_app_names=()
    # Parse config.yml and initialize each instance for helm by calling init_instance_helm
        while IFS='|' read -r sample_app instance_name env_vars; do
            if init_instance_helm "$sample_app" "$instance_name" "$env_vars"; then
                ((instance_count++))
                instance_names+=("$instance_name")
                # Add to sample_app_names if not already present
                if [[ ! " ${sample_app_names[@]} " =~ " ${sample_app} " ]]; then
                    sample_app_names+=("$sample_app")
                fi
            else
                err "Failed to initialize instance $sample_app/$instance_name for helm"
            fi
        done < <(parse_config_yml)
        
        # Validate at least one instance was initialized
        if [[ $instance_count -eq 0 ]]; then
            err "No instances were initialized from config file. Check config.yml format."
            exit 1
        fi
        
        # Print summary
        echo "Setup Summary for multi instances (helm):"
        echo "  Number of Sample Apps: ${#sample_app_names[@]}"
        echo "  Number of Instances in config.yml: $instance_count"
        echo "All instances setup completed for helm!"
        return
    else 
        # Single instance setup for helm
        # load environment variables from helm/values.yaml
        # load environment variables from helm/values.yaml if it exists inside SCRIPT_DIR/helm/values.yaml
        # set ENV_PATH to SCRIPT_DIR
        ENV_PATH="$SCRIPT_DIR"
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
        
        # Set permissions for single instance helm
        APP_DIR="$SCRIPT_DIR/helm/apps/$SAMPLE_APP"
        if [[ -d "$APP_DIR" ]]; then
            set_permissions "$APP_DIR"
        fi
    fi
}

main() {
    # check for helm argument
    if [[ "$1" == "helm" ]]; then
        echo "Setting up helm"
        # initialize the sample app for helm, load env from values.yml
        init_helm
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
