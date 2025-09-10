#!/bin/bash

# Path to the .env file
ENV_FILE="./.env"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found."
    exit 1
fi

# Extract SAMPLE_APP variable from .env file
SAMPLE_APP=$(grep -E "^SAMPLE_APP=" "$ENV_FILE" | cut -d '=' -f2 | tr -d '"' | tr -d "'")

# Check if SAMPLE_APP variable exists
if [ -z "$SAMPLE_APP" ]; then
    echo "Error: SAMPLE_APP variable not found in .env file."
    exit 1
fi

# Check if the directory exists
if [ ! -d "$SAMPLE_APP" ]; then
    echo "Error: Directory $SAMPLE_APP does not exist."
    exit 1
fi

# Navigate to the directory and run the sample_start script
echo "Navigating to $SAMPLE_APP directory and running sample_start script..."
cd "$SAMPLE_APP" || exit 1

if [ -f "./sample_start.sh" ]; then
    chmod +x ./sample_start.sh
    ./sample_start.sh "$@"
else
    echo "Error: sample_start.sh not found in $SAMPLE_APP directory."
    exit 1
fi
