/* Copyright (C) 2026 Intel Corporation */
/* SPDX-License-Identifier: Apache-2.0 */

/**
 * Metrics feature controller.
 * Handles SSE metrics ingestion, chart rendering, and capability tooltips.
 */

import { getMetricsStreamUrl } from "../../config/runtime.js";
import { fetchSystemCapabilities } from "../../services/api.js";
import { buildHostSystemInfo } from "../../utils/capabilities.js";

const METRICS_HISTORY_LIMIT = 60;
const METRICS_MAX_RECONNECT_ATTEMPTS = 10;

export function createMetricsController(elements) {
    const {
        metricsConnection,
        cpuVal,
        ramVal,
        gpuVal,
        npuVal,
        hostCpuVal,
        hostRamVal,
        hostGpuVal,
        hostNpuVal,
        metricsCanvas,
    } = elements;

    const state = {
        source: null,
        reconnectTimer: null,
        reconnectAttempts: 0,
        history: [],
    };

    function setMetricsConnection(connected) {
        metricsConnection.textContent = connected ? "connected" : "disconnected";
        metricsConnection.className = connected
            ? "metrics-connection metrics-connection--ok"
            : "metrics-connection metrics-connection--idle";
    }

    function updateMetricValue(el, value) {
        el.textContent = value === null ? "-" : `${value.toFixed(1)}%`;
    }

    function updateSystemInfoValue(el, value) {
        if (!el) return;

        const normalized = typeof value === "string" && value.trim() ? value.trim() : "-";
        const isDetected = normalized !== "-";

        el.textContent = normalized;
        el.classList.add("system-status-value");
        el.classList.toggle("system-status-value--detected", isDetected);
        el.classList.toggle("system-status-value--missing", !isDetected);
    }

    function drawMetricLine(ctx, samples, key, color, left, right, top, bottom) {
        if (samples.length < 2) return;
        const xStep = (right - left) / Math.max(samples.length - 1, 1);
        let started = false;

        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;

        samples.forEach((sample, index) => {
            const value = sample[key];
            if (value === null || value === undefined) return;

            const x = left + index * xStep;
            const y = bottom - (Math.max(0, Math.min(100, value)) / 100) * (bottom - top);
            if (started) {
                ctx.lineTo(x, y);
            } else {
                ctx.moveTo(x, y);
                started = true;
            }
        });

        if (started) {
            ctx.stroke();
        }
    }

    function drawMetricsChart() {
        if (!metricsCanvas) return;

        const ctx = metricsCanvas.getContext("2d");
        if (!ctx) return;

        const cssWidth = metricsCanvas.clientWidth || 640;
        const cssHeight = 220;
        if (metricsCanvas.width !== cssWidth) metricsCanvas.width = cssWidth;
        if (metricsCanvas.height !== cssHeight) metricsCanvas.height = cssHeight;

        const width = metricsCanvas.width;
        const height = metricsCanvas.height;
        const leftPadding = 38;
        const rightPadding = 10;
        const topPadding = 12;
        const bottomPadding = 20;
        const plotLeft = leftPadding;
        const plotRight = width - rightPadding;
        const plotTop = topPadding;
        const plotBottom = height - bottomPadding;

        ctx.clearRect(0, 0, width, height);

        // Y-axis labels and horizontal grid (0-100%).
        ctx.font = "11px 'Segoe UI', sans-serif";
        ctx.fillStyle = "rgba(139, 148, 158, 0.9)";
        ctx.textAlign = "right";
        ctx.textBaseline = "middle";
        ctx.strokeStyle = "rgba(139, 148, 158, 0.2)";
        ctx.lineWidth = 1;

        for (let pct = 0; pct <= 100; pct += 10) {
            const y = plotBottom - (pct / 100) * (plotBottom - plotTop);
            ctx.beginPath();
            ctx.moveTo(plotLeft, y);
            ctx.lineTo(plotRight, y);
            ctx.stroke();
            ctx.fillText(String(pct), plotLeft - 6, y);
        }

        // Y-axis line.
        ctx.beginPath();
        ctx.moveTo(plotLeft, plotTop);
        ctx.lineTo(plotLeft, plotBottom);
        ctx.strokeStyle = "rgba(139, 148, 158, 0.28)";
        ctx.stroke();

        drawMetricLine(ctx, state.history, "cpu", "#1ad0ff", plotLeft, plotRight, plotTop, plotBottom);
        drawMetricLine(ctx, state.history, "ram", "#8ca0c2", plotLeft, plotRight, plotTop, plotBottom);
        drawMetricLine(ctx, state.history, "gpu", "#ffb347", plotLeft, plotRight, plotTop, plotBottom);
        drawMetricLine(ctx, state.history, "npu", "#b388ff", plotLeft, plotRight, plotTop, plotBottom);
    }

    function processMetrics(metrics) {
        let cpu = null;
        let ram = null;
        let npu = null;
        const gpuByDevice = new Map();

        function gpuDeviceId(labels) {
            if (labels.gpu_id !== undefined && labels.gpu_id !== null) return String(labels.gpu_id);
            if (labels.device !== undefined && labels.device !== null) return String(labels.device);
            if (labels.card !== undefined && labels.card !== null) return String(labels.card);
            return "0";
        }

        metrics.forEach((metric) => {
            const labels = metric.labels || {};
            if (metric.name === "cpu_usage_user") {
                if (labels.cpu === undefined || labels.cpu === "cpu-total") {
                    cpu = metric.value;
                }
            } else if (metric.name === "mem_used_percent") {
                ram = metric.value;
            } else if (metric.name === "gpu_engine_usage_usage") {
                if (!labels.engine) return;
                const id = gpuDeviceId(labels);
                const prev = gpuByDevice.get(id);
                const next = prev === undefined ? metric.value : Math.max(prev, metric.value);
                gpuByDevice.set(id, next);
            } else if (metric.name === "npu_utilization") {
                npu = metric.value;
            }
        });

        let gpu = null;
        if (gpuByDevice.size > 0) {
            gpu = Math.max(...Array.from(gpuByDevice.values()));
        }

        updateMetricValue(cpuVal, cpu);
        updateMetricValue(ramVal, ram);
        updateMetricValue(gpuVal, gpu);
        updateMetricValue(npuVal, npu);

        if (cpu !== null || ram !== null || gpu !== null || npu !== null) {
            state.history.push({ cpu, ram, gpu, npu });
            while (state.history.length > METRICS_HISTORY_LIMIT) {
                state.history.shift();
            }
            drawMetricsChart();
        }
    }

    async function loadSystemCapabilities() {
        const chips = Array.from(document.querySelectorAll(".metric-chip[data-chip]"));
        chips.forEach((chip) => chip.removeAttribute("title"));

        const capabilities = await fetchSystemCapabilities();
        const hostInfo = buildHostSystemInfo(capabilities);

        updateSystemInfoValue(hostCpuVal, hostInfo.cpuModel || "-");
        updateSystemInfoValue(hostRamVal, hostInfo.ramTotal || "-");
        updateSystemInfoValue(hostGpuVal, hostInfo.gpuModel || "-");
        updateSystemInfoValue(hostNpuVal, hostInfo.npuModel || "-");
    }

    function connectMetricsStream() {
        if (state.source && state.source.readyState !== EventSource.CLOSED) {
            return;
        }

        state.source = new EventSource(getMetricsStreamUrl());

        state.source.onopen = () => {
            state.reconnectAttempts = 0;
            setMetricsConnection(true);
        };

        state.source.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (!Array.isArray(data.metrics)) return;
                processMetrics(data.metrics);
            } catch (_err) {
                // Ignore malformed payload frames.
            }
        };

        state.source.onerror = () => {
            setMetricsConnection(false);
            if (state.source && state.source.readyState === EventSource.CLOSED) {
                state.source.close();
                state.source = null;
                if (state.reconnectAttempts < METRICS_MAX_RECONNECT_ATTEMPTS) {
                    state.reconnectAttempts += 1;
                    state.reconnectTimer = setTimeout(connectMetricsStream, 3000);
                }
            }
        };
    }

    function bindEvents() {
        window.addEventListener("resize", drawMetricsChart);
        window.addEventListener("beforeunload", () => {
            if (state.reconnectTimer) {
                clearTimeout(state.reconnectTimer);
            }
            if (state.source) {
                state.source.close();
            }
        });
    }

    function init() {
        drawMetricsChart();
        loadSystemCapabilities();
        connectMetricsStream();
        bindEvents();
    }

    return {
        init,
        drawMetricsChart,
    };
}
