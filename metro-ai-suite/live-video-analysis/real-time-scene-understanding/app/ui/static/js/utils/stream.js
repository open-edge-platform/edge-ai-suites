/* Copyright (C) 2026 Intel Corporation */
/* SPDX-License-Identifier: Apache-2.0 */

/**
 * Stream-domain formatting and normalization helpers.
 * Keeps stream controller logic focused on orchestration instead of text rules.
 */

function formatMetricNumber(value, digits = 1) {
    if (value === null || value === undefined || value === "") return "-";
    const num = Number(value);
    if (!Number.isFinite(num)) return "-";
    return num.toFixed(digits);
}

export function sanitizeStreamId(value) {
    return value
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9_-]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 48);
}

export function formatAlertPromptDetails(stream) {
    const promptText = String(stream.alert_prompt || "").trim();
    const compactPrompt = promptText.replace(/\s*\n\s*/g, " / ").replace(/\s+/g, " ");
    const preview = compactPrompt.length > 120 ? `${compactPrompt.slice(0, 117)}...` : compactPrompt;
    return preview
        ? `Alert Prompt: ${preview}`
        : "Alert Prompt: not provided";
}

const DECISION_RE = /decision\s*:\s*(yes|no)\b/i;
const DESCRIPTION_RE = /description\s*:\s*([\s\S]*)$/i;

/**
 * Split a VLM alert caption ("Decision: Yes/No\nDescription: ...") into its
 * parts. Falls back to treating the whole text as the description when it
 * doesn't match the expected shape (e.g. still loading, or a parse failure).
 */
export function parseAlertCaption(captionText) {
    const text = String(captionText || "").trim();
    if (!text) return { decision: null, description: "" };

    try {
        const parsed = JSON.parse(text);
        if (parsed && typeof parsed === "object") {
            const decision = String(parsed.decision || "").toLowerCase();
            const description = String(parsed.description || "").trim();
            if (decision === "yes" || decision === "no") {
                return { decision, description: description || text };
            }
        }
    } catch (_err) {
        // Captions normally use the formatted Decision/Description form.
    }

    const decisionMatch = DECISION_RE.exec(text);
    const descriptionMatch = DESCRIPTION_RE.exec(text);

    return {
        decision: decisionMatch ? decisionMatch[1].toLowerCase() : null,
        description: descriptionMatch ? descriptionMatch[1].trim() : text,
    };
}

export function isAlertDetected(captionText) {
    return parseAlertCaption(captionText).decision === "yes";
}

export function formatVlmMetrics(stream) {
    const ttft = formatMetricNumber(stream.ttft_ms);
    const tpot = formatMetricNumber(stream.tpot_ms);
    const throughput = formatMetricNumber(stream.throughput_tps);
    return `TTFT: ${ttft} ms | TPOT: ${tpot} ms | Throughput: ${throughput} tok/s`;
}

export function formatVlmResponse(stream) {
    const { description } = parseAlertCaption(stream.caption);
    return description || "Awaiting response...";
}

function formatHistoryLabel(index) {
    if (index === 0) return "Latest";
    return `latest - ${index}`;
}

function formatStreamSeconds(seconds) {
    const value = Number(seconds);
    if (!Number.isFinite(value) || value < 0) return "";
    const mins = Math.floor(value / 60);
    const rem = value - mins * 60;
    const secText = rem.toFixed(2).padStart(5, "0");
    return `${String(mins).padStart(2, "0")}:${secText}`;
}

export function formatVlmResponseHistory(stream, limit = 3) {
    const history = Array.isArray(stream.caption_history)
        ? stream.caption_history
            .map((entry, index) => {
                if (entry && typeof entry === "object") {
                    const raw = String(entry.response || "").trim();
                    if (!raw) return null;
                    const { decision, description } = parseAlertCaption(raw);
                    return {
                        label: formatHistoryLabel(index),
                        timeLabel: formatStreamSeconds(entry.playback_seconds),
                        text: description,
                        alert: decision === "yes",
                    };
                }

                const raw = String(entry || "").trim();
                if (!raw) return null;
                const { decision, description } = parseAlertCaption(raw);
                return {
                    label: formatHistoryLabel(index),
                    timeLabel: "",
                    text: description,
                    alert: decision === "yes",
                };
            })
            .filter(Boolean)
        : [];

    if (history.length > 0) {
        return history.slice(0, limit);
    }

    const latest = String(stream.caption || "").trim();
    if (!latest) return [];
    const { decision, description } = parseAlertCaption(latest);
    return [{ label: "Latest", timeLabel: "", text: description, alert: decision === "yes" }];
}
