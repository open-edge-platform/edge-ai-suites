/* Copyright (C) 2026 Intel Corporation */
/* SPDX-License-Identifier: Apache-2.0 */

/**
 * Central DOM element registry.
 * Exposes stable references used across feature controllers.
 */

export const elements = {
    statusPill: document.getElementById("status-pill"),
    rtspForm: document.getElementById("rtsp-form"),
    rtspInput: document.getElementById("rtsp-url"),
    streamIdInput: document.getElementById("stream-id"),
    alertPromptInput: document.getElementById("alert-prompt"),
    deepAnalyzerPromptInput: document.getElementById("deep-analyzer-prompt"),
    rtspSubmit: document.getElementById("rtsp-submit"),
    rtspMessage: document.getElementById("rtsp-message"),
    streamsGrid: document.getElementById("streams-grid"),
    streamsEmpty: document.getElementById("streams-empty"),

    settingsToggle: document.getElementById("settings-toggle"),
    settingsPanel: document.getElementById("settings-panel"),
    systemInfoToggle: document.getElementById("system-info-toggle"),
    systemInfoPanel: document.getElementById("system-info-panel"),
    settingsVlmModel: document.getElementById("settings-vlm-model"),
    settingsVlmDevice: document.getElementById("settings-vlm-device"),
    settingsVlmMaxTokens: document.getElementById("settings-vlm-max-tokens"),
    settingsDeepAnalyzerGroup: document.getElementById("settings-deep-analyzer-group"),
    settingsDeepModel: document.getElementById("settings-deep-model"),
    settingsDeepDevice: document.getElementById("settings-deep-device"),
    settingsDeepMaxFrames: document.getElementById("settings-deep-max-frames"),
    settingsDeepMaxTokens: document.getElementById("settings-deep-max-tokens"),

    alertDrawer: document.getElementById("alert-drawer"),
    alertDrawerStream: document.getElementById("alert-drawer-stream"),
    alertDrawerList: document.getElementById("alert-drawer-list"),
    alertDrawerStatus: document.getElementById("alert-drawer-status"),
    alertDrawerMore: document.getElementById("alert-drawer-more"),
    alertDrawerClose: document.getElementById("alert-drawer-close"),

    alertModal: document.getElementById("alert-modal"),
    alertModalVideo: document.getElementById("alert-modal-video"),
    alertModalMeta: document.getElementById("alert-modal-meta"),
    alertModalSummary: document.getElementById("alert-modal-summary"),
    alertModalStatus: document.getElementById("alert-modal-status"),
    alertModalClose: document.getElementById("alert-modal-close"),

    metricsConnection: document.getElementById("metrics-connection"),
    cpuVal: document.getElementById("cpu-val"),
    ramVal: document.getElementById("ram-val"),
    gpuVal: document.getElementById("gpu-val"),
    npuVal: document.getElementById("npu-val"),
    hostCpuVal: document.getElementById("host-cpu-val"),
    hostRamVal: document.getElementById("host-ram-val"),
    hostGpuVal: document.getElementById("host-gpu-val"),
    hostNpuVal: document.getElementById("host-npu-val"),
    metricsCanvas: document.getElementById("metrics-canvas"),
};

export function getMetricChips() {
    return Array.from(document.querySelectorAll(".metric-chip[data-chip]"));
}
