#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
#!/bin/sh

# Read the certificate files and export their contents as environment variables
export SERVER_CACERT=$(cat $GF_SERVER_CACERT)
export CLIENT_CERT=$(cat $GF_SERVER_CERT_FILE)
export CLIENT_KEY=$(cat $GF_SERVER_CERT_KEY)

# Start Grafana
/run.sh