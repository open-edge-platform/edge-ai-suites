#!/bin/bash

# Check if directory argument is provided
if [[ -z $1 ]]; then
    echo "Usage: $0 <directory>"
    exit 1
fi

DIRECTORY=$1

# Create directory if it doesn't exist
mkdir -p $DIRECTORY

# Array of download URLs obtained from Figshare
URLS=(
    "https://figshare.com/ndownloader/articles/22202866/versions/1"
)

# Loop to download each file
for url in "${URLS[@]}"; do
    filename=$(basename "$url")
    curl -o "$DIRECTORY/$filename" $url
done

# Unzip and delete all downloaded zip files
for file in "$DIRECTORY"/*.tar.zip; do
    unzip "$file" -d "$DIRECTORY" && rm "$file"
done

echo "Download, extraction, and cleanup complete."

