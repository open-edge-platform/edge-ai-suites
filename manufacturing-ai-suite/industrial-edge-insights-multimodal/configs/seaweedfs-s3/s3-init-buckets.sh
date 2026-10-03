#!/bin/sh
#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Script to generate S3 config and create default buckets in SeaweedFS before starting S3 service

set -eu

WEED_CONFIG_DIR="/etc/seaweedfs"
WEED_MASTER_ADDRESS="${WEED_MASTER_ADDRESS:-seaweedfs-master:9333}"
WEED_FILER_ADDRESS="${WEED_FILER_ADDRESS:-seaweedfs-filer:8888}"

for arg in "$@"; do
    case "$arg" in
        -config_dir=*)
            WEED_CONFIG_DIR="${arg#-config_dir=}"
            ;;
    esac
done

echo "Generating S3 config from template..."

sed -e "s/\${S3_STORAGE_USER}/${S3_STORAGE_USER}/g" \
    -e "s/\${S3_STORAGE_PASS}/${S3_STORAGE_PASS}/g" \
    "${WEED_CONFIG_DIR}/s3_config.json.template" > /tmp/s3_config.json
echo "S3 config generated with user: ${S3_STORAGE_USER}"

# Wait and check if filer is accessible
echo "Checking if filer is accessible..."
RETRY_COUNT=0
MAX_RETRIES=30

until [ $RETRY_COUNT -ge $MAX_RETRIES ]; do
    if curl -s --connect-timeout 3 --max-time 5 "http://${WEED_FILER_ADDRESS}/healthz" > /dev/null 2>&1 \
        || curl -s --connect-timeout 3 --max-time 5 "http://${WEED_FILER_ADDRESS}/" > /dev/null 2>&1; then
        echo "✓ Filer is accessible!"
        break
    fi
    echo "Filer not accessible yet, waiting... (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)"
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 2
done

if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "⚠ Warning: Filer check timed out. Attempting bucket creation anyway..."
fi

# Create default buckets using the filer API
DEFAULT_BUCKETS="${DEFAULT_S3_BUCKETS:-dlstreamer-pipeline-results}"
# Optional TTL for all default buckets, e.g. 10m, 1h, 7d
DEFAULT_S3_BUCKET_TTL="${S3_BUCKET_TTL:-30m}"

run_weed_shell() {
    printf '%s\n' "$1" | weed "-config_dir=${WEED_CONFIG_DIR}" shell -master="$WEED_MASTER_ADDRESS" -filer="$WEED_FILER_ADDRESS"
}

OLD_IFS=$IFS
IFS=,
set -- $DEFAULT_BUCKETS
IFS=$OLD_IFS

for bucket in "$@"; do
    bucket=$(printf '%s' "$bucket" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [ -n "$bucket" ] || continue
    case "$bucket" in
        *[[:space:]]*)
            echo "✗ Bucket name '$bucket' is invalid: whitespace is not allowed"
            exit 1
            ;;
    esac

    echo "Creating bucket: $bucket"

    CREATE_BUCKET_CMD="s3.bucket.create -name=$bucket"
    if CREATE_BUCKET_OUTPUT=$(run_weed_shell "$CREATE_BUCKET_CMD" 2>&1); then
        echo "✓ Bucket '$bucket' created successfully"
    elif printf '%s' "$CREATE_BUCKET_OUTPUT" | grep -qi "already exists"; then
        echo "ℹ Bucket '$bucket' already exists"
    else
        echo "✗ Failed to create bucket '$bucket'"
        echo "$CREATE_BUCKET_OUTPUT"
        exit 1
    fi

    if [ -n "$DEFAULT_S3_BUCKET_TTL" ]; then
        LOCATION_PREFIX="/buckets/$bucket/"
        FS_CONFIG_CMD="fs.configure -locationPrefix=$LOCATION_PREFIX -ttl=$DEFAULT_S3_BUCKET_TTL -apply"
        echo "Applying TTL '$DEFAULT_S3_BUCKET_TTL' to path '$LOCATION_PREFIX'"

        if FS_CONFIG_OUTPUT=$(run_weed_shell "$FS_CONFIG_CMD" 2>&1); then
            echo "✓ TTL configured for bucket '$bucket'"
        else
            echo "⚠ Failed to configure TTL for bucket '$bucket'"
            echo "$FS_CONFIG_OUTPUT"
        fi
    fi
done

echo "Bucket initialization complete. Starting S3 service..."
# Execute the SeaweedFS binary with the provided command arguments
exec weed "$@"
