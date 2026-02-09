#!/bin/sh
#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Script to generate S3 config and create default buckets in SeaweedFS before starting S3 service

echo "Generating S3 config from template..."

sed -e "s/\${S3_STORAGE_USER}/${S3_STORAGE_USER}/g" \
    -e "s/\${S3_STORAGE_PASS}/${S3_STORAGE_PASS}/g" \
    /etc/seaweedfs/s3_config.json.template > /tmp/s3_config.json
echo "S3 config generated with user: ${S3_STORAGE_USER}"

# Wait and check if filer is accessible
echo "Checking if filer is accessible..."
RETRY_COUNT=0
MAX_RETRIES=30

until [ $RETRY_COUNT -ge $MAX_RETRIES ]; do
    if curl -s --connect-timeout 3 --max-time 5 http://seaweedfs-filer:8888/ > /dev/null 2>&1; then
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

for bucket in $(echo "$DEFAULT_BUCKETS" | tr ',' ' '); do
    echo "Creating bucket: $bucket"
    
    RESULT=$(curl -s -w "\n%{http_code}" -X POST "http://seaweedfs-filer:8888/buckets/$bucket/?op=mkdir" 2>&1)
    HTTP_CODE=$(echo "$RESULT" | tail -n1)
    if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "200" ]; then
        echo "✓ Bucket '$bucket' created successfully"
    else
        echo "ℹ Bucket '$bucket' may already exist or created (HTTP: $HTTP_CODE)"
    fi
done

echo "Bucket initialization complete. Starting S3 service..."
# Execute the SeaweedFS binary with the provided command arguments
exec weed "$@"
