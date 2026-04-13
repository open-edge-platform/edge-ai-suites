/**
 * Metadata stream service for SSE handling
 */
const MetadataStreamService = (function() {
    let metadataSource = null;
    let reconnectTimer = null;
    const runUIs = new Map();
    const lastCaptionTime = new Map();
    const captionHistoryByRun = new Map();
    const MAX_CAPTION_BUFFER = 20;
    let captionHistoryCount = null;
    let onRunErrorCallback = null;

    function normalizeCaptionHistory(value, fallback = 3) {
        const parsed = Number.parseInt(value, 10);
        if (!Number.isFinite(parsed)) return fallback;
        return Math.max(0, parsed);
    }

    function getVisibleCaptionLimit() {
        const effectiveCount = captionHistoryCount === null ? 3 : captionHistoryCount;
        return effectiveCount + 1;
    }

    function shouldAutoScroll(timelineEl) {
        if (!timelineEl) return true;
        if (timelineEl.scrollHeight <= timelineEl.clientHeight) return true;
        return timelineEl.scrollTop <= 12;
    }

    function formatStreamSeconds(seconds) {
        if (!Number.isFinite(seconds)) return '—';
        const safeSeconds = Math.max(0, seconds);
        const minutes = Math.floor(safeSeconds / 60);
        const remaining = safeSeconds - (minutes * 60);
        const secondsText = remaining.toFixed(2).padStart(5, '0');
        return `${String(minutes).padStart(2, '0')}:${secondsText}`;
    }

    function formatTimelinePositionLabel(index) {
        if (index === 0) return 'Latest';
        if (index === 1) return '1 back';
        return `${index} back`;
    }

    function formatCaptionTimestamp(data) {
        if (data && data.timestamp_seconds !== undefined) {
            return `${formatStreamSeconds(data.timestamp_seconds)}`;
        }
        if (data && data.timestamp) {
            return `at ${new Date(data.timestamp).toLocaleTimeString()}`;
        }
        return `at ${new Date().toLocaleTimeString()}`;
    }

    function renderCaptionTimeline(ui, entries) {
        const timelineEl = ui?.captionTimeline;
        if (!timelineEl) return;

        const keepPinnedToLatest = shouldAutoScroll(timelineEl);
        timelineEl.innerHTML = '';

        if (!entries || entries.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'caption-entry caption-entry-placeholder';
            empty.textContent = 'Waiting for live captions...';
            timelineEl.appendChild(empty);
            return;
        }

        for (let index = 0; index < entries.length; index++) {
            const item = entries[index];
            const row = document.createElement('article');
            row.className = 'caption-entry';

            const meta = document.createElement('div');
            meta.className = 'caption-entry-meta';
            const timelineLabel = formatTimelinePositionLabel(index);
            meta.textContent = `${timelineLabel} • ${item.timestampLabel}`;

            const text = document.createElement('p');
            text.className = 'caption-entry-text';
            text.textContent = item.captionText;

            row.appendChild(meta);
            row.appendChild(text);
            timelineEl.appendChild(row);
        }

        if (keepPinnedToLatest) {
            timelineEl.scrollTop = 0;
        }
    }

    function updateRunCaptionHistory(runId, ui, data, captionText) {
        const history = captionHistoryByRun.get(runId) || [];
        history.unshift({
            captionText,
            timestampLabel: formatCaptionTimestamp(data),
        });

        if (history.length > MAX_CAPTION_BUFFER) {
            history.length = MAX_CAPTION_BUFFER;
        }

        captionHistoryByRun.set(runId, history);
        renderCaptionTimeline(ui, history.slice(0, getVisibleCaptionLimit()));
    }

    function rerenderAllCaptionHistories() {
        const visibleLimit = getVisibleCaptionLimit();
        for (const [runId, ui] of runUIs) {
            const history = captionHistoryByRun.get(runId) || [];
            renderCaptionTimeline(ui, history.slice(0, visibleLimit));
        }
    }

    function initMultiplexedMetadataStream(cfg) {
        // Single SSE connection for all run metadata to avoid browser connection limits
        if (metadataSource) {
            return; // Already initialized
        }

        // Respect value already chosen by UI/localStorage. Backend default is fallback only.
        if (captionHistoryCount === null) {
            const runtimeCaptionHistory = cfg?.captionHistory;
            captionHistoryCount = normalizeCaptionHistory(runtimeCaptionHistory, 3);
        }

        console.log('Initializing multiplexed metadata stream...');
        metadataSource = new EventSource('/api/runs/metadata-stream');

        metadataSource.onopen = () => {
            console.log('Multiplexed metadata stream connected');
        };

        metadataSource.onmessage = (event) => {
            if (!event.data) return;

            try {
                const msg = JSON.parse(event.data);

                // Handle run-status heartbeats emitted when no MQTT message arrives.
                // Each heartbeat carries {type:"status", runs:{runId: status, ...}}.
                if (msg.type === 'status' && msg.runs) {
                    for (const [runId, status] of Object.entries(msg.runs)) {
                        if (status !== 'error') continue;
                        const ui = runUIs.get(runId);
                        if (!ui || ui._errorStateShown) continue;
                        ui._errorStateShown = true;
                        if (onRunErrorCallback) onRunErrorCallback(runId, ui);
                    }
                    return;
                }

                const runId = msg.runId;

                if (!runId) {
                    console.warn('Received metadata without runId:', msg);
                    return;
                }

                // Handle run removal notification
                if (msg.removed) {
                    console.log(`Run ${runId} removed from server`);
                    return;
                }

                // Get the UI elements for this run
                const ui = runUIs.get(runId);
                if (!ui) {
                    console.log(`No UI found for run ${runId}, ignoring metadata`);
                    return; // No UI for this run yet
                }

                // msg.data is already parsed; extract caption and metrics directly
                const data = msg.data;
                const captionText = typeof data === 'object' && data.result ? data.result : (typeof data === 'string' ? data : JSON.stringify(data));
                updateRunCaptionHistory(runId, ui, data, captionText);

                // Alert Mode: Apply per-run configurable substring-to-color rules
                if (cfg && cfg.alertMode) {
                    const runCard = ui.wrap;
                    const captionPanel = ui.captionPanel;
                    const lowerCaption = captionText ? captionText.toLowerCase() : '';

                    // Clear inline color state
                    for (const el of [runCard, captionPanel]) {
                        if (!el) continue;
                        el.classList.remove('alert-1', 'alert-2', 'alert-3');
                        el.style.removeProperty('--alert-color');
                        el.style.removeProperty('--alert-color-rgb');
                    }

                    // Use per-run configured rules (no defaults — empty means no alerts)
                    const rules = (ui.alertRules && ui.alertRules.length > 0) ? ui.alertRules : [];

                    // Apply first matching rule (alert-1, alert-2, alert-3 based on rule index)
                    for (let i = 0; i < rules.length; i++) {
                        const rule = rules[i];
                        if (!rule.substring) continue;
                        if (lowerCaption.includes(rule.substring.toLowerCase())) {
                            const hex = rule.color || '#ff4444';
                            const rgb = hexToRgb(hex);
                            const alertClass = 'alert-' + (i + 1);
                            for (const el of [runCard, captionPanel]) {
                                if (!el) continue;
                                el.style.setProperty('--alert-color', hex);
                                if (rgb) el.style.setProperty('--alert-color-rgb', rgb);
                                el.classList.add(alertClass);
                            }
                            break;
                        }
                    }
                }

                // Extract metrics from the data object
                const metrics = (typeof data === 'object' && data.metrics) ? data.metrics : {};
                const throughput = metrics.throughput_mean;
                const timestampText =
                    data.timestamp_seconds !== undefined
                        ? `Updated ${data.timestamp_seconds.toFixed(2)}s into stream`
                        : data.timestamp
                        ? `Updated at ${new Date(data.timestamp).toLocaleTimeString()}`
                        : '—';
                ui.chips.querySelector('[data-ttft]').textContent = metrics.ttft_mean ? `${metrics.ttft_mean.toFixed(0)} ms` : '—';
                ui.chips.querySelector('[data-tpot]').textContent = metrics.tpot_mean ? `${metrics.tpot_mean.toFixed(2)} ms` : '—';
                ui.chips.querySelector('[data-throughput]').textContent = throughput ? `${throughput.toFixed(2)} tok/s` : '—';

                // Calculate lag: time since this caption was received by the browser
                // We use the browser's own timestamp to avoid clock sync issues with the container
                const receivedAtMs = Date.now();
                // Store when this run last received a caption update
                lastCaptionTime.set(runId, receivedAtMs);
                ui.chips.querySelector('[data-lag]').textContent = '0.00s';

                ui.timestamp.textContent = timestampText;

                console.log(`Updated metadata for run ${runId}`);
            } catch (err) {
                console.error('Error parsing metadata:', err, 'Event data:', event.data);
            }
        };

        metadataSource.onerror = (event) => {
            console.error('Metadata stream error:', event);
            // Cancel any pending reconnect before scheduling a new one to prevent
            // multiple concurrent EventSource instances on rapid error bursts.
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
            reconnectTimer = setTimeout(() => {
                reconnectTimer = null;
                if (metadataSource && metadataSource.readyState === EventSource.CLOSED) {
                    console.log('Reconnecting metadata stream...');
                    metadataSource = null;
                    initMultiplexedMetadataStream(cfg);
                }
            }, 5000);
        };

        metadataSource.onclose = () => {
            console.log('Metadata stream closed');
            metadataSource = null;
        };
    }

    function registerRunUI(runId, ui) {
        runUIs.set(runId, ui);
        const history = captionHistoryByRun.get(runId) || [];
        renderCaptionTimeline(ui, history.slice(0, getVisibleCaptionLimit()));
    }

    function unregisterRunUI(runId) {
        runUIs.delete(runId);
        lastCaptionTime.delete(runId);
        captionHistoryByRun.delete(runId);
    }

    function setOnRunError(callback) {
        onRunErrorCallback = callback;
    }

    function getLastCaptionTime(runId) {
        return lastCaptionTime.get(runId);
    }

    function hexToRgb(hex) {
        const m = /^#([0-9a-f]{3,6})$/i.exec(hex.trim());
        if (!m) return null;
        let h = m[1];
        if (h.length === 3) h = h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
        const n = parseInt(h, 16);
        return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`;
    }

    function getRunUIs() {
        return runUIs;
    }

    function setCaptionHistoryLimit(value) {
        const fallback = captionHistoryCount === null ? 3 : captionHistoryCount;
        captionHistoryCount = normalizeCaptionHistory(value, fallback);
        rerenderAllCaptionHistories();
    }

    function getCaptionHistoryLimit() {
        return captionHistoryCount === null ? 3 : captionHistoryCount;
    }

    function close() {
        if (metadataSource) {
            console.log('Closing metadata stream');
            metadataSource.close();
            metadataSource = null;
        }
    }

    return {
        initMultiplexedMetadataStream,
        registerRunUI,
        unregisterRunUI,
        setOnRunError,
        getLastCaptionTime,
        getRunUIs,
        setCaptionHistoryLimit,
        getCaptionHistoryLimit,
        close
    };
})();
