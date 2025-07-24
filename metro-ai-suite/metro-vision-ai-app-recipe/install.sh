#!/bin/bash

# Path to the .env file
ENV_FILE="./.env"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found."
    exit 1
fi

# Check and set SAMPLE_APP from first argument
SAMPLE_APP_ARG="$1"
if [ -z "$SAMPLE_APP_ARG" ]; then
    echo "Error: First argument (SAMPLE_APP) is required."
    echo "Usage: $0 <smart-parking|loitering-detection|smart-intersection> [HOST_IP]"
    exit 1
fi

case "$SAMPLE_APP_ARG" in
    "smart-parking"|"loitering-detection"|"smart-intersection")
        # Update SAMPLE_APP in .env file
        if grep -q "^SAMPLE_APP=" "$ENV_FILE"; then
            sed -i "s/^SAMPLE_APP=.*/SAMPLE_APP=$SAMPLE_APP_ARG/" "$ENV_FILE"
        else
            echo "SAMPLE_APP=$SAMPLE_APP_ARG" >> "$ENV_FILE"
        fi
        ;;
    *)
        echo "Error: Invalid SAMPLE_APP value '$SAMPLE_APP_ARG'. Must be one of: smart-parking, loitering-detection, smart-intersection."
        exit 1
        ;;
esac

# Update the HOST_IP in .env file
# Check if HOST_IP is provided as second argument, otherwise use hostname -I
HOST_IP_ARG="$2"
if [ -z "$HOST_IP_ARG" ]; then
    HOST_IP=$(hostname -I | cut -f1 -d' ')
else
    # Validate IP format (basic validation for IPv4)
    if [[ ! $HOST_IP_ARG =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "Warning: Invalid IP format. Using hostname -I instead."
        HOST_IP=$(hostname -I | cut -f1 -d' ')
    else
        HOST_IP=$HOST_IP_ARG
    fi
fi

echo "Configuring application to use $HOST_IP"
if grep -q "^HOST_IP=" "$ENV_FILE"; then
    # Replace existing HOST_IP line
    sed -i "s/^HOST_IP=.*/HOST_IP=$HOST_IP/" "$ENV_FILE"
else
    # Add HOST_IP if it doesn't exist
    echo "HOST_IP=$HOST_IP" >> "$ENV_FILE"
fi

# Extract SAMPLE_APP variable from .env file
SAMPLE_APP=$(grep -E "^SAMPLE_APP=" "$ENV_FILE" | cut -d '=' -f2 | tr -d '"' | tr -d "'")

# Bring down the application before updating docker compose file
if docker compose ps >/dev/null 2>&1; then
    echo "Bringing down any running containers..."
    docker compose down
fi

# Copy appropriate docker-compose file
if [ "$SAMPLE_APP" = "smart-intersection" ]; then
    cp compose-scenescape.yml docker-compose.yml
else
    cp compose-without-scenescape.yml docker-compose.yml
fi

# Check if the directory exists
if [ ! -d "$SAMPLE_APP" ]; then
    echo "Error: Directory $SAMPLE_APP does not exist."
    exit 1
fi

# Navigate to the directory and run the install script
echo "Navigating to $SAMPLE_APP directory and running install script..."
cd "$SAMPLE_APP" || exit 1

if [ -f "./install.sh" ]; then
    chmod +x ./install.sh
    ./install.sh $HOST_IP
else
    echo "Error: install.sh not found in $SAMPLE_APP directory."
    exit 1
fi