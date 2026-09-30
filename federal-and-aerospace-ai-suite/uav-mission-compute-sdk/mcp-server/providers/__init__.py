# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from .dlstreamer import HANDLERS as dlstreamer_handlers
from .anomalib import HANDLERS as anomalib_handlers
from .edge_ai_suites import HANDLERS as edge_ai_suites_handlers
from .telemetry import HANDLERS as telemetry_handlers

PROVIDER_HANDLERS = {
    "dlstreamer": dlstreamer_handlers,
    "anomalib": anomalib_handlers,
    "edge_ai_suites": edge_ai_suites_handlers,
    "telemetry": telemetry_handlers,
    "mavlink": telemetry_handlers,
}
