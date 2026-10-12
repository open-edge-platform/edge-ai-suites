/* Copyright (C) 2026 Intel Corporation */
/* SPDX-License-Identifier: Apache-2.0 */

/**
 * WebRTC/WHEP transport service.
 * Handles SDP handshake, remote stream binding, and session cleanup.
 */

import { whepUrl } from "../config/runtime.js";

function waitForIceGathering(pc, timeoutMs = 2500) {
    if (pc.iceGatheringState === "complete") return Promise.resolve();

    return new Promise((resolve) => {
        let done = false;

        const finish = () => {
            if (done) return;
            done = true;
            pc.removeEventListener("icegatheringstatechange", onChange);
            resolve();
        };

        const onChange = () => {
            if (pc.iceGatheringState === "complete") finish();
        };

        pc.addEventListener("icegatheringstatechange", onChange);
        setTimeout(finish, timeoutMs);
    });
}

export async function startWhepPlayback(streamId, videoElement) {
    const pc = new RTCPeerConnection();
    let sessionUrl = "";

    pc.addTransceiver("video", { direction: "recvonly" });
    pc.ontrack = (event) => {
        const stream = event.streams && event.streams[0];
        if (!stream) return;

        videoElement.srcObject = stream;
        videoElement.play().catch(() => {
            // autoplay may be blocked
        });
    };

    await pc.setLocalDescription(await pc.createOffer());
    await waitForIceGathering(pc);

    const resp = await fetch(whepUrl(streamId), {
        method: "POST",
        headers: { "Content-Type": "application/sdp" },
        body: pc.localDescription?.sdp || "",
    });

    if (!resp.ok) {
        pc.close();
        throw new Error(`WHEP handshake failed: HTTP ${resp.status}`);
    }

    const location = resp.headers.get("Location") || resp.headers.get("location");
    if (location) {
        sessionUrl = new URL(location, whepUrl(streamId)).toString();
    }

    const answer = await resp.text();
    await pc.setRemoteDescription({ type: "answer", sdp: answer });

    const cleanup = () => {
        try {
            pc.close();
        } catch (_err) {
            // ignore
        }
        if (sessionUrl) {
            fetch(sessionUrl, { method: "DELETE" }).catch(() => {
                // best effort
            });
        }
    };

    return { pc, cleanup };
}
