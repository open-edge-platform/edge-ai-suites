/* Copyright (C) 2026 Intel Corporation */
/* SPDX-License-Identifier: Apache-2.0 */

/**
 * App entrypoint.
 * Wires feature controllers and starts the UI.
 */

import { elements } from "./dom/elements.js";
import { createAlertsController } from "./features/alerts/controller.js";
import { createMetricsController } from "./features/metrics/controller.js";
import { initSettingsMenu } from "./features/settings/controller.js";
import { createStreamsController } from "./features/streams/controller.js";

function bootstrap() {
    const alertsController = createAlertsController(elements);
    const metricsController = createMetricsController(elements);
    const streamsController = createStreamsController(elements, {
        openAlertDrawer: alertsController.openAlertDrawer,
    });

    alertsController.bindEvents();
    metricsController.init();
    initSettingsMenu(elements);
    streamsController.init();
}

bootstrap();