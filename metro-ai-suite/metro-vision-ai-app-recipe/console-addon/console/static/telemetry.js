// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//
// Telemetry polling, per-stream cards and utilisation gauges.
// FRONTEND-SPEC.md part B sections B5-B6, E and G.

window.Console = window.Console || {};

(function (C) {
  "use strict";

  function byId(id) { return document.getElementById(id); }

  function fmtNum(v, suffix) {
    if (v === null || v === undefined || isNaN(v)) { return "n/a"; }
    return (Math.round(v * 10) / 10) + (suffix || "");
  }

  function fmtMem(used, total) {
    if (!used && !total) { return ""; }
    var g = function (b) { return (b / (1024 * 1024 * 1024)).toFixed(1); };
    if (used && total) { return g(used) + "/" + g(total) + " GB"; }
    return used ? g(used) + " GB" : "";
  }

  // A running pipeline that returns nothing is not the same as a dead one.
  // Saying so prevents an incompatible model reading as a dashboard fault.
  function healthNote(s) {
    if (s.detection_state === "no-data") {
      return "no metadata received";
    }
    if (s.detection_state === "no-detections") {
      return "pipeline running, model returning no detections";
    }
    return "";
  }

  function escapeHtml(t) {
    return String(t).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  // Render the per-object loiter table beneath a panel's video.
  C.renderPanelAnalytics = function (peerId, s) {
    var el = C.panelEl(peerId);
    if (!el) { return; }
    var stats = el.querySelector(".p-stats");
    var tbody = el.querySelector(".p-loiter tbody");
    var empty = el.querySelector(".p-empty-rows");
    if (!stats || !tbody) { return; }
    var n = function (v, suf) { return fmtNum(v, suf); };
    stats.innerHTML =
      '<span><b>' + n(s.fps) + "</b> fps</span>" +
      "<span><b>" + (s.object_count || 0) + "</b> objects</span>" +
      "<span><b>" + n(s.max_dwell_s, "s") + "</b> max dwell</span>" +
      "<span><b>" + (s.loiter_count || 0) + "</b> loiter</span>";
    var rows = s.objects || [];
    tbody.innerHTML = rows.map(function (r) {
      var cls = r.status === "Loitering" ? ' class="row-loiter"' : "";
      return "<tr" + cls + "><td>" + escapeHtml(r.id) + "</td><td>" + escapeHtml(r.label) +
        "</td><td>" + escapeHtml(r.zone) + "</td><td>" + escapeHtml(r.status) + "</td><td>" + escapeHtml(r.entry_time) +
        "</td><td>" + n(r.dwell_s) + "</td></tr>";
    }).join("");
    if (empty) { empty.style.display = rows.length ? "none" : "block"; }
  };



  function renderStreams(streams) {
    streams.forEach(function (s) {
      // Rebuild a panel for any session the page does not know about, so a
      // refresh reattaches to streams that are still running. The session
      // only carries the raw model id, never the operator-facing label
      // Start shows, so look that label up from the already-loaded model
      // list rather than printing the id verbatim.
      if (!C.panels[s.peer_id]) {
        var modelLabel = (C.modelLabel ? C.modelLabel(s.model) : s.model) || "?";
        C.createPanel({
          peer_id: s.peer_id,
          whep_url: "whep/" + s.peer_id,
          title: modelLabel + " \u00b7 " + (s.device || "?"),
          zone: s.zone,
        });
        C.panels[s.peer_id].settled = true;
      }
      // The full per-object table lives beneath its own stream window.
      C.renderPanelAnalytics(s.peer_id, s);
      // Keep the panel's zone rectangle aligned with what the server enforces.
      if (s.zone) { C.setPanelZone(s.peer_id, s.zone); }
      var note = healthNote(s);
      if (note && C.panels[s.peer_id]) {
        C.setPanelStatus(s.peer_id, "streaming", note);
      }
    });
    C.updateEmptyState();
  }

  function pollEvents() {
    C.apiGet("api/events").then(function (d) {
      var streams = (d && d.streams) || [];
      // Drop panels the server no longer knows about, so a stopped or
      // aborted pipeline cannot linger as a frozen panel.
      var live = {};
      streams.forEach(function (s) { live[s.peer_id] = true; });
      Object.keys(C.panels).forEach(function (pid) {
        if (!live[pid] && C.panels[pid].settled) {
          C.removePanel(pid);
        }
        C.panels[pid].settled = true;
      });
      renderStreams(streams);
    }).catch(function () { /* transient */ });
  }

  function setGauge(key, percent, sub) {
    var g = document.querySelector('.gauge[data-key="' + key + '"]');
    if (!g) { return; }
    var bar = g.querySelector(".bar i");
    var val = g.querySelector(".g-val");
    var subEl = g.querySelector(".g-sub");
    if (percent === null || percent === undefined || isNaN(percent)) {
      val.textContent = "n/a";
      bar.style.width = "0%";
    } else {
      var p = Math.max(0, Math.min(100, percent));
      val.textContent = Math.round(p) + "%";
      bar.style.width = p + "%";
    }
    if (subEl) { subEl.textContent = sub || ""; }
  }

  function engineSub(gpu) {
    var e = gpu && gpu.engines;
    var parts = [];
    if (e) {
      // engines holds raw 0-1 ratios, not percentages; rounding before
      // scaling made every engine but the busiest read as 0.
      Object.keys(e).sort().forEach(function (k) {
        var v = e[k];
        if (v !== null && v !== undefined) { parts.push(k + " " + Math.round(v * 100)); }
      });
    }
    var mem = fmtMem(gpu && gpu.mem_used_bytes, gpu && gpu.mem_total_bytes);
    return [parts.join(" \u00b7 "), mem].filter(Boolean).join("  ");
  }

  function pollMetrics() {
    C.apiGet("api/metrics").then(function (m) {
      if (!m) { return; }
      var cpu = m.cpu || {}, gpu = m.gpu || {}, npu = m.npu || {}, mem = m.mem || {};
      setGauge("cpu", cpu.percent, cpu.freq_mhz ? Math.round(cpu.freq_mhz) + " MHz" : "");
      setGauge("gpu", gpu.percent, engineSub(gpu));
      setGauge("npu", npu.percent, fmtMem(npu.mem_used_bytes, npu.mem_total_bytes));
      setGauge("mem", mem.percent, fmtMem(mem.used_bytes, mem.total_bytes));
    }).catch(function () { /* transient */ });
  }

  function pollHealth() {
    C.apiGet("api/health").then(function (h) {
      var el = byId("connState");
      if (!el || !h) { return; }
      var ok = h.pipeline_server_reachable;
      el.textContent = "DLSPS: " + (ok ? "connected" : "unreachable") +
        (h.mqtt_connected ? " \u00b7 MQTT ok" : " \u00b7 MQTT down");
      el.className = "conn " + (ok ? "conn-ok" : "conn-bad");
    }).catch(function () { /* transient */ });
  }

  C.startPolling = function () {
    pollEvents(); pollMetrics(); pollHealth();
    setInterval(pollEvents, 1000);
    setInterval(pollMetrics, 2000);
    setInterval(pollHealth, 5000);
  };
  C.fmtMem = fmtMem;
})(window.Console);
