/* Copyright (C) 2026 Intel Corporation */
/* SPDX-License-Identifier: Apache-2.0 */

/**
 * Runtime configuration and URL resolution helpers.
 * Normalizes access to window-provided deployment settings.
 */

function getRuntimeConfig() {
    return window.RUNTIME_CONFIG || {};
}

function resolveProtocol() {
    return window.location.protocol === "https:" ? "https:" : "http:";
}

function resolveHost() {
    return window.location.hostname;
}

export function readRuntimeConfigString(key, fallback = "Not configured") {
    const value = getRuntimeConfig()[key];
    if (value === null || value === undefined) return fallback;
    const text = String(value).trim();
    return text || fallback;
}

export function readRuntimeConfigBool(key, fallback = false) {
    const value = getRuntimeConfig()[key];
    if (value === null || value === undefined) return fallback;
    if (typeof value === "boolean") return value;

    const normalized = String(value).trim().toLowerCase();
    if (["1", "true", "yes", "on"].includes(normalized)) return true;
    if (["0", "false", "no", "off"].includes(normalized)) return false;
    return fallback;
}

export function resolveWebRtcBase() {
    const configured = (getRuntimeConfig().webrtcSignalingUrl || "").trim();
    if (configured) {
        return configured.replace(/\/+$/, "");
    }

    const protocol = resolveProtocol();
    const host = resolveHost();
    const port = String(getRuntimeConfig().webrtcSignalingPort || 8889);
    return `${protocol}//${host}:${port}`;
}

export function whepUrl(streamId) {
    return `${resolveWebRtcBase()}/${encodeURIComponent(streamId)}/whep`;
}

export function getMetricsStreamUrl() {
    if (window.METRICS_SERVICE_URL) {
        return window.METRICS_SERVICE_URL;
    }

    const protocol = resolveProtocol();
    const host = resolveHost();
    const port = getRuntimeConfig().metricsServicePort || window.METRICS_SERVICE_PORT || "9090";
    return `${protocol}//${host}:${port}/metrics/stream`;
}

export function getCapabilitiesUrl() {
    const protocol = resolveProtocol();
    const host = resolveHost();
    const port = getRuntimeConfig().metricsServicePort || window.METRICS_SERVICE_PORT || "9090";
    return `${protocol}//${host}:${port}/api/v1/capabilities?profile=minimal`;
}
