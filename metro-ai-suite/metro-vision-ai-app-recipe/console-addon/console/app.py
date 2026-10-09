#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Entry point: composes the modules and serves the app."""

import os

from config import TLS_CERT, TLS_KEY, UI_PORT, app

# Imported for their side effects: registering routes on the shared app and
# starting MQTT ingestion.
import api        # noqa: F401,E402
import api_pipelines  # noqa: F401,E402
import whep_proxy  # noqa: F401,E402
import ingest  # noqa: F401,E402


if __name__ == "__main__":
    # TLS is only meaningful for the standalone deployment (no reverse proxy
    # in front of it); behind nginx the edge already terminates TLS, and
    # this process serves that upstream over plain HTTP.
    ssl_context = (TLS_CERT, TLS_KEY) if os.path.isfile(TLS_CERT) and os.path.isfile(TLS_KEY) else None
    app.run(host="0.0.0.0", port=UI_PORT, ssl_context=ssl_context, threaded=True)
