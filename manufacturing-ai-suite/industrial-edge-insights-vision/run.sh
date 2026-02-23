#!/bin/bash
# Start and stop all containers for the instances defined in config.yml

SCRIPT_DIR=$(dirname $(readlink -f "$0"))
CONFIG_FILE="$SCRIPT_DIR/config.yml"

err() {
    echo "ERROR: $1" >&2
}

usage() {
    echo "Usage: $0 <command> [subcommand]"
    echo ""
    echo "Docker Compose commands:"
    echo "  up             - Start all instances"
    echo "  down           - Stop all instances"
    echo ""
    echo "Helm commands:"
    echo "  helm_install   - Install helm releases for all instances"
    echo "  helm uninstall - Uninstall helm releases for all instances"
    exit 1
}

# Parse config.yml to get all instances
get_all_instances() {
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

main() {
    if [[ $# -ne 1 ]]; then
        usage
    fi
    
    if [[ ! -f "$CONFIG_FILE" ]]; then
        err "Config file not found: $CONFIG_FILE"
        exit 1
    fi
    
    case "$1" in
        up) 
            echo "Starting all instances..."
            while IFS='|' read -r sample_app instance_name; do
                env_file="$SCRIPT_DIR/temp_apps/$sample_app/$instance_name/.env"
                if [[ ! -f "$env_file" ]]; then
                    err "Environment file not found: $env_file"
                    err "Run ./setup.sh first"
                    exit 1
                fi
                echo "Starting $sample_app/$instance_name..."
                docker compose -p "$instance_name" --env-file "$env_file" up -d
            done < <(get_all_instances)
            echo "All instances started!"
            ;;
        down)
            echo "Stopping all instances..."
            while IFS='|' read -r sample_app instance_name; do
                echo "Stopping $sample_app/$instance_name..."
                docker compose -p "$instance_name" down -v
            done < <(get_all_instances)
            echo "All instances stopped!"
            ;;
        helm_install)
            echo "Installing helm releases for all instances..."
            while IFS='|' read -r sample_app instance_name; do
            values_file="$SCRIPT_DIR/helm/temp_apps/$sample_app/$instance_name/values.yaml"
            if [[ ! -f "$values_file" ]]; then
                err "Values file not found: $values_file"
                exit 1
            fi
            echo "Installing $instance_name..."
            helm install "$instance_name" helm -n "$instance_name" --create-namespace -f "$values_file"
            done < <(get_all_instances)
            echo "All helm releases installed!"
            ;;
        helm_uninstall)
            echo "Uninstalling helm releases for all instances..."
            while IFS='|' read -r sample_app instance_name; do
            echo "Uninstalling $instance_name..."
            helm uninstall "$instance_name" -n "$instance_name"
            done < <(get_all_instances)
            echo "All helm releases uninstalled!"
            ;;
        *)
            usage
            ;;
    esac
}

main "$@"