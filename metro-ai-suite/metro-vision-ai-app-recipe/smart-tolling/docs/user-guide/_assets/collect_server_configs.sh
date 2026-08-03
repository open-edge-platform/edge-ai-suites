#!/bin/bash
# collect_server_configs.sh
# -----------------------------------------------------------------------------
# Usage: ./collect_server_configs.sh [APP_NAME]
# Example: ./collect_server_configs.sh smart-intersection
#
# This script bundles specific configuration files referenced in the 
# docker-compose.yml for documentation and local replication.
# It skips large database dumps and media files.
# -----------------------------------------------------------------------------

APP_NAME=${1:-smart-intersection}
OUTPUT_DIR="metro_config_bundle"
ARCHIVE_NAME="metro_configs.tar.gz"

echo "=========================================="
echo "Collecting configs for: $APP_NAME"
echo "=========================================="

if [ ! -d "$APP_NAME" ]; then
    echo "Error: Directory '$APP_NAME' not found in current path."
    echo "Please run this script from the directory containing '$APP_NAME'."
    exit 1
fi

# Clean up previous runs
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# Defines files to collect explicitly to avoid grabbing unnecessary large files
FILES=(
    # Nginx
    "src/nginx/anpr.conf"
    
    # Mosquitto
    "src/mosquitto/mosquitto-secure.conf"
    
    # Node-RED
    "src/node-red/flows.json"
    "src/node-red/flows_cred.json"
    "src/node-red/settings.js"
    "src/node-red/install_package.sh"
    
    # Grafana
    "src/grafana/data/dashboards/anthem-intersection.json"
    "src/grafana/dashboards.yml"
    "src/grafana/datasources.yml"
    
    # DLStreamer (Critical)
    "src/dlstreamer-pipeline-server/config.json"
    
    # SceneScape Configs
    "src/webserver/user_access_config.json"
    "src/controller/tracker-config.json"
)

# Directories to collect recursively (e.g. scripts)
DIRECTORIES=(
    "src/dlstreamer-pipeline-server/user_scripts"
)

# Copy Files
echo "--> Copying individual config files..."
for file in "${FILES[@]}"; do
    SRC="$APP_NAME/$file"
    DEST="$OUTPUT_DIR/$SRC"
    
    if [ -f "$SRC" ]; then
        mkdir -p "$(dirname "$DEST")"
        cp "$SRC" "$DEST"
        echo "   OK: $file"
    else
        echo "   MISSING: $file"
    fi
done

# Copy Directories
echo "--> Copying script directories..."
for dir in "${DIRECTORIES[@]}"; do
    SRC="$APP_NAME/$dir"
    DEST="$OUTPUT_DIR/$SRC"
    
    if [ -d "$SRC" ]; then
        mkdir -p "$(dirname "$DEST")"
        cp -r "$SRC" "$(dirname "$DEST")"
        echo "   OK: Directory $dir"
    else
        echo "   MISSING: Directory $dir"
    fi
done

# Optional: Collecting Secrets (Certificates only, usually safe/needed for docs context)
# We usually avoid passwords, but including certs helps verify SSL setup docs.
echo "--> Copying certificates (excluding passwords)..."
mkdir -p "$OUTPUT_DIR/$APP_NAME/src/secrets/certs"
if [ -d "$APP_NAME/src/secrets/certs" ]; then
    cp "$APP_NAME/src/secrets/certs/"*.pem "$OUTPUT_DIR/$APP_NAME/src/secrets/certs/" 2>/dev/null
    cp "$APP_NAME/src/secrets/certs/"*.crt "$OUTPUT_DIR/$APP_NAME/src/secrets/certs/" 2>/dev/null
    # Skipping keys for security, unless explicitly needed. 
    # cp "$APP_NAME/src/secrets/certs/"*.key "$OUTPUT_DIR/$APP_NAME/src/secrets/certs/" 
    echo "   OK: Certificates copied."
else
    echo "   MISSING: Certs directory."
fi

# Create Tarball
echo "=========================================="
echo "Creating archive: $ARCHIVE_NAME"
tar -czf "$ARCHIVE_NAME" -C "$OUTPUT_DIR" .
echo "Done."
echo "=========================================="
echo "Transfer '$ARCHIVE_NAME' to your local machine and unpack it."
echo "=========================================="
