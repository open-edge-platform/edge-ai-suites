#!/bin/sh
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
set -e

# Ensure the whisper cache bind-mount directory is owned by the app user.
# This runs as root so it works regardless of the host directory's initial ownership.
mkdir -p /app/.cache/whisper
chown -R app:root /app/.cache/whisper

exec gosu app "$@"
