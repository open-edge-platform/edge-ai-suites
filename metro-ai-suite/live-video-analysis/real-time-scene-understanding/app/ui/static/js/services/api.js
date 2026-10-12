/* Copyright (C) 2026 Intel Corporation */
/* SPDX-License-Identifier: Apache-2.0 */

/**
 * Network service layer for REST endpoints.
 * Encapsulates fetch calls, payload normalization, and error extraction.
 */

import { getCapabilitiesUrl } from "../config/runtime.js";
import { buildCapabilitiesFallback, enrichCapabilities } from "../utils/capabilities.js";

const ALERT_PAGE_SIZE = 20;

async function parseErrorDetail(resp, fallback) {
    let detail = fallback;
    try {
        const payload = await resp.json();
        if (payload && payload.detail) {
            detail = String(payload.detail);
        }
    } catch (_err) {
        // keep default message
    }
    return detail;
}

export async function fetchStreams() {
    const res = await fetch("/api/streams");
    const data = await res.json();
    return Array.isArray(data.streams) ? data.streams : [];
}

export async function addStream({ streamId, url, alertPrompt, deepAnalyzerPrompt }) {
    const addResp = await fetch("/api/streams", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            stream_id: streamId,
            url,
            alert_prompt: alertPrompt,
            deep_analyzer_prompt: deepAnalyzerPrompt,
        }),
    });

    if (!addResp.ok) {
        const detail = await parseErrorDetail(addResp, "Failed to add stream.");
        throw new Error(detail);
    }
}

export async function deleteStream(streamId) {
    const resp = await fetch(`/api/streams/${encodeURIComponent(streamId)}`, { method: "DELETE" });
    if (!resp.ok && resp.status !== 404) {
        const detail = await parseErrorDetail(resp, "Failed to stop stream.");
        throw new Error(detail);
    }
}

export async function fetchAlertPage(streamId, offset) {
    const resp = await fetch(
        `/api/streams/${encodeURIComponent(streamId)}/alerts?limit=${ALERT_PAGE_SIZE}&offset=${offset}`
    );
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    return {
        alerts: Array.isArray(data.alerts) ? data.alerts : [],
        total: Number(data.total) || 0,
    };
}

export async function fetchAlertDetail(streamId, frameId) {
    const resp = await fetch(`/api/streams/${encodeURIComponent(streamId)}/alerts/${encodeURIComponent(frameId)}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
}

export async function fetchSystemCapabilities() {
    try {
        const resp = await fetch(getCapabilitiesUrl(), { method: "GET" });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

        const data = await resp.json();
        return enrichCapabilities(data);
    } catch (_err) {
        return buildCapabilitiesFallback();
    }
}
