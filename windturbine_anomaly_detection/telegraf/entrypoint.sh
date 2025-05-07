#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
#!/bin/sh
export DEBUG_MODE=$( [ \"$LOG_LEVEL\" = \"DEBUG\" ] && echo true || echo false )

telegraf --config ${TELEGRAF_CONFIG_PATH} --input-filter ${TELEGRAF_INPUT_PLUGIN}