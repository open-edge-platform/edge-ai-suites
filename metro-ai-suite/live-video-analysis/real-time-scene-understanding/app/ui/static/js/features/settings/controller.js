/* Copyright (C) 2026 Intel Corporation */
/* SPDX-License-Identifier: Apache-2.0 */

/**
 * Settings feature controller.
 * Hydrates runtime settings and controls settings panel interactions.
 */

import { readRuntimeConfigBool, readRuntimeConfigString } from "../../config/runtime.js";

export function initSettingsMenu(elements) {
    const {
        settingsToggle,
        settingsPanel,
        systemInfoToggle,
        systemInfoPanel,
        settingsVlmModel,
        settingsVlmDevice,
        settingsVlmMaxTokens,
        settingsDeepAnalyzerGroup,
        settingsDeepModel,
        settingsDeepDevice,
        settingsDeepMaxFrames,
        settingsDeepMaxTokens,
    } = elements;

    const hasSettingsPopover = Boolean(settingsToggle && settingsPanel);
    const hasSystemInfoPopover = Boolean(systemInfoToggle && systemInfoPanel);
    if (!hasSettingsPopover && !hasSystemInfoPopover) return;

    const setSettingsOpen = (open) => {
        if (!hasSettingsPopover) return;

        settingsPanel.classList.toggle("settings-panel--hidden", !open);
        settingsToggle.setAttribute("aria-expanded", String(open));
    };

    const setSystemInfoOpen = (open) => {
        if (!hasSystemInfoPopover) return;

        systemInfoPanel.classList.toggle("settings-panel--hidden", !open);
        systemInfoToggle.setAttribute("aria-expanded", String(open));
    };

    if (settingsVlmModel) {
        settingsVlmModel.textContent = readRuntimeConfigString("alertVlmModel");
    }
    if (settingsVlmDevice) {
        settingsVlmDevice.textContent = readRuntimeConfigString("alertVlmDevice");
    }
    if (settingsVlmMaxTokens) {
        settingsVlmMaxTokens.textContent = readRuntimeConfigString("alertVlmMaxTokens");
    }

    const deepAnalyzerEnabled = readRuntimeConfigBool("deepAnalyzerEnabled", false);
    if (settingsDeepAnalyzerGroup) {
        settingsDeepAnalyzerGroup.hidden = !deepAnalyzerEnabled;
    }

    if (deepAnalyzerEnabled) {
        if (settingsDeepModel) {
            settingsDeepModel.textContent = readRuntimeConfigString("deepAnalyzerModel");
        }
        if (settingsDeepDevice) {
            settingsDeepDevice.textContent = readRuntimeConfigString("deepAnalyzerDevice");
        }
        if (settingsDeepMaxFrames) {
            settingsDeepMaxFrames.textContent = readRuntimeConfigString("deepAnalyzerMaxFrames");
        }
        if (settingsDeepMaxTokens) {
            settingsDeepMaxTokens.textContent = readRuntimeConfigString("deepAnalyzerMaxTokens");
        }
    }

    if (hasSettingsPopover) {
        settingsToggle.addEventListener("click", (event) => {
            event.stopPropagation();
            const willOpen = settingsPanel.classList.contains("settings-panel--hidden");
            setSettingsOpen(willOpen);
            if (willOpen) setSystemInfoOpen(false);
        });

        settingsPanel.addEventListener("click", (event) => {
            event.stopPropagation();
        });
    }

    if (hasSystemInfoPopover) {
        systemInfoToggle.addEventListener("click", (event) => {
            event.stopPropagation();
            const willOpen = systemInfoPanel.classList.contains("settings-panel--hidden");
            setSystemInfoOpen(willOpen);
            if (willOpen) setSettingsOpen(false);
        });

        systemInfoPanel.addEventListener("click", (event) => {
            event.stopPropagation();
        });
    }

    document.addEventListener("click", () => {
        setSettingsOpen(false);
        setSystemInfoOpen(false);
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            setSettingsOpen(false);
            setSystemInfoOpen(false);
        }
    });
}
