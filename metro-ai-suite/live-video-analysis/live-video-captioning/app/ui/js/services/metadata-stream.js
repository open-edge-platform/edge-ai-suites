/**
 * Metadata stream service for SSE handling
 */
const MetadataStreamService = (function() {
    let metadataSource = null;
    const runUIs = new Map();
    const lastCaptionTime = new Map();

    function initMultiplexedMetadataStream(cfg) {
        // Single SSE connection for all run metadata to avoid browser connection limits
        if (metadataSource) {
            return; // Already initialized
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
                ui.caption.textContent = captionText;
                
                // Agent Mode: Check for "Yes" or "No" in caption and apply alert styling
                if (cfg && cfg.agentMode) {
                    const runCard = ui.wrap;
                    const captionPanel = ui.captionPanel;
                    const lowerCaption = captionText ? captionText.toLowerCase() : '';
                    
                    if (lowerCaption.includes('yes')) {
                        // Red alert for "yes"
                        if (runCard) {
                            runCard.classList.add('alert-active');
                            runCard.classList.remove('safe-active');
                        }
                        if (captionPanel) {
                            captionPanel.classList.add('alert-active');
                            captionPanel.classList.remove('safe-active');
                        }
                    } else if (lowerCaption.includes('no')) {
                        // Green indicator for "no"
                        if (runCard) {
                            runCard.classList.add('safe-active');
                            runCard.classList.remove('alert-active');
                        }
                        if (captionPanel) {
                            captionPanel.classList.add('safe-active');
                            captionPanel.classList.remove('alert-active');
                        }
                    } else {
                        // No keyword detected - remove both states
                        if (runCard) {
                            runCard.classList.remove('alert-active');
                            runCard.classList.remove('safe-active');
                        }
                        if (captionPanel) {
                            captionPanel.classList.remove('alert-active');
                            captionPanel.classList.remove('safe-active');
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
            // EventSource will automatically try to reconnect
            // Reset the connection after a delay if it keeps failing
            setTimeout(() => {
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
    }

    function unregisterRunUI(runId) {
        runUIs.delete(runId);
        lastCaptionTime.delete(runId);
    }

    function getLastCaptionTime(runId) {
        return lastCaptionTime.get(runId);
    }

    function getRunUIs() {
        return runUIs;
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
        getLastCaptionTime,
        getRunUIs,
        close
    };
})();
