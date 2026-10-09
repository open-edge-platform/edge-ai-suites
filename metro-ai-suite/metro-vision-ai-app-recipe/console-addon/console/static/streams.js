// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//
// Per-instance stream configuration: one accordion per stream the operator
// wants to start, each with its own source/model/device, replacing the old
// single source+model pair and its "compare" checkbox. Zone customization
// happens only after a stream is live (draw on video, see zones.js/
// panels.js) - there is nothing to draw on before a stream exists, so a
// new stream always starts on the deployment's own configured zones.
// app.js owns fetching sources/models/devices (C.SOURCES/C.MODELS/
// C.DEVICES) and calls C.initStreamConfigs() once that data has actually
// arrived - see the note on that function for why the ordering matters.
(function (C) {
  "use strict";

  function byId(id) { return document.getElementById(id); }
  function container() { return byId("streamConfigs"); }

  function cards() {
    return Array.prototype.slice.call(container().querySelectorAll(".stream-cfg"));
  }

  function fillSelect(sel, items, valueKey, labelKey, labelFn) {
    if (!sel) { return; }
    var keep = sel.value;
    sel.innerHTML = "";
    items.forEach(function (it) {
      var o = document.createElement("option");
      o.value = typeof it === "string" ? it : it[valueKey];
      o.textContent = labelFn ? labelFn(it) : (typeof it === "string" ? it : it[labelKey]);
      sel.appendChild(o);
    });
    if (keep && items.some(function (it) { return (typeof it === "string" ? it : it[valueKey]) === keep; })) {
      sel.value = keep;
    }
  }

  function modelOptionLabel(m) {
    if (m.compatibility && m.compatibility !== "ok") {
      return m.label + "  \u26a0 " + m.compatibility;
    }
    return m.label;
  }

  function updateHint(card) {
    var hint = card.querySelector(".sc-hint");
    var sel = card.querySelector(".sc-model");
    if (!hint || !sel) { return; }
    var m = (C.MODELS || []).filter(function (x) { return x.id === sel.value; })[0];
    if (m && m.compatibility && m.compatibility !== "ok") {
      hint.textContent = m.compatibility_detail ||
        ("This model reports " + m.compatibility + " and may not run on every device.");
      hint.className = "hint sc-hint hint-warn";
      return;
    }
    hint.className = "hint sc-hint";
    var s = m && m.input_shape;
    hint.textContent = (s && s.length >= 4)
      ? "Input resolution " + s[s.length - 1] + "\u00d7" + s[s.length - 2]
      : "Models are discovered from the mounted model store.";
  }

  function setCardTitle(card, idx) {
    card.querySelector(".sc-title").textContent = "Pipeline " + idx;
  }

  function populateCardSelects(card) {
    fillSelect(card.querySelector(".sc-source"), C.SOURCES || [], "id", "label");
    fillSelect(card.querySelector(".sc-model"), C.MODELS || [], "id", "label", modelOptionLabel);
    var deviceSel = card.querySelector(".sc-device");
    var devices = C.DEVICES || [];
    var hadValue = !!deviceSel.value;
    fillSelect(deviceSel, devices, "id", "id");
    // Only pick a default the first time this select is ever populated -
    // once it had any value, fillSelect's own "keep current selection"
    // logic is authoritative, so a later re-populate (model refresh, more
    // devices becoming known) never clobbers a choice the operator may
    // since have made deliberately.
    if (!hadValue && devices.length) {
      var hasGpu = devices.some(function (d) { return d.id === "GPU"; });
      deviceSel.value = hasGpu ? "GPU" : devices[0].id;
    }
    updateHint(card);
  }

  function addCard(idx) {
    var tpl = byId("streamCfgTpl");
    var card = tpl.content.firstElementChild.cloneNode(true);
    setCardTitle(card, idx);
    // Only the first stream starts expanded - a dashboard with several
    // streams configured at once is what the accordion (name=streamAccordion,
    // exclusive open) exists to avoid.
    if (idx === 1) { card.open = true; }
    container().appendChild(card);
    card.querySelector(".sc-model").addEventListener("change", function () { updateHint(card); });
    card.querySelector(".sc-refresh").addEventListener("click", function (ev) {
      var refreshBtn = ev.currentTarget;
      refreshBtn.disabled = true;
      refreshBtn.classList.add("spin");
      C.refreshModels().catch(function () { /* transient - models list just stays as-is */ })
        .then(function () {
          refreshBtn.disabled = false;
          refreshBtn.classList.remove("spin");
        });
    });
    populateCardSelects(card);
    return card;
  }

  // Adds/removes accordions at the tail to match n, without touching the
  // values of instances that persist.
  C.ensureStreamConfigCount = function (n) {
    var existing = cards();
    for (var i = existing.length; i < n; i++) { addCard(i + 1); }
    for (var j = existing.length - 1; j >= n; j--) { existing[j].remove(); }
  };

  // Re-populate every existing accordion's selects - called after
  // sources/models/devices (re)load, so a model store refresh lands
  // correctly on cards created earlier.
  C.populateStreamConfigSelects = function () {
    cards().forEach(populateCardSelects);
  };

  // Creates the first accordion. Deliberately NOT called from this file's
  // own DOMContentLoaded handler: creating it before C.SOURCES/C.MODELS/
  // C.DEVICES exist left it permanently defaulted to a CPU-only fallback
  // device list, and fillSelect's "keep the current selection" behaviour
  // then preserved that accidental default even after the real device list
  // (with GPU) arrived moments later - every later-added stream, created
  // after the real list had loaded, defaulted to GPU correctly, so only
  // the very first stream was ever stuck on CPU. app.js calls this once
  // its initial config+model fetch has actually resolved.
  C.initStreamConfigs = function () {
    var countEl = byId("streamCount");
    var n = countEl ? (parseInt(countEl.value, 10) || 1) : 1;
    C.ensureStreamConfigCount(n);
  };

  // {source, rtsp, model, device} per configured stream, plus its 1-based
  // position (pipelineNum, for the panel title) and whether Start should
  // skip it because it already has a running pipeline attached - see
  // markCardStarted/markCardStopped. Zone is never set here - see the file
  // banner comment.
  C.collectStreamConfigs = function () {
    return cards().map(function (card, i) {
      return {
        source: card.querySelector(".sc-source").value,
        rtsp: (card.querySelector(".sc-rtsp").value || "").trim(),
        model: card.querySelector(".sc-model").value,
        device: card.querySelector(".sc-device").value,
        zone: null,
        pipelineNum: i + 1,
        alreadyRunning: !!card.dataset.peerId
      };
    });
  };

  function cardAt(pipelineNum) {
    return cards()[pipelineNum - 1];
  }

  function cardWithPeerId(peerId) {
    return cards().filter(function (c) { return c.dataset.peerId === peerId; })[0];
  }

  // Links a card to the pipeline it started, so a later Start click leaves
  // it alone instead of launching a second instance of the same card.
  C.markCardStarted = function (pipelineNum, peerId) {
    var card = cardAt(pipelineNum);
    if (card) { card.dataset.peerId = peerId; card.classList.add("sc-running"); }
  };

  // Un-links a card once its pipeline is actually stopped (operator Stop
  // or Stop all), so Start will launch it again next time.
  C.markCardStopped = function (peerId) {
    var card = cardWithPeerId(peerId);
    if (card) { delete card.dataset.peerId; card.classList.remove("sc-running"); }
  };

  // A zone reapply relaunches a running session under a brand new peer_id
  // (see panels.js's applyZone) - if that session came from one of these
  // cards, keep the card linked to its replacement id rather than treating
  // it as stopped (which would let a later Start click launch a duplicate).
  C.transferCardPeerId = function (oldPeerId, newPeerId) {
    var card = cardWithPeerId(oldPeerId);
    if (card) { card.dataset.peerId = newPeerId; }
  };

  function wire() {
    var countEl = byId("streamCount");
    if (!countEl) { return; }
    countEl.addEventListener("change", function () {
      var n = Math.max(1, Math.min(8, parseInt(countEl.value, 10) || 1));
      countEl.value = n;
      C.ensureStreamConfigCount(n);
      C.populateStreamConfigSelects();
    });
  }

  document.addEventListener("DOMContentLoaded", wire);
})(window.Console = window.Console || {});

