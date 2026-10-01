// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//
// Panel lifecycle, zone overlay and drag-to-draw zone selection.
// FRONTEND-SPEC.md part B sections B1-B4 and F.

window.Console = window.Console || {};

(function (C) {
  "use strict";

  var panels = {};      // peer_id -> { el, video, whep, zone }
  // Drag state lives on C so zones.js (start/move) and finishDraw here agree.

  function grid() { return document.getElementById("grid"); }
  function byId(id) { return document.getElementById(id); }

  // The placeholder is driven by what is mounted in the DOM, not by the
  // session table: a panel is created before its start request resolves, so
  // counting sessions leaves the placeholder visible over a live stream.
  function updateEmptyState() {
    var n = grid() ? grid().querySelectorAll(".panel").length : 0;
    var empty = byId("emptyState");
    if (empty) { empty.hidden = n > 0; }
    if (C.refreshApplyState) { C.refreshApplyState(); }
  }

  // Vertices, when supplied, take precedence over the rectangle fields.
  // Both notations are understood by the server.
  //
  // Starting a stream and the 1s reconcile poll (telemetry.js) can both
  // learn about the same brand-new session - whichever's response arrives
  // first wins the create; the other just adopts its (possibly more
  // accurate) title/zone onto the panel already running, rather than
  // cloning a second DOM node and opening a second WHEP connection for the
  // same peer_id.
  C.createPanel = function (info) {
    var existing = panels[info.peer_id];
    if (existing) {
      if (info.title) { existing.el.querySelector(".p-title").textContent = info.title; }
      if (info.zone) { existing.zone = info.zone; C.drawCurrentZone(info.peer_id); }
      return existing;
    }
    var tpl = byId("panelTpl");
    var el = tpl.content.firstElementChild.cloneNode(true);
    var video = el.querySelector("video");
    el.querySelector(".p-title").textContent = info.title;
    el.dataset.peerId = info.peer_id;
    grid().appendChild(el);

    var rec = { el: el, video: video, whep: null, zone: info.zone || null };
    panels[info.peer_id] = rec;
    updateEmptyState();

    el.querySelector(".p-close").addEventListener("click", function () {
      C.removePanel(info.peer_id);
    });

    var overlay = el.querySelector(".roi-overlay");
    overlay.addEventListener("mousedown", function (e) { C.onDrawStart(info.peer_id, e); });
    overlay.addEventListener("mousemove", function (e) { C.onDrawMove(info.peer_id, e); });
    overlay.addEventListener("mouseup", function (e) { C.finishDraw(info.peer_id, e); });
    video.addEventListener("loadedmetadata", function () { C.drawCurrentZone(info.peer_id); });

    var whep = new C.Whep.WhepSession(video, info.whep_url, function (state, detail) {
      C.setPanelStatus(info.peer_id, state, detail);
    });
    rec.whep = whep;
    whep.start().catch(function (e) {
      C.setPanelStatus(info.peer_id, "error", String(e && e.message ? e.message : e));
    });
    return rec;
  };

  C.finishDraw = function (peerId, ev) {
    var drawing = C._drawing;
    if (!drawing || drawing.peerId !== peerId) { return; }
    var p = panels[peerId];
    var overlay = p.el.querySelector(".roi-overlay");
    var box = p.el.querySelector(".roi-draw");
    var r = overlay.getBoundingClientRect();
    var x1 = ev.clientX - r.left, y1 = ev.clientY - r.top;
    var x0 = drawing.x0, y0 = drawing.y0;
    var g = C.videoGeometry(p.video);
    box.style.display = "none";
    C._drawing = null;
    if (!g) { return; }
    var sx = Math.round((Math.min(x0, x1) - g.ox) / g.scale);
    var sy = Math.round((Math.min(y0, y1) - g.oy) / g.scale);
    var sw = Math.round(Math.abs(x1 - x0) / g.scale);
    var sh = Math.round(Math.abs(y1 - y0) / g.scale);
    if (sw < 8 || sh < 8) { return; }
    sx = Math.max(0, Math.min(sx, g.vw - 1));
    sy = Math.max(0, Math.min(sy, g.vh - 1));
    C.setZoneInputs({ x: sx, y: sy, w: Math.min(sw, g.vw - sx), h: Math.min(sh, g.vh - sy) });
    C._zoneCustomized = true;
    C.refreshApplyState();
  };

  // Removes a panel whose instance the server already tore down (a zone
  // reapply), without issuing a second stop request.
  function removePanelLocal(peerId) {
    var p = panels[peerId];
    if (!p) { return; }
    delete panels[peerId];
    if (p.whep) { try { p.whep.stop(); } catch (e) { /* already closed */ } }
    if (p.el && p.el.parentNode) { p.el.parentNode.removeChild(p.el); }
    updateEmptyState();
  }

  // Applying with a peerId targets that stream only; without one the server
  // fans out to every live stream itself, so callers must not loop over panels.
  // gvaanalytics cannot update a zone in place, so each affected session is
  // relaunched under a new peer_id and its panel replaced.
  C.applyZone = function (peerId, btn) {
    var zone = C.currentZoneString();
    C._zoneCustomized = true;
    var body = { zone: zone };
    if (peerId) { body.peer_id = peerId; }
    if (btn) { btn.disabled = true; btn.textContent = "Applying..."; }
    return C.apiPost("api/zone", body).then(function (r) {
      var updated = (r && r.updated) || [];
      updated.forEach(function (session) {
        var old = panels[session.old_peer_id];
        var title = old ? old.el.querySelector(".p-title").textContent : (session.model + " / " + session.device);
        removePanelLocal(session.old_peer_id);
        C.createPanel({
          peer_id: session.peer_id,
          whep_url: session.whep_url,
          title: title,
          zone: session.zone,
        });
      });
      if (r && r.zone) { C.setZoneInputs(r.zone); }
      C.markZoneApplied();
      var n = (r && r.count) || 0;
      if (btn) {
        btn.textContent = "Applied to " + n + " stream" + (n === 1 ? "" : "s");
        setTimeout(function () { btn.textContent = "Apply zone to live streams"; C.refreshApplyState(); }, 1500);
      }
    }).catch(function () {
      if (btn) { btn.textContent = "Apply failed"; btn.disabled = false; }
    });
  };

  C.panelZone = function (peerId) {
    var p = panels[peerId];
    return p ? p.zone : null;
  };

  C.panelEl = function (peerId) {
    var p = panels[peerId];
    return p ? p.el : null;
  };

  C.setPanelStatus = function (peerId, state, detail) {
    var p = panels[peerId];
    if (!p) { return; }
    var el = p.el.querySelector(".p-status");
    el.textContent = detail ? (state + " \u2014 " + detail) : state;
    el.className = "p-status st-" + String(state).replace(/[^a-z-]/gi, "");
  };

  C.removePanel = function (peerId) {
    var p = panels[peerId];
    if (!p) { return Promise.resolve(); }
    delete panels[peerId];
    if (p.whep) { try { p.whep.stop(); } catch (e) { /* already closed */ } }
    if (p.el && p.el.parentNode) { p.el.parentNode.removeChild(p.el); }
    updateEmptyState();
    return C.apiPost("api/pipelines/stop", { peer_id: peerId }).catch(function () { return null; });
  };

  C.stopAll = function () {
    return Promise.all(Object.keys(panels).map(C.removePanel));
  };

  C.panels = panels;
  C.updateEmptyState = updateEmptyState;
  C.setPanelZone = function (peerId, z) {
    if (panels[peerId]) { panels[peerId].zone = z; C.drawCurrentZone(peerId); }
  };
  window.addEventListener("resize", C.redrawAllZones);
})(window.Console);
