#!/bin/bash

# Copyright (C) 2026 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials,
# and your use of them is governed by the express license under which they
# were provided to you ("License"). Unless the License provides otherwise,
# you may not use, modify, copy, publish, distribute, disclose or transmit
# this software or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express
# or implied warranties, other than those that are expressly stated in the License.

# Generates the Node-RED adminAuth credentials required by settings.js.
# Kept separate from generate_secrets.sh (and self-guarded) so it can also
# backfill this secret on deployments that already ran generate_secrets.sh
# before adminAuth was introduced, without touching their existing certs/passwords.

EXEC_PATH="$(dirname "$(readlink -f "$0")")"
SECRETSDIR="$EXEC_PATH/../secrets"

if [ -f "$SECRETSDIR/nodered/nodered-admin-password" ]; then
  exit 0
fi

echo Generating Node-RED admin credentials
mkdir -p "$SECRETSDIR/nodered"
NODERED_PASS=$(openssl rand -base64 12)
echo -n "admin" > "$SECRETSDIR/nodered/nodered-admin-username"
echo -n "$NODERED_PASS" > "$SECRETSDIR/nodered/nodered-admin-password"
chmod 0600 "$SECRETSDIR/nodered/nodered-admin-password"
