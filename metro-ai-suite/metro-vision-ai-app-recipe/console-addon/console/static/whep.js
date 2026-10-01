// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//
// WHEP playback. Plain script, no framework, no bundler, no external CDN.

(function (global) {
  "use strict";

  function parseLinkHeader(value) {
    // Link: <turn:host:3478>; rel="ice-server"; username="..."; credential="..."
    var servers = [];
    if (!value) return servers;
    var entries = value.split(/,(?=\s*<)/);
    for (var i = 0; i < entries.length; i++) {
      var entry = entries[i];
      var urlMatch = entry.match(/<([^>]+)>/);
      if (!urlMatch) continue;
      var relMatch = entry.match(/rel="?ice-server"?/i);
      if (!relMatch) continue;
      var server = { urls: urlMatch[1] };
      var userMatch = entry.match(/username="([^"]*)"/i);
      var credMatch = entry.match(/credential="([^"]*)"/i);
      if (userMatch) server.username = userMatch[1];
      if (credMatch) server.credential = credMatch[1];
      servers.push(server);
    }
    return servers;
  }

  async function discoverIceServers(whepUrl) {
    try {
      var resp = await fetch(whepUrl, { method: "OPTIONS" });
      var linkValues = [];
      // Multiple Link headers may be folded into one by the fetch API.
      var raw = resp.headers.get("Link");
      if (raw) linkValues.push(raw);
      var servers = [];
      for (var i = 0; i < linkValues.length; i++) {
        servers = servers.concat(parseLinkHeader(linkValues[i]));
      }
      return servers;
    } catch (e) {
      return [];
    }
  }

  function sleep(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  function WhepSession(videoEl, whepUrl, onState) {
    this.videoEl = videoEl;
    this.whepUrl = whepUrl;
    this.onState = onState || function () {};
    this.pc = null;
    this.resourceUrl = null;
    this.closed = false;
  }

  WhepSession.prototype._setState = function (state, detail) {
    this.onState(state, detail);
  };

  WhepSession.prototype.start = async function () {
    var self = this;
    self._setState("connecting", "discovering ICE servers");
    var iceServers = await discoverIceServers(self.whepUrl);
    // An empty iceServers list still lets signalling succeed while the
    // browser gathers only unreachable host candidates; proceed anyway and
    // record the condition rather than aborting.
    if (!iceServers.length) {
      self._setState("connecting", "no ICE servers advertised");
    }

    var pc = new RTCPeerConnection({ iceServers: iceServers });
    self.pc = pc;

    pc.addTransceiver("video", { direction: "recvonly" });
    pc.addTransceiver("audio", { direction: "recvonly" });

    pc.ontrack = function (ev) {
      if (ev.streams && ev.streams[0]) {
        self.videoEl.srcObject = ev.streams[0];
      }
      self._setState("live", "media attached");
    };

    // Frames arriving must clear any earlier "stalled" report.
    ["playing", "loadeddata"].forEach(function (evt) {
      self.videoEl.addEventListener(evt, function () {
        self._setState("live", "streaming");
      });
    });

    pc.oniceconnectionstatechange = function () {
      var st = pc.iceConnectionState;
      if (st === "failed" || st === "disconnected") {
        self._setState("error", "media negotiation failed (ICE " + st + ")");
      } else if (st === "connected" || st === "completed") {
        if (self.videoEl.readyState < 2) self._setState("stalled", "connected, awaiting frames");
      }
    };

    var offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    await new Promise(function (resolve) {
      if (pc.iceGatheringState === "complete") return resolve();
      var timer = setTimeout(resolve, 1500);
      pc.onicegatheringstatechange = function () {
        if (pc.iceGatheringState === "complete") {
          clearTimeout(timer);
          resolve();
        }
      };
    });

    self._setState("connecting", "sending offer");

    var deadline = Date.now() + 30000;
    var resp = null;
    while (Date.now() < deadline) {
      resp = await fetch(self.whepUrl, {
        method: "POST",
        headers: { "Content-Type": "application/sdp" },
        body: pc.localDescription.sdp
      }).catch(function () { return null; });

      if (resp && resp.status === 404) {
        // 404 means the pipeline has not published yet, not that
        // signalling failed; retry on a fixed interval until the path
        // appears or the timeout elapses.
        self._setState("connecting", "waiting for stream...");
        await sleep(1500);
        continue;
      }
      break;
    }

    if (!resp || !resp.ok) {
      self._setState("error", "signalling rejected" + (resp ? " (" + resp.status + ")" : ""));
      return;
    }

    var loc = resp.headers.get("Location");
    if (loc) {
      self.resourceUrl = new URL(loc, document.baseURI).toString();
    }

    var answerSdp = await resp.text();
    await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });
  };

  WhepSession.prototype.stop = async function () {
    this.closed = true;
    if (this.resourceUrl) {
      try {
        await fetch(this.resourceUrl, { method: "DELETE" });
      } catch (e) { /* best-effort teardown */ }
    }
    if (this.pc) {
      try { this.pc.close(); } catch (e) { /* already closed */ }
      this.pc = null;
    }
  };

  // Shared namespace for the controller modules (FRONTEND-SPEC.md 0).
  global.Console = global.Console || {};
  global.Console.Whep = { WhepSession: WhepSession, discoverIceServers: discoverIceServers };

  global.MissionConsoleWhep = {
    WhepSession: WhepSession,
    discoverIceServers: discoverIceServers,
    parseLinkHeader: parseLinkHeader
  };
})(window);
