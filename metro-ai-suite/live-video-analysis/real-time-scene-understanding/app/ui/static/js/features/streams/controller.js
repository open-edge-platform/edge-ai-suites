/* Copyright (C) 2026 Intel Corporation */
/* SPDX-License-Identifier: Apache-2.0 */

/**
 * Streams feature controller.
 * Owns stream CRUD UX, card lifecycle, polling, and playback orchestration.
 */

import { addStream, deleteStream, fetchStreams } from "../../services/api.js";
import { startWhepPlayback } from "../../services/webrtc.js";
import {
    formatVlmResponseHistory,
    formatVlmMetrics,
    sanitizeStreamId,
} from "../../utils/stream.js";

const POLL_INTERVAL_MS = 2000;
const VLM_HISTORY_LIMIT = 3;

const PROMPT_TYPE_ALERT = "alert";
const PROMPT_TYPE_DEEP_ANALYZER = "deep-analyzer";

export function createStreamsController(elements, { openAlertDrawer }) {
    const {
        statusPill,
        rtspForm,
        rtspInput,
        streamIdInput,
        alertPromptInput,
        deepAnalyzerPromptInput,
        rtspSubmit,
        rtspMessage,
        streamsGrid,
        streamsEmpty,
    } = elements;

    const players = new Map();
    let autoStreamCounter = 1;

    function nextStreamId() {
        const id = `stream-${Date.now()}-${autoStreamCounter}`;
        autoStreamCounter += 1;
        return id;
    }

    function setStatus(text, kind) {
        statusPill.textContent = text;
        statusPill.className = `pill pill--${kind}`;
    }

    function setRtspMessage(message, isError = false) {
        rtspMessage.textContent = message;
        rtspMessage.style.color = isError ? "var(--err)" : "var(--muted)";
    }

    function updateStatusFromPlayers() {
        const values = Array.from(players.values());
        const liveCount = values.filter((p) => p.stream?.publishing && p.playback).length;
        const total = values.length;

        if (total === 0) {
            setStatus("no stream", "idle");
            return;
        }
        if (liveCount > 0) {
            setStatus(`${liveCount}/${total} live`, "ok");
            return;
        }
        setStatus("waiting for source", "idle");
    }

    function setCardOverlay(player, text, show = true) {
        player.overlay.textContent = text;
        player.overlay.style.display = show ? "flex" : "none";
    }

    function teardownPlayer(streamId, message = "Reconnecting...") {
        const player = players.get(streamId);
        if (!player) return;

        if (player.playback) {
            player.playback.cleanup();
            player.playback = null;
        }
        player.video.srcObject = null;
        setCardOverlay(player, message, true);
    }

    async function connectPlayer(streamId) {
        const player = players.get(streamId);
        if (!player || player.connecting || player.playback) return;
        if (!player.stream?.publishing) {
            setCardOverlay(player, "Waiting for publisher...", true);
            return;
        }

        player.connecting = true;
        setCardOverlay(player, "Connecting...", true);
        try {
            player.playback = await startWhepPlayback(streamId, player.video);
            player.playback.pc.addEventListener("connectionstatechange", () => {
                const connState = player.playback?.pc.connectionState;
                if (connState === "connected") {
                    setCardOverlay(player, "", false);
                }
                if (connState === "failed" || connState === "disconnected" || connState === "closed") {
                    teardownPlayer(streamId);
                }
                updateStatusFromPlayers();
            });
        } catch (_err) {
            teardownPlayer(streamId, "Unable to connect. Retrying...");
        } finally {
            player.connecting = false;
            updateStatusFromPlayers();
        }
    }

    function removeCard(streamId) {
        const player = players.get(streamId);
        if (!player) return;

        teardownPlayer(streamId, "Stopped");
        player.card.remove();
        players.delete(streamId);

        streamsEmpty.style.display = players.size === 0 ? "block" : "none";
        updateStatusFromPlayers();
    }

    async function stopStream(streamId, button) {
        button.disabled = true;
        try {
            await deleteStream(streamId);
            removeCard(streamId);
            setRtspMessage(`Stopped stream '${streamId}'.`);
        } catch (err) {
            const message = err instanceof Error ? err.message : "Failed to stop stream.";
            setRtspMessage(message, true);
            button.disabled = false;
        }
    }

    function getPromptText(stream, promptType) {
        if (promptType === PROMPT_TYPE_ALERT) {
            return String(stream.alert_prompt || "").trim();
        }
        if (promptType === PROMPT_TYPE_DEEP_ANALYZER) {
            return String(stream.deep_analyzer_prompt || "").trim();
        }
        return "";
    }

    function getPromptLabel(promptType) {
        if (promptType === PROMPT_TYPE_ALERT) {
            return "Alert Prompt";
        }
        if (promptType === PROMPT_TYPE_DEEP_ANALYZER) {
            return "Deep Analyzer Prompt";
        }
        return "Prompt";
    }

    function setPromptView(player, promptType = null) {
        if (!player.promptView) return;

        if (!promptType) {
            player.activePromptType = null;
            player.promptView.textContent = "";
            player.promptView.classList.add("stream-prompt-view--hidden");
            if (player.alertPromptTag) {
                player.alertPromptTag.classList.remove("stream-prompt-tag--active");
                player.alertPromptTag.setAttribute("aria-expanded", "false");
            }
            if (player.deepAnalyzerPromptTag) {
                player.deepAnalyzerPromptTag.classList.remove("stream-prompt-tag--active");
                player.deepAnalyzerPromptTag.setAttribute("aria-expanded", "false");
            }
            return;
        }

        const promptText = getPromptText(player.stream, promptType);
        if (!promptText) {
            setPromptView(player, null);
            return;
        }

        player.activePromptType = promptType;
        player.promptView.textContent = `${getPromptLabel(promptType)}: ${promptText}`;
        player.promptView.classList.remove("stream-prompt-view--hidden");

        const isAlert = promptType === PROMPT_TYPE_ALERT;
        if (player.alertPromptTag) {
            player.alertPromptTag.classList.toggle("stream-prompt-tag--active", isAlert);
            player.alertPromptTag.setAttribute("aria-expanded", isAlert ? "true" : "false");
        }
        if (player.deepAnalyzerPromptTag) {
            player.deepAnalyzerPromptTag.classList.toggle("stream-prompt-tag--active", !isAlert);
            player.deepAnalyzerPromptTag.setAttribute("aria-expanded", !isAlert ? "true" : "false");
        }
    }

    function handlePromptTagClick(player, promptType) {
        const isSamePrompt = player.activePromptType === promptType;
        if (isSamePrompt) {
            setPromptView(player, null);
            return;
        }
        setPromptView(player, promptType);
    }

    function syncPromptTags(player, stream) {
        if (!player.promptTags) return;

        const hasAlertPrompt = Boolean(getPromptText(stream, PROMPT_TYPE_ALERT));
        const hasDeepPrompt = Boolean(getPromptText(stream, PROMPT_TYPE_DEEP_ANALYZER));
        const hasAnyPrompt = hasAlertPrompt || hasDeepPrompt;

        if (player.alertPromptTag) {
            player.alertPromptTag.hidden = !hasAlertPrompt;
        }
        if (player.deepAnalyzerPromptTag) {
            player.deepAnalyzerPromptTag.hidden = !hasDeepPrompt;
        }

        player.promptTags.classList.toggle("stream-prompt-tags--hidden", !hasAnyPrompt);

        if (!hasAnyPrompt) {
            setPromptView(player, null);
            return;
        }

        if (player.activePromptType && !getPromptText(stream, player.activePromptType)) {
            setPromptView(player, null);
            return;
        }

        if (player.activePromptType) {
            setPromptView(player, player.activePromptType);
        }
    }

    function createCard(stream) {
        const card = document.createElement("article");
        card.className = "stream-card";

        const head = document.createElement("div");
        head.className = "stream-head";

        const idText = document.createElement("h3");
        idText.className = "stream-id";
        idText.textContent = stream.stream_id;

        const stopButton = document.createElement("button");
        stopButton.className = "stream-stop";
        stopButton.type = "button";
        stopButton.textContent = "Stop";

        const actions = document.createElement("div");
        actions.className = "stream-actions";

        const alertBell = document.createElement("button");
        alertBell.className = "stream-alert-bell";
        alertBell.type = "button";
        alertBell.innerHTML = '\uD83D\uDD14<span class="stream-alert-bell__badge" hidden>0</span>';
        alertBell.setAttribute("aria-label", "View alert history");

        const promptTags = document.createElement("div");
        promptTags.className = "stream-prompt-tags stream-prompt-tags--hidden";

        const alertPromptTag = document.createElement("button");
        alertPromptTag.type = "button";
        alertPromptTag.className = "stream-prompt-tag";
        alertPromptTag.textContent = "Alert Prompt";
        alertPromptTag.setAttribute("aria-expanded", "false");

        const deepAnalyzerPromptTag = document.createElement("button");
        deepAnalyzerPromptTag.type = "button";
        deepAnalyzerPromptTag.className = "stream-prompt-tag";
        deepAnalyzerPromptTag.textContent = "Deep Analyzer Prompt";
        deepAnalyzerPromptTag.setAttribute("aria-expanded", "false");

        promptTags.appendChild(alertPromptTag);
        promptTags.appendChild(deepAnalyzerPromptTag);

        const promptView = document.createElement("p");
        promptView.className = "stream-prompt-view stream-prompt-view--hidden";

        const meta = document.createElement("p");
        meta.className = "stream-meta";

        const frame = document.createElement("div");
        frame.className = "stream-frame";
        const video = document.createElement("video");
        video.autoplay = true;
        video.muted = true;
        video.playsInline = true;
        const overlay = document.createElement("div");
        overlay.className = "stream-overlay";
        overlay.textContent = "Waiting for publisher...";

        const vlmMetrics = document.createElement("div");
        vlmMetrics.className = "stream-vlm-metrics";
        vlmMetrics.textContent = "TTFT: - ms | TPOT: - ms | Throughput: - tok/s";

        const vlmResponse = document.createElement("div");
        vlmResponse.className = "stream-vlm-response";

        const vlmResponseHistory = document.createElement("ol");
        vlmResponseHistory.className = "stream-vlm-response__history";

        const initialHistoryItem = document.createElement("li");
        initialHistoryItem.className = "stream-vlm-response__item stream-vlm-response__item--placeholder";
        initialHistoryItem.textContent = "Awaiting response...";
        vlmResponseHistory.appendChild(initialHistoryItem);

        vlmResponse.appendChild(vlmResponseHistory);

        frame.appendChild(video);
        frame.appendChild(overlay);
        head.appendChild(idText);
        actions.appendChild(alertBell);
        actions.appendChild(stopButton);
        head.appendChild(actions);
        card.appendChild(head);
        card.appendChild(meta);
        card.appendChild(promptTags);
        card.appendChild(promptView);
        card.appendChild(frame);
        card.appendChild(vlmMetrics);
        card.appendChild(vlmResponse);
        streamsGrid.appendChild(card);

        const player = {
            stream,
            card,
            video,
            overlay,
            meta,
            promptTags,
            alertPromptTag,
            deepAnalyzerPromptTag,
            promptView,
            activePromptType: null,
            alertBell,
            alertCountSeen: null,
            alertPulseTimeout: null,
            vlmResponse,
            vlmResponseHistory,
            vlmMetrics,
            stopButton,
            playback: null,
            connecting: false,
        };
        players.set(stream.stream_id, player);

        video.addEventListener("loadeddata", () => {
            setCardOverlay(player, "", false);
            updateStatusFromPlayers();
        });
        stopButton.addEventListener("click", () => {
            stopStream(stream.stream_id, stopButton);
        });
        alertBell.addEventListener("click", () => {
            alertBell.classList.remove("stream-alert-bell--pulse");
            if (player.alertPulseTimeout) {
                clearTimeout(player.alertPulseTimeout);
                player.alertPulseTimeout = null;
            }
            openAlertDrawer(stream.stream_id);
        });
        alertPromptTag.addEventListener("click", () => {
            handlePromptTagClick(player, PROMPT_TYPE_ALERT);
        });
        deepAnalyzerPromptTag.addEventListener("click", () => {
            handlePromptTagClick(player, PROMPT_TYPE_DEEP_ANALYZER);
        });

        return player;
    }

    function syncPlayerCard(player, stream) {
        player.stream = stream;
        player.meta.textContent = stream.url || "";

        syncPromptTags(player, stream);

        if (player.vlmMetrics) {
            player.vlmMetrics.textContent = formatVlmMetrics(stream);
        }

        if (player.vlmResponseHistory) {
            const history = formatVlmResponseHistory(stream, VLM_HISTORY_LIMIT);
            player.vlmResponseHistory.innerHTML = "";

            if (history.length === 0) {
                const placeholderItem = document.createElement("li");
                placeholderItem.className = "stream-vlm-response__item stream-vlm-response__item--placeholder";
                placeholderItem.textContent = "Awaiting response...";
                player.vlmResponseHistory.appendChild(placeholderItem);
            } else {
                history.forEach((response, index) => {
                    const item = document.createElement("li");
                    item.className = "stream-vlm-response__item";
                    item.classList.toggle("stream-vlm-response__item--alert", Boolean(response.alert));

                    const meta = document.createElement("p");
                    meta.className = "stream-vlm-response__meta";
                    meta.textContent = response.timeLabel
                        ? `${response.label} \u2022 ${response.timeLabel}`
                        : response.label;

                    const text = document.createElement("p");
                    text.className = "stream-vlm-response__text";
                    text.textContent = response.text;

                    item.appendChild(meta);
                    item.appendChild(text);
                    player.vlmResponseHistory.appendChild(item);
                });
            }
        }

        if (player.alertBell) {
            const count = Number(stream.alert_count) || 0;
            const badge = player.alertBell.querySelector(".stream-alert-bell__badge");
            player.alertBell.classList.toggle("stream-alert-bell--visible", count > 0);

            if (badge) {
                badge.hidden = count === 0;
                badge.textContent = count > 99 ? "99+" : String(count);
            }

            // Only pulse for a genuine increase after the baseline is known, not on first load.
            if (player.alertCountSeen !== null && count > player.alertCountSeen) {
                player.alertBell.classList.remove("stream-alert-bell--pulse");
                void player.alertBell.offsetWidth; // restart animation if already pulsing
                player.alertBell.classList.add("stream-alert-bell--pulse");
                if (player.alertPulseTimeout) clearTimeout(player.alertPulseTimeout);
                player.alertPulseTimeout = setTimeout(() => {
                    player.alertBell.classList.remove("stream-alert-bell--pulse");
                    player.alertPulseTimeout = null;
                }, 2400);
            }
            player.alertCountSeen = count;
        }

        if (stream.publishing) {
            if (!player.playback) {
                setCardOverlay(player, "Connecting...", true);
                connectPlayer(stream.stream_id);
            }
        } else if (!player.playback && !player.connecting) {
            setCardOverlay(player, "Waiting for publisher...", true);
        }
    }

    async function pollHealth() {
        try {
            const streams = await fetchStreams();
            const seen = new Set();

            streams.forEach((stream) => {
                seen.add(stream.stream_id);
                let player = players.get(stream.stream_id);
                if (!player) {
                    player = createCard(stream);
                }
                syncPlayerCard(player, stream);
            });

            Array.from(players.keys()).forEach((streamId) => {
                if (!seen.has(streamId)) {
                    removeCard(streamId);
                }
            });

            streamsEmpty.style.display = players.size === 0 ? "block" : "none";
            updateStatusFromPlayers();
        } catch (_err) {
            setStatus("offline", "err");
            setRtspMessage("Unable to fetch stream status.", true);
        }
    }

    async function onSubmitRtsp(event) {
        event.preventDefault();

        const url = rtspInput.value.trim();
        if (!url) {
            setRtspMessage("Please enter an RTSP URL.", true);
            return;
        }

        const alertPrompt = (alertPromptInput?.value || "").trim();
        if (!alertPrompt) {
            setRtspMessage("Please enter an alert prompt.", true);
            return;
        }

        const deepAnalyzerPrompt = (deepAnalyzerPromptInput?.value || "").trim();
        if (!deepAnalyzerPrompt) {
            setRtspMessage("Please enter a deep analyzer prompt.", true);
            return;
        }

        const customId = sanitizeStreamId(streamIdInput.value || "");
        const streamId = customId || nextStreamId();

        rtspSubmit.disabled = true;
        setRtspMessage(`Adding stream '${streamId}'...`);

        try {
            await addStream({ streamId, url, alertPrompt, deepAnalyzerPrompt });

            setRtspMessage(`Stream '${streamId}' added.`);
            rtspInput.value = "";
            streamIdInput.value = "";
            if (alertPromptInput) {
                alertPromptInput.value = "";
            }
            if (deepAnalyzerPromptInput) {
                deepAnalyzerPromptInput.value = "";
            }
            await pollHealth();
        } catch (err) {
            const message = err instanceof Error ? err.message : "Failed to add stream.";
            setRtspMessage(message, true);
        } finally {
            rtspSubmit.disabled = false;
        }
    }

    function bindPromptTemplateShortcut(input) {
        if (!input) return;

        input.addEventListener("keydown", (event) => {
            if (event.key !== "Enter" && event.key !== "Tab") return;
            if ((input.value || "").trim()) return;

            const template = (input.getAttribute("placeholder") || "").trim();
            if (!template) return;

            event.preventDefault();
            input.value = template;
            input.selectionStart = input.value.length;
            input.selectionEnd = input.value.length;
            input.dispatchEvent(new Event("input", { bubbles: true }));
        });
    }

    function init() {
        rtspForm.addEventListener("submit", onSubmitRtsp);
        bindPromptTemplateShortcut(alertPromptInput);
        bindPromptTemplateShortcut(deepAnalyzerPromptInput);
        pollHealth();
        setInterval(pollHealth, POLL_INTERVAL_MS);
    }

    return {
        init,
        pollHealth,
    };
}
