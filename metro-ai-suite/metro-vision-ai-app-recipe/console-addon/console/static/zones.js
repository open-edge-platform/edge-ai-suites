// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
// Zone concern: source-pixel mapping, overlay rendering, drag/click-to-draw
// and application to live streams. There is no numeric coordinate entry -
// drawing on a live stream's video is the only way to set a custom zone,
// so the rectangle's value lives in C._rectZone (a plain object) rather
// than form fields; the rail only ever shows a read-only summary of it.
(function (C) {
  "use strict";
  function byId(id) { return document.getElementById(id); }
  // Shared with panels.js via C._drawing - see the note there.

  // "rect" (drag a rectangle - default) or "poly" (click vertices). A
  // completed polygon lives in C._zonePolygonPoints ([x,y] pairs, source
  // pixels) until the shape is switched back to rect or a new rectangle is
  // drawn, either of which drops it so stale polygon data can never leak
  // into a rectangle-intended Apply.
  C._zoneShape = "rect";
  C._zonePolygonPoints = null;
  C._rectZone = { x: 0, y: 0, w: 0, h: 0 };

  C.clearZonePolygon = function () { C._zonePolygonPoints = null; }

  C.currentZoneString = function () {
    if (C._zoneShape === "poly" && C._zonePolygonPoints && C._zonePolygonPoints.length >= 3) {
      return C._zonePolygonPoints.map(function (p) { return "(" + p[0] + "," + p[1] + ")"; }).join(" ");
    }
    var z = C._rectZone;
    return [z.x, z.y, z.w, z.h].join(",");
  }

  function updateZoneSummary() {
    var el = byId("zoneSummary");
    if (!el) { return; }
    if (C._zoneShape === "poly" && C._zonePolygonPoints && C._zonePolygonPoints.length >= 3) {
      el.textContent = "Current zone: polygon, " + C._zonePolygonPoints.length + " points";
      return;
    }
    var z = C._rectZone;
    el.textContent = C._zoneCustomized
      ? "Current zone: rectangle " + z.w + "\u00d7" + z.h + " at (" + z.x + "," + z.y + ")"
      : "Current zone: this deployment's own configured zone(s)";
  }
  C.updateZoneSummary = updateZoneSummary;

  // Sets the rectangle the rail currently holds (from a drag, an Apply
  // response, or the deployment's own default at page load) and refreshes
  // its read-only summary - there is no form field left to populate.
  C.setRectZone = function (z) {
    if (!z) { return; }
    C._rectZone = { x: z.x | 0, y: z.y | 0, w: z.w | 0, h: z.h | 0 };
    updateZoneSummary();
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
    btn.title = !hasStreams ? "Start a pipeline first"
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

  // The peer_id whose drawn-but-not-yet-applied zone is currently shown as
  // a persistent preview (.roi-current for a rectangle, .roi-polygon for a
  // polygon) - only one at a time, since the rail's zone fields (and
  // C._zonePolygonPoints) are shared/global, not per-panel.
  C._pendingZonePeerId = null;

  function positionPendingRect(peerId) {
    var el = C.panelEl(peerId);
    var box = el && el.querySelector(".roi-current");
    var g = el && C.videoGeometry(el.querySelector("video"));
    if (!box || !g) { return; }
    var z = C._rectZone;
    box.style.left = (z.x * g.scale + g.ox) + "px";
    box.style.top = (z.y * g.scale + g.oy) + "px";
    box.style.width = (z.w * g.scale) + "px";
    box.style.height = (z.h * g.scale) + "px";
    box.style.display = "block";
  }

  // Shows the rail's current (drawn, unapplied) zone on the given panel and
  // reveals that panel's own "Apply to this stream" button. Replaces
  // whatever was pending on any other panel - there is only ever one
  // drawn-but-unapplied zone at a time.
  C.showPendingZone = function (peerId) {
    if (C._pendingZonePeerId && C._pendingZonePeerId !== peerId) {
      C.hidePendingZone(C._pendingZonePeerId);
    }
    C._pendingZonePeerId = peerId;
    if (C._zoneShape === "poly") { renderPolyOverlay(peerId); } else { positionPendingRect(peerId); }
    C.showPanelApplyButton(peerId);
  }

  C.hidePendingZone = function (peerId) {
    var el = C.panelEl(peerId);
    if (el) {
      var box = el.querySelector(".roi-current");
      if (box) { box.style.display = "none"; }
      var svg = el.querySelector(".roi-polygon");
      if (svg) { svg.style.display = "none"; svg.innerHTML = ""; }
    }
    C.hidePanelApplyButton(peerId);
    if (C._pendingZonePeerId === peerId) { C._pendingZonePeerId = null; }
  }

  // Re-renders whatever is actually showing for this panel on
  // loadedmetadata/resize: the pending draft if it is the one with one, or
  // nothing - gvawatermark already renders an applied zone server-side, so
  // there is never anything to draw here for a panel with no pending draft.
  C.drawCurrentZone = function (peerId) {
    if (C._pendingZonePeerId === peerId) {
      if (C._zoneShape === "poly") { renderPolyOverlay(peerId); } else { positionPendingRect(peerId); }
      return;
    }
    var el = C.panelEl(peerId);
    var box = el && el.querySelector(".roi-current");
    if (box) { box.style.display = "none"; }
    var svg = el && el.querySelector(".roi-polygon");
    if (svg) { svg.style.display = "none"; svg.innerHTML = ""; }
  }

  // "panels" (the peer_id -> panel record map) lives in panels.js's own
  // closure; it is only reachable here via the shared C namespace.
  C.redrawAllZones = function () {
    // An in-progress polygon's screen-space rendering goes stale on resize;
    // aborting it is simpler and safer than re-deriving a consistent layout
    // mid-draw across a monitor/window size change.
    if (C._polyDrawing) { C.cancelPolyDrawing(C._polyDrawing.peerId); }
    Object.keys(C.panels || {}).forEach(C.drawCurrentZone);
  }

  C.onDrawStart = function (peerId, ev) {
    if (C._zoneShape !== "rect" || !byId("drawZone") || !byId("drawZone").checked) { return; }
    var el = C.panelEl(peerId);
    if (!el) { return; }
    // Starting a fresh drag replaces whatever was previously pending on
    // this panel - it is about to be redrawn from scratch.
    C.hidePendingZone(peerId);
    var r = el.querySelector(".roi-overlay").getBoundingClientRect();
    C._drawing = { peerId: peerId, x0: ev.clientX - r.left, y0: ev.clientY - r.top };
    ev.preventDefault();
  }

  C.onDrawMove = function (peerId, ev) {
    if (C._zoneShape !== "rect") { return; }
    var drawing = C._drawing;
    if (!drawing || drawing.peerId !== peerId) { return; }
    var el = C.panelEl(peerId);
    if (!el) { return; }
    var overlay = el.querySelector(".roi-overlay");
    var box = el.querySelector(".roi-draw");
    var r = overlay.getBoundingClientRect();
    var x = ev.clientX - r.left, y = ev.clientY - r.top;
    box.style.display = "block";
    box.style.left = Math.min(drawing.x0, x) + "px";
    box.style.top = Math.min(drawing.y0, y) + "px";
    box.style.width = Math.abs(x - drawing.x0) + "px";
    box.style.height = Math.abs(y - drawing.y0) + "px";
  }

  /* ------------------------------------------------------- polygon draw --- */

  // Standard orientation/on-segment test for whether two line segments
  // properly intersect (including collinear-overlap cases).
  function orientation(p, q, r) {
    var val = (q.sy - p.sy) * (r.sx - q.sx) - (q.sx - p.sx) * (r.sy - q.sy);
    if (Math.abs(val) < 1e-9) { return 0; }
    return val > 0 ? 1 : 2;
  }
  function onSegment(p, q, r) {
    return q.sx <= Math.max(p.sx, r.sx) && q.sx >= Math.min(p.sx, r.sx) &&
           q.sy <= Math.max(p.sy, r.sy) && q.sy >= Math.min(p.sy, r.sy);
  }
  function segmentsIntersect(p1, p2, p3, p4) {
    var o1 = orientation(p1, p2, p3), o2 = orientation(p1, p2, p4);
    var o3 = orientation(p3, p4, p1), o4 = orientation(p3, p4, p2);
    if (o1 !== o2 && o3 !== o4) { return true; }
    if (o1 === 0 && onSegment(p1, p3, p2)) { return true; }
    if (o2 === 0 && onSegment(p1, p4, p2)) { return true; }
    if (o3 === 0 && onSegment(p3, p1, p4)) { return true; }
    if (o4 === 0 && onSegment(p3, p2, p4)) { return true; }
    return false;
  }

  // Would the candidate edge (points[last] -> newPoint) cross any edge of
  // the polygon-so-far that it is not already joined to at a shared vertex?
  // Handles both "placing the next point" and "closing back to the first
  // point" with the same check.
  function wouldSelfIntersect(points, newPoint) {
    var n = points.length;
    var newA = points[n - 1];
    var closingToFirst = newPoint === points[0];
    for (var i = 0; i < n - 1; i++) {
      if (i === n - 2) { continue; }                 // shares endpoint newA
      if (closingToFirst && i === 0) { continue; }    // shares endpoint newPoint
      if (segmentsIntersect(newA, newPoint, points[i], points[i + 1])) { return true; }
    }
    return false;
  }

  function svgEl(svg, name, attrs) {
    var el = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.keys(attrs).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    svg.appendChild(el);
    return el;
  }

  // Redraws the polygon overlay: either the in-progress draw (confirmed
  // vertices/edges plus a rubber-band preview line to the cursor, when one
  // is supplied) or, once closed and pending Apply, the completed shape as
  // a static preview (closing edge included, no rubber band) so it stays
  // visible instead of vanishing the moment the mouse is released.
  function renderPolyOverlay(peerId, cursor, rejected) {
    var el = C.panelEl(peerId);
    if (!el) { return; }
    var video = el.querySelector("video");
    var g = C.videoGeometry(video);
    var svg = el.querySelector(".roi-polygon");
    svg.innerHTML = "";
    var state = C._polyDrawing;
    var points, closed;
    if (state && state.peerId === peerId) {
      points = state.points; closed = false;
    } else if (C._pendingZonePeerId === peerId && C._zonePolygonPoints && C._zonePolygonPoints.length >= 3) {
      points = C._zonePolygonPoints.map(function (p) { return { sx: p[0], sy: p[1] }; });
      closed = true;
    } else {
      svg.style.display = "none";
      return;
    }
    if (!g || !points.length) { svg.style.display = "none"; return; }
    svg.style.display = "block";
    var toScreen = function (p) { return { x: p.sx * g.scale + g.ox, y: p.sy * g.scale + g.oy }; };
    var pts = points.map(toScreen);
    for (var i = 0; i < pts.length - 1; i++) {
      svgEl(svg, "line", { x1: pts[i].x, y1: pts[i].y, x2: pts[i + 1].x, y2: pts[i + 1].y });
    }
    if (closed) {
      var first = pts[0], last = pts[pts.length - 1];
      svgEl(svg, "line", { x1: last.x, y1: last.y, x2: first.x, y2: first.y });
    }
    if (cursor) {
      var lastPt = pts[pts.length - 1];
      svgEl(svg, "line", {
        x1: lastPt.x, y1: lastPt.y, x2: cursor.x, y2: cursor.y,
        "class": "closing-edge" + (rejected ? " rejected" : "")
      });
    }
    pts.forEach(function (p, idx) {
      svgEl(svg, "circle", { cx: p.x, cy: p.y, r: 5, "class": idx === 0 ? "first-point" : "" });
    });
  }

  // Maps a client-space event to source-video pixels, clamping anything in
  // the letterbox margin (where object-fit: contain leaves no video) to the
  // nearest valid edge so a click just outside the frame still places a
  // usable point instead of being silently dropped.
  function eventToSourcePixel(overlay, video, ev) {
    var g = C.videoGeometry(video);
    if (!g) { return null; }
    var r = overlay.getBoundingClientRect();
    var x = ev.clientX - r.left, y = ev.clientY - r.top;
    return {
      g: g,
      screen: { x: x, y: y },
      sx: Math.max(0, Math.min(g.vw - 1, Math.round((x - g.ox) / g.scale))),
      sy: Math.max(0, Math.min(g.vh - 1, Math.round((y - g.oy) / g.scale)))
    };
  }

  C.onPolyClick = function (peerId, ev) {
    if (C._zoneShape !== "poly" || !byId("drawZone") || !byId("drawZone").checked) { return; }
    var el = C.panelEl(peerId);
    if (!el) { return; }
    var overlay = el.querySelector(".roi-overlay");
    var hit = eventToSourcePixel(overlay, el.querySelector("video"), ev);
    if (!hit) { return; }
    var state = C._polyDrawing;
    if (!state || state.peerId !== peerId) {
      state = C._polyDrawing = { peerId: peerId, points: [] };
      // A fresh polygon replaces whatever this panel had pending before.
      C.hidePendingZone(peerId);
    }
    var candidate = { sx: hit.sx, sy: hit.sy };
    // Clicking back near the first point closes the polygon - the same
    // gesture as double-click, without needing a second input method.
    if (state.points.length >= 3) {
      var g = hit.g, first = state.points[0];
      var fx = first.sx * g.scale + g.ox, fy = first.sy * g.scale + g.oy;
      if (Math.hypot(hit.screen.x - fx, hit.screen.y - fy) <= 10) {
        C.closePolyDrawing(peerId);
        return;
      }
    }
    if (state.points.length >= 1 && wouldSelfIntersect(state.points, candidate)) {
      renderPolyOverlay(peerId, hit.screen, true);
      return;
    }
    state.points.push(candidate);
    renderPolyOverlay(peerId);
  }

  C.onPolyPreviewMove = function (peerId, ev) {
    var state = C._polyDrawing;
    if (C._zoneShape !== "poly" || !state || state.peerId !== peerId) { return; }
    var el = C.panelEl(peerId);
    var overlay = el && el.querySelector(".roi-overlay");
    var hit = overlay && eventToSourcePixel(overlay, el.querySelector("video"), ev);
    if (!hit) { return; }
    var rejected = wouldSelfIntersect(state.points, { sx: hit.sx, sy: hit.sy });
    renderPolyOverlay(peerId, hit.screen, rejected);
  }

  C.closePolyDrawing = function (peerId) {
    var state = C._polyDrawing;
    if (!state || state.peerId !== peerId || state.points.length < 3) { return; }
    if (wouldSelfIntersect(state.points, state.points[0])) {
      renderPolyOverlay(peerId, null, true);
      return; // closing edge would cross another edge - stay open, keep drawing
    }
    C._zonePolygonPoints = state.points.map(function (p) { return [p.sx, p.sy]; });
    C._polyDrawing = null;
    // Mirror the rectangle fields to the polygon's bounding box, purely for
    // reference - currentZoneString() sends the polygon itself, not this box.
    var xs = state.points.map(function (p) { return p.sx; });
    var ys = state.points.map(function (p) { return p.sy; });
    C.setRectZone({
      x: Math.min.apply(null, xs), y: Math.min.apply(null, ys),
      w: Math.max.apply(null, xs) - Math.min.apply(null, xs),
      h: Math.max.apply(null, ys) - Math.min.apply(null, ys)
    });
    C._zoneCustomized = true;
    C.refreshApplyState();
    C.showPendingZone(peerId);
  }

  C.cancelPolyDrawing = function (peerId) {
    if (!C._polyDrawing || C._polyDrawing.peerId !== peerId) { return; }
    C._polyDrawing = null;
    C.drawCurrentZone(peerId);
  }

  C.onDrawPolygonClose = function (peerId, ev) {
    if (C._zoneShape !== "poly") { return; }
    ev.preventDefault();
    C.closePolyDrawing(peerId);
  }

  document.addEventListener("keydown", function (ev) {
    if (!C._polyDrawing) { return; }
    if (ev.key === "Escape") { C.cancelPolyDrawing(C._polyDrawing.peerId); }
    else if (ev.key === "Enter") { C.closePolyDrawing(C._polyDrawing.peerId); }
  });

  function wireShapeToggle() {
    var drawCb = byId("drawZone");
    var wrap = byId("shapeToggleWrap");
    var polyHint = byId("polyHint");
    if (!drawCb) { return; }
    function sync() {
      var drawing = drawCb.checked;
      // .roi-overlay is pointer-events:none at rest so it never steals
      // clicks from the video underneath; .draw is what switches it back
      // on while actively drawing (rectangle drag or polygon clicks alike).
      document.querySelectorAll(".roi-overlay").forEach(function (o) {
        o.classList.toggle("draw", drawing);
      });
      if (wrap) { wrap.hidden = !drawing; }
      var isPoly = drawing && C._zoneShape === "poly";
      if (polyHint) { polyHint.hidden = !isPoly; }
    }
    drawCb.addEventListener("change", sync);
    [byId("shapeRect"), byId("shapePoly")].forEach(function (radio) {
      if (!radio) { return; }
      radio.addEventListener("change", function () {
        C._zoneShape = this.value === "poly" ? "poly" : "rect";
        if (C._zoneShape === "rect") { C.clearZonePolygon(); }
        if (C._polyDrawing) { C.cancelPolyDrawing(C._polyDrawing.peerId); }
        // A rectangle pending from the OTHER shape mode would otherwise
        // keep showing alongside whatever gets drawn next - switching
        // shape always starts from a clean slate.
        if (C._pendingZonePeerId) { C.hidePendingZone(C._pendingZonePeerId); }
        sync();
      });
    });
    sync();
  }
  document.addEventListener("DOMContentLoaded", wireShapeToggle);

})(window.Console = window.Console || {});
