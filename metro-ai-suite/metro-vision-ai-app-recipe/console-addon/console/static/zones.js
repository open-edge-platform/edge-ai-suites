// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
// Zone concern: rectangle input, source-pixel mapping, overlay rendering,
// drag-to-draw and application to live streams.
(function (C) {
  "use strict";
  function byId(id) { return document.getElementById(id); }
  // Shared with panels.js via C._drawing - see the note there.

  C.currentZoneString = function () {
    var v = ["roiX", "roiY", "roiW", "roiH"].map(function (id) {
      var el = byId(id);
      return el ? parseInt(el.value, 10) || 0 : 0;
    });
    return v.join(",");
  }

  C.setZoneInputs = function (z) {
    if (!z) { return; }
    var m = { roiX: z.x, roiY: z.y, roiW: z.w, roiH: z.h };
    Object.keys(m).forEach(function (id) {
      var el = byId(id);
      if (el && m[id] !== undefined) { el.value = m[id]; }
    });
  }

  // The zone the running streams are actually evaluating; the control stays
  // disabled until the fields differ from it.
  C._appliedZone = null;

  // Whether the operator has ever edited the rail, drawn on video, or
  // applied a zone. Starting a stream while this is false keeps the
  // deployment's own zones (loitering_analytics_config.json) exactly as
  // configured; once true, a custom rectangle is sent instead and replaces
  // them entirely (gvaanalytics evaluates one zone set or the other, never
  // both - see config.py's analytics_zones_json). Never reset to false:
  // once customised, the session stays in "custom zone" mode.
  C._zoneCustomized = false;

  C.markZoneApplied = function (zoneString) {
    C._appliedZone = zoneString !== undefined ? zoneString : C.currentZoneString();
    C.refreshApplyState();
  }

  C.refreshApplyState = function () {
    var btn = byId("applyZoneAll");
    if (!btn) { return; }
    var changed = C.currentZoneString() !== C._appliedZone;
    var hasStreams = Object.keys(C.panels || {}).length > 0;
    btn.disabled = !(changed && hasStreams);
    btn.title = !hasStreams ? "Start a stream first"
      : (changed ? "" : "This zone is already applied");
  }

  // Map a rectangle expressed in source pixels onto the rendered <video>,
  // accounting for the letterbox introduced by object-fit: contain.
  C.videoGeometry = function (video) {
    var vw = video.videoWidth, vh = video.videoHeight;
    var cw = video.clientWidth, ch = video.clientHeight;
    if (!vw || !vh || !cw || !ch) { return null; }
    var scale = Math.min(cw / vw, ch / vh);
    return { scale: scale, ox: (cw - vw * scale) / 2, oy: (ch - vh * scale) / 2, vw: vw, vh: vh };
  }

  // gvawatermark already renders the attached ROI into the video, so drawing
  // it again here would show two boxes. Only the drag preview is drawn.
  C.drawCurrentZone = function (peerId) {
    var el = C.panelEl(peerId);
    var box = el && el.querySelector(".roi-current");
    if (box) { box.style.display = "none"; }
  }

  // "panels" (the peer_id -> panel record map) lives in panels.js's own
  // closure; it is only reachable here via the shared C namespace.
  C.redrawAllZones = function () { Object.keys(C.panels || {}).forEach(C.drawCurrentZone); }

  C.onDrawStart = function (peerId, ev) {
    if (!byId("drawZone") || !byId("drawZone").checked) { return; }
    var el = C.panelEl(peerId);
    var p = el ? { el: el, video: el.querySelector('video'), zone: C.panelZone(peerId) } : null;
    if (!p) { return; }
    var r = p.el.querySelector(".roi-overlay").getBoundingClientRect();
    C._drawing = { peerId: peerId, x0: ev.clientX - r.left, y0: ev.clientY - r.top };
    ev.preventDefault();
  }

  C.onDrawMove = function (peerId, ev) {
    var drawing = C._drawing;
    if (!drawing || drawing.peerId !== peerId) { return; }
    var el = C.panelEl(peerId);
    var p = el ? { el: el, video: el.querySelector('video'), zone: C.panelZone(peerId) } : null;
    var overlay = p.el.querySelector(".roi-overlay");
    var box = p.el.querySelector(".roi-draw");
    var r = overlay.getBoundingClientRect();
    var x = ev.clientX - r.left, y = ev.clientY - r.top;
    box.style.display = "block";
    box.style.left = Math.min(drawing.x0, x) + "px";
    box.style.top = Math.min(drawing.y0, y) + "px";
    box.style.width = Math.abs(x - drawing.x0) + "px";
    box.style.height = Math.abs(y - drawing.y0) + "px";
  }


})(window.Console = window.Console || {});
