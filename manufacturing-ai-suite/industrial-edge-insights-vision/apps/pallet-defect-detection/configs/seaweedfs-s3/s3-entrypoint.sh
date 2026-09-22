#!/bin/sh
# Renders the SeaweedFS S3 IAM identity config from template using the
# S3_STORAGE_USER/S3_STORAGE_PASS env vars, then starts the requested weed command.

set -e

sed -e "s/\${S3_STORAGE_USER}/${S3_STORAGE_USER}/g" \
    -e "s/\${S3_STORAGE_PASS}/${S3_STORAGE_PASS}/g" \
    /etc/seaweedfs/s3_config.json.template > /tmp/s3_config.json

exec weed "$@"
