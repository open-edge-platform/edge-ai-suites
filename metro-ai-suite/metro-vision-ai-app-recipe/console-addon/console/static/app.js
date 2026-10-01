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
      .then(function (r) { return r.json(); });
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

  function fillSelect(sel, items, valueKey, labelKey) {
    if (!sel) { return; }
    sel.innerHTML = "";
    items.forEach(function (it) {
      var o = document.createElement("option");
      o.value = typeof it === "string" ? it : it[valueKey];
      o.textContent = typeof it === "string" ? it : it[labelKey];
      sel.appendChild(o);
    });
  }

  function modelOptionLabel(m) {
    // An incompatible IR is marked rather than hidden: it is selectable on
    // the devices that accept it, and the reason is shown on selection.
    if (m.compatibility && m.compatibility !== "ok") {
      return m.label + "  \u26a0 " + m.compatibility;
    }
    return m.label;
  }

  function showModelHint() {
    var hint = byId("modelSrcHint");
    var sel = byId("modelSelA");
    if (!hint || !sel) { return; }
    var m = MODELS.filter(function (x) { return x.id === sel.value; })[0];
    if (m && m.compatibility && m.compatibility !== "ok") {
      hint.textContent = m.compatibility_detail ||
        ("This model reports " + m.compatibility + " and may not run on every device.");
      hint.className = "hint hint-warn";
      return;
    }
    hint.className = "hint";
    // The last two dimensions are the input height and width the model was
    // built for; the leading batch and channel counts tell an operator nothing.
    var s = m && m.input_shape;
    hint.textContent = (s && s.length >= 4)
      ? "Input resolution " + s[s.length - 1] + "\u00d7" + s[s.length - 2]
      : "Models are discovered from the mounted model store.";
  }

  function loadModels(force) {
    return C.apiGet("api/models" + (force ? "?refresh=1" : "")).then(function (d) {
      MODELS = (d && d.models) || [];
      [byId("modelSelA"), byId("modelSelB")].forEach(function (sel) {
        if (!sel) { return; }
        var keep = sel.value;
        sel.innerHTML = "";
        MODELS.forEach(function (m) {
          var o = document.createElement("option");
          o.value = m.id;
          o.textContent = modelOptionLabel(m);
          sel.appendChild(o);
        });
        if (keep) { sel.value = keep; }
      });
      if (byId("modelSelB") && MODELS.length > 1 && !byId("modelSelB").value) {
        byId("modelSelB").selectedIndex = 1;
      }
      showModelHint();
      return MODELS;
    });
  }

  // Used by telemetry.js to title a panel reattached on page reload, where
  // the session carries only the raw model id (never an operator-facing
  // string) and there is no fresher label from a Start click to adopt.
  C.modelLabel = function (modelId) {
    var m = MODELS.filter(function (x) { return x.id === modelId; })[0];
    return m ? m.label : modelId;
  };

  function loadConfig() {
    return C.apiGet("api/config").then(function (cfg) {
      if (!cfg) { return; }
      fillSelect(byId("sourceSel"), cfg.sources || [], "id", "label");
      // cfg.devices is a list of {id, available} objects, not plain strings;
      // only devices actually usable on this deployment are offered.
      var devices = (cfg.devices || []).filter(function (d) { return d.available; });
      if (!devices.length) { devices = [{ id: "CPU", available: true }]; }
      fillSelect(byId("deviceSel"), devices, "id", "id");
      // GPU gives the best balance of throughput and availability on this
      // deployment; fall back to whatever is first when it is not present.
      var deviceSel = byId("deviceSel");
      if (deviceSel) {
        var hasGpu = devices.some(function (d) { return d.id === "GPU"; });
        deviceSel.value = hasGpu ? "GPU" : devices[0].id;
      }
      // Reflect the zone this deployment was configured with, so the rail
      // never shows a rectangle the server is not enforcing.
      C.setZoneInputs(cfg.default_zone);
      if (byId("loiterThr") && cfg.loiter_threshold_s !== undefined) {
        byId("loiterThr").textContent = cfg.loiter_threshold_s;
      }
      return cfg;
    });
  }

  function startOne(modelId, device, source, rtsp, zone) {
    var m = MODELS.filter(function (x) { return x.id === modelId; })[0];
    return C.apiPost("api/pipelines/start", {
      source: source, rtsp: rtsp, model: modelId, device: device, zone: zone
    }).then(function (r) {
      C.createPanel({
        peer_id: r.peer_id,
        whep_url: r.whep_url,
        title: ((m && m.label) || modelId) + " \u00b7 " + device,
        zone: r.zone
      });
      if (r.compatibility && r.compatibility !== "ok") {
        C.setPanelStatus(r.peer_id, "warning", r.compatibility_detail || r.compatibility);
      }
      return r;
    });
  }

  function onStart() {
    var btn = byId("startBtn");
    var device = byId("deviceSel").value;
    var source = byId("sourceSel").value;
    var rtsp = (byId("rtspInput").value || "").trim();
    // Omit the zone entirely until the operator customises it, so the
    // deployment's own zones (loitering_analytics_config.json) are what the
    // pipeline evaluates rather than an implicit rectangle derived from them.
    var zone = C._zoneCustomized ? C.currentZoneString() : null;
    var wanted = [byId("modelSelA").value];
    if (byId("compareMode").checked && byId("modelSelB").value) {
      wanted.push(byId("modelSelB").value);
    }
    btn.disabled = true;
    var prev = btn.textContent;
    btn.textContent = "Starting\u2026";
    Promise.all(wanted.map(function (mid) {
      return startOne(mid, device, source, rtsp, zone).catch(function (e) {
        alert("Could not start " + mid + ": " + (e && e.message ? e.message : e));
        return null;
      });
    })).then(function () {
      btn.disabled = false;
      btn.textContent = prev;
      C.updateEmptyState();
      // Streams now run this zone (or the file's own, if not customised),
      // so applying the rail's current value again would be a no-op.
      if (zone) { C.markZoneApplied(zone); }
    });
  }

  function wire() {
    byId("startBtn").addEventListener("click", onStart);
    byId("stopAllBtn").addEventListener("click", function () { C.stopAll(); });
    byId("refreshModels").addEventListener("click", function () { loadModels(true); });
    byId("modelSelA").addEventListener("change", showModelHint);
    byId("compareMode").addEventListener("change", function () {
      byId("modelBWrap").hidden = !this.checked;
    });
    byId("applyZoneAll").addEventListener("click", function (ev) {
      // The server applies to every live stream when no peer_id is given.
      C.applyZone(null, ev.currentTarget);
    });
    ["roiX", "roiY", "roiW", "roiH"].forEach(function (id) {
      var el = byId(id);
      if (el) {
        el.addEventListener("input", function () {
          C._zoneCustomized = true;
          C.refreshApplyState();
        });
      }
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
      .then(function () { C.startPolling(); })
      .catch(function (e) {
        var el = byId("connState");
        if (el) { el.textContent = "console error: " + e; el.className = "conn conn-bad"; }
      });
  });
})(window.Console);
