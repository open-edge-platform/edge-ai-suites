// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//
// Connects to the metrics-manager SSE stream via nginx proxy and renders
// CPU, RAM, GPU utilization and CPU temperature on the dashboard.

(function () {
  "use strict";

  const METRICS_STREAM_URL = "/api/metrics/stream";
  const MAX_POINTS = 60;
  const RECONNECT_DELAY_MS = 3000;
  const MAX_RECONNECT_ATTEMPTS = 20;

  let reconnectAttempts = 0;
  let evtSource = null;
  let chart = null;

  // Chart data arrays
  const cpuData = [];
  const ramData = [];
  const gpuData = [];
  const npuData = [];
  const labels = [];

  function initChart() {
    const canvas = document.getElementById("metrics-chart");
    if (!canvas || typeof Chart === "undefined") return;

    chart = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "CPU %",
            data: cpuData,
            borderColor: "#4fc3f7",
            backgroundColor: "rgba(79,195,247,0.1)",
            tension: 0.3,
            fill: true,
            pointRadius: 0,
            borderWidth: 2,
          },
          {
            label: "RAM %",
            data: ramData,
            borderColor: "#81c784",
            backgroundColor: "rgba(129,199,132,0.1)",
            tension: 0.3,
            fill: true,
            pointRadius: 0,
            borderWidth: 2,
          },
          {
            label: "GPU %",
            data: gpuData,
            borderColor: "#ffb74d",
            backgroundColor: "rgba(255,183,77,0.1)",
            tension: 0.3,
            fill: true,
            pointRadius: 0,
            borderWidth: 2,
          },
          {
            label: "NPU %",
            data: npuData,
            borderColor: "#ce93d8",
            backgroundColor: "rgba(206,147,216,0.1)",
            tension: 0.3,
            fill: true,
            pointRadius: 0,
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 300 },
        scales: {
          x: { display: false },
          y: { min: 0, max: 100, ticks: { callback: (v) => v + "%" } },
        },
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12 } },
        },
        interaction: { intersect: false, mode: "index" },
      },
    });
  }

  function pushPoint(arr, value) {
    arr.push(value);
    if (arr.length > MAX_POINTS) arr.shift();
  }

  function processMetrics(metrics) {
    let cpu = null;
    let ram = null;
    let gpu = null;
    let npu = null;

    metrics.forEach(function (m) {
      const name = m.name;
      const mlabels = m.labels || {};
      const value = m.value;

      if (name === "cpu_usage_user" || name === "cpu_usage_idle") {
        if (name === "cpu_usage_idle" && (mlabels.cpu === undefined || mlabels.cpu === "cpu-total")) {
          cpu = 100 - value;
        } else if (name === "cpu_usage_user" && (mlabels.cpu === undefined || mlabels.cpu === "cpu-total")) {
          if (cpu === null) cpu = value;
        }
      }

      if (name === "mem_used_percent") {
        ram = value;
      }

      if (name === "gpu_engine_usage_usage") {
        if (gpu === null || value > gpu) gpu = value;
      }

      if (name === "npu_utilization") {
        npu = value;
      }
    });

    // Update stat values
    const cpuEl = document.getElementById("metric-cpu");
    const ramEl = document.getElementById("metric-ram");
    const gpuEl = document.getElementById("metric-gpu");
    const npuEl = document.getElementById("metric-npu");

    if (cpu !== null && cpuEl) cpuEl.textContent = cpu.toFixed(1) + "%";
    if (ram !== null && ramEl) ramEl.textContent = ram.toFixed(1) + "%";
    if (gpu !== null && gpuEl) gpuEl.textContent = gpu.toFixed(1) + "%";
    if (npu !== null && npuEl) npuEl.textContent = npu.toFixed(1) + "%";

    // Update chart
    if (chart) {
      const now = new Date();
      labels.push(now.toLocaleTimeString());
      if (labels.length > MAX_POINTS) labels.shift();

      pushPoint(cpuData, cpu !== null ? cpu : cpuData[cpuData.length - 1] || 0);
      pushPoint(ramData, ram !== null ? ram : ramData[ramData.length - 1] || 0);
      pushPoint(gpuData, gpu !== null ? gpu : gpuData[gpuData.length - 1] || 0);
      pushPoint(npuData, npu !== null ? npu : npuData[npuData.length - 1] || 0);

      chart.update("none");
    }
  }

  function setStatus(msg, isError) {
    const el = document.getElementById("metrics-status");
    if (el) {
      el.textContent = msg;
      el.className = "metrics-status" + (isError ? " metrics-error" : "");
    }
  }

  function connect() {
    if (evtSource) {
      evtSource.close();
      evtSource = null;
    }

    setStatus("Connecting to metrics stream…", false);
    evtSource = new EventSource(METRICS_STREAM_URL);

    evtSource.onopen = function () {
      reconnectAttempts = 0;
      setStatus("", false);
      const el = document.getElementById("metrics-status");
      if (el) el.style.display = "none";
    };

    evtSource.onmessage = function (event) {
      try {
        const data = JSON.parse(event.data);
        if (data.metrics && Array.isArray(data.metrics)) {
          processMetrics(data.metrics);
        }
      } catch (e) {
        console.debug("Metrics parse error:", e);
      }
    };

    evtSource.onerror = function () {
      evtSource.close();
      evtSource = null;
      reconnectAttempts++;

      if (reconnectAttempts <= MAX_RECONNECT_ATTEMPTS) {
        setStatus("Metrics stream disconnected. Reconnecting…", true);
        setTimeout(connect, RECONNECT_DELAY_MS);
      } else {
        setStatus("Metrics stream unavailable.", true);
      }
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initChart();
      connect();
    });
  } else {
    initChart();
    connect();
  }
})();
