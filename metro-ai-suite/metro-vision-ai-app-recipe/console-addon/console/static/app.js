// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//
// Bootstrap, control wiring, stream start and stop.
// FRONTEND-SPEC.md part B sections B0 and B7.

window.Console = window.Console || {};

(function (C) {
  "use strict";

  function byId(id) { return document.getElementById(id); }

  // All requests are relative to the document base, so the console works
  // unchanged at the site root or behind any path prefix.
  C.apiGet = function (path) {
    return fetch(new URL(path, document.baseURI), { headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.json().then(function (j) {
          if (!r.ok) { throw new Error(j && j.error ? j.error : "request failed"); }
          return j;
        });
      });
  };

  C.apiPost = function (path, body) {
    return fetch(new URL(path, document.baseURI), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) { throw new Error(j && j.error ? j.error : "request failed"); }
        return j;
      });
    });
  };

  var MODELS = [];
  C.MODELS = MODELS;

  // Used by telemetry.js to title a panel reattached on page reload, where
  // the session carries only the raw model id (never an operator-facing
  // string) and there is no fresher label from a Start click to adopt.
  C.modelLabel = function (modelId) {
    var m = MODELS.filter(function (x) { return x.id === modelId; })[0];
    return m ? m.label : modelId;
  };

  function loadModels(force) {
    return C.apiGet("api/models" + (force ? "?refresh=1" : "")).then(function (d) {
      MODELS.length = 0;
      Array.prototype.push.apply(MODELS, (d && d.models) || []);
      C.populateStreamConfigSelects();
      return MODELS;
    });
  }

  C.refreshModels = function () { return loadModels(true); };

  function loadConfig() {
    return C.apiGet("api/config").then(function (cfg) {
      if (!cfg) { return; }
      C.SOURCES = cfg.sources || [];
      // cfg.devices is a list of {id, available} objects, not plain strings;
      // only devices actually usable on this deployment are offered.
      C.DEVICES = (cfg.devices || []).filter(function (d) { return d.available; });
      if (!C.DEVICES.length) { C.DEVICES = [{ id: "CPU", available: true }]; }
      // Reflect the zone this deployment was configured with, so the rail
      // never shows a rectangle the server is not enforcing.
      C.setRectZone(cfg.default_zone);
      if (byId("loiterThr") && cfg.loiter_threshold_s !== undefined) {
        byId("loiterThr").textContent = cfg.loiter_threshold_s;
      }
      return cfg;
    });
  }

  function startOne(pipelineNum, modelId, device, source, rtsp, zone) {
    var m = MODELS.filter(function (x) { return x.id === modelId; })[0];
    return C.apiPost("api/pipelines/start", {
      source: source, rtsp: rtsp, model: modelId, device: device, zone: zone
    }).then(function (r) {
      C.createPanel({
        peer_id: r.peer_id,
        whep_url: r.whep_url,
        title: "Pipeline " + pipelineNum + " \u00b7 " + ((m && m.label) || modelId) + " \u00b7 " + device,
        zone: r.zone
      });
      C.markCardStarted(pipelineNum, r.peer_id);
      if (r.compatibility && r.compatibility !== "ok") {
        C.setPanelStatus(r.peer_id, "warning", r.compatibility_detail || r.compatibility);
      }
      return r;
    });
  }

  function onStart() {
    var btn = byId("startBtn");
    // A card already linked to a running pipeline is left alone -
    // otherwise raising "Number of pipelines" to add one more card 
    // and clicking Start again would relaunch every earlier pipeline
    // too, duplicating all of them instead of adding just the new one.
    var configs = C.collectStreamConfigs().filter(function (cfg) { return !cfg.alreadyRunning; });
    if (!configs.length) { return; }
    btn.disabled = true;
    var prev = btn.textContent;
    btn.textContent = "Starting\u2026";
    Promise.all(configs.map(function (cfg) {
      return startOne(cfg.pipelineNum, cfg.model, cfg.device, cfg.source, cfg.rtsp, cfg.zone).catch(function (e) {
        alert("Could not start " + cfg.model + ": " + (e && e.message ? e.message : e));
        return null;
      });
    })).then(function () {
      btn.disabled = false;
      btn.textContent = prev;
      C.updateEmptyState();
    });
  }

  function wire() {
    byId("startBtn").addEventListener("click", onStart);
    byId("stopAllBtn").addEventListener("click", function () { C.stopAll(); });
    byId("applyZoneAll").addEventListener("click", function (ev) {
      // The server applies to every live stream when no peer_id is given.
      C.applyZone(null, ev.currentTarget);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    wire();
    C.updateEmptyState();
    loadConfig()
      .then(function () {
        // The fields now hold the deployment's configured zone; treat it as
        // already applied so the control only lights up on a real change.
        C.markZoneApplied();
        return loadModels(false);
      })
      .then(function () {
        // Only now, not from streams.js's own DOMContentLoaded listener:
        // creating the first stream accordion before C.SOURCES/C.MODELS/
        // C.DEVICES exist is what stuck it with a CPU-only fallback device
        // default forever.
        C.initStreamConfigs();
        C.startPolling();
      })
      .catch(function (e) {
        var el = byId("connState");
        if (el) { el.textContent = "console error: " + e; el.className = "conn conn-bad"; }
      });
  });
})(window.Console);
