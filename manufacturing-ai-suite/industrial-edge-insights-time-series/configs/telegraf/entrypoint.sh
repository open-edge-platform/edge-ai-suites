#!/bin/sh
#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
if [ "$LOG_LEVEL" = "DEBUG" ]; then
	DEBUG_MODE=true
else
	DEBUG_MODE=false
fi
export DEBUG_MODE

telegraf --non-strict-env-handling --config "${TELEGRAF_CONFIG_PATH}" --input-filter "${TELEGRAF_INPUT_PLUGIN}"
