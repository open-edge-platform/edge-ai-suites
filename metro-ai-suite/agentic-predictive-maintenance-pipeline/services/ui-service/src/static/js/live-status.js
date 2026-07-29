// Copyright (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//
// Polls /api/status and patches the dashboard in place so detection counts,
// run history, and the current run phase (detecting -> reasoning -> completed)
// stay current without a full page reload.

const POLL_INTERVAL_MS = 3000;

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderDetectionsRows(byClass) {
  if (!byClass || byClass.length === 0) return "";
  return byClass
    .map(
      (cls) => `
      <tr>
        <td><span class="label-badge">${escapeHtml(cls.label)}</span></td>
        <td>${cls.count}</td>
        <td>${Number(cls.avg_confidence).toFixed(3)}</td>
        <td>${Number(cls.max_confidence).toFixed(3)}</td>
      </tr>`
    )
    .join("");
}

function statusBadgeHtml(run) {
  const suffix = run.status === "running" && run.phase ? ` — ${escapeHtml(run.phase)}` : "";
  return `<span class="status-badge status-${escapeHtml(run.status)}">${escapeHtml(run.status)}${suffix}</span>`;
}

function runActionHtml(run) {
  if (run.status === "completed") return `<a href="/results/${run.run_id}">View Results</a>`;
  if (run.status === "running") return `<a href="/results/${run.run_id}">Waiting…</a>`;
  return `<a href="/results/${run.run_id}">View Error</a>`;
}

function renderRunsRows(runs) {
  if (!runs || runs.length === 0) return "";
  return runs
    .map(
      (run) => `
      <tr>
        <td><code title="${run.run_id}">${run.run_id.slice(0, 8)}…</code></td>
        <td>${statusBadgeHtml(run)}</td>
        <td>${runActionHtml(run)}</td>
      </tr>`
    )
    .join("");
}

function phaseHintText(activeRun) {
  if (!activeRun) return "Ready — click to run inference + agent analysis.";
  if (activeRun.phase === "detecting") return "Running DL Streamer inference over the video…";
  if (activeRun.phase === "reasoning") return "Detection complete — agents are analyzing the results…";
  return "Run in progress…";
}

async function pollStatus() {
  try {
    const res = await fetch("/api/status", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();

    const detTotal = document.getElementById("stat-detections");
    const completed = document.getElementById("stat-runs-completed");
    const running = document.getElementById("stat-runs-running");
    if (detTotal) detTotal.textContent = data.total_detections;
    if (completed) completed.textContent = data.runs_completed;
    if (running) running.textContent = data.runs_running;

    const detTbody = document.getElementById("detections-tbody");
    const detTable = document.getElementById("detections-table");
    const detEmpty = document.getElementById("detections-empty");
    if (detTbody) {
      detTbody.innerHTML = renderDetectionsRows(data.by_class);
      if (data.by_class && data.by_class.length > 0) {
        if (detTable) detTable.style.display = "";
        if (detEmpty) detEmpty.style.display = "none";
      }
    }

    const runsTbody = document.getElementById("runs-tbody");
    const runsTable = document.getElementById("runs-table");
    const runsEmpty = document.getElementById("runs-empty");
    if (runsTbody) {
      runsTbody.innerHTML = renderRunsRows(data.recent_runs);
      if (data.recent_runs && data.recent_runs.length > 0) {
        if (runsTable) runsTable.style.display = "";
        if (runsEmpty) runsEmpty.style.display = "none";
      }
    }

    const banner = document.getElementById("pipeline-live-banner");
    const bannerText = document.getElementById("pipeline-live-text");
    if (banner && bannerText) {
      const isActive = !!data.active_run;
      banner.classList.toggle("live-on", isActive);
      banner.classList.toggle("live-off", !isActive);
      bannerText.textContent = isActive
        ? `Pipeline: RUNNING (${data.active_run.phase})`
        : "Pipeline: IDLE";
    }

    const runBtn = document.getElementById("run-pipeline-btn");
    if (runBtn) {
      runBtn.disabled = !!data.active_run;
      runBtn.textContent = data.active_run ? "▶ Running…" : "▶ Run Pipeline";
    }

    const phaseHint = document.getElementById("run-phase-hint");
    if (phaseHint) phaseHint.textContent = phaseHintText(data.active_run);
  } catch (err) {
    // Network hiccup — keep the last known state, next poll will retry.
    console.debug("Live status poll failed:", err);
  }
}

pollStatus();
setInterval(pollStatus, POLL_INTERVAL_MS);
