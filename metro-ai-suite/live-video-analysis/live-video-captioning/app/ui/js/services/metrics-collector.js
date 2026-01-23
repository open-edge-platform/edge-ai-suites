/**
 * Metrics collector service for WebSocket-based system metrics
 */
const MetricsCollectorService = (function() {
    let metricsWS = null;
    let reconnectTimeout = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 10;
    const reconnectDelay = 3000;

    // Data structures for tracking GPU engine metrics
    const gpuEngineData = {};
    // Track GPU power values separately for combining
    let gpuPowerValue = null;
    let pkgPowerValue = null;

    function formatEngineName(name) {
        // Format engine names for display (e.g., "rcs0" -> "RCS0", "video" -> "Video")
        if (!name) return 'Unknown';
        return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    function processCollectorMetrics(metrics, elements) {
        const { cpuVal, ramVal, gpuVal, gpuDetail, gpuEngines, gpuFreq, gpuPower, gpuTemp, gpuError } = elements;
        
        // Reset power values for this batch
        gpuPowerValue = null;
        pkgPowerValue = null;
        
        metrics.forEach(metric => {
            const { name, fields, tags } = metric;
            
            switch (name) {
                case 'cpu':
                    if (fields.usage_user !== undefined) {
                        const cpuUsage = fields.usage_user;
                        ChartManager.pushStatSample('cpu', cpuUsage);
                        
                        if (cpuVal) {
                            cpuVal.textContent = `${cpuUsage.toFixed(1)}%`;
                        }
                    }
                    break;
                
                case 'mem':
                    if (fields.used_percent !== undefined) {
                        const memUsage = fields.used_percent;
                        ChartManager.pushStatSample('ram', memUsage);
                        
                        if (ramVal) {
                            ramVal.textContent = `${memUsage.toFixed(1)}%`;
                        }
                    }
                    break;
                
                case 'gpu_engine_usage':
                    if (fields.usage !== undefined && tags.engine) {
                        const engineName = tags.engine.toUpperCase();
                        const usage = fields.usage;
                        
                        // Store engine data
                        gpuEngineData[engineName] = usage;
                    }
                    break;
                
                case 'gpu_frequency':
                    if (fields.value !== undefined && tags.type === 'cur_freq') {
                        const freqMHz = fields.value;
                        if (gpuFreq) {
                            gpuFreq.textContent = `Freq: ${freqMHz} MHz`;
                            gpuFreq.style.display = 'block';
                        }
                    }
                    break;
                
                case 'gpu_power':
                    if (fields.value !== undefined) {
                        const powerType = tags.type;
                        const powerW = fields.value;
                        
                        if (powerType === 'gpu_cur_power') {
                            gpuPowerValue = powerW;
                        } else if (powerType === 'pkg_cur_power') {
                            pkgPowerValue = powerW;
                        }
                    }
                    break;
                
                case 'temp':
                    if (fields.temp !== undefined) {
                        const tempC = fields.temp;
                        const sensor = tags.sensor || 'unknown';
                        
                        // Display package temperature
                        if (gpuTemp && sensor.includes('package')) {
                            gpuTemp.textContent = `Temp: ${tempC}°C`;
                            gpuTemp.style.display = 'block';
                        }
                    }
                    break;
                
                case 'cpu_frequency_avg':
                    // CPU frequency - could be displayed if needed
                    break;
                
                case 'fps':
                    // FPS metrics - could be displayed if needed
                    break;
            }
        });
        
        // Update GPU power display after processing all metrics
        if (gpuPower && gpuPowerValue !== null) {
            let powerText = `Power: ${gpuPowerValue.toFixed(1)}W`;
            if (pkgPowerValue !== null) {
                powerText += ` (Pkg: ${pkgPowerValue.toFixed(1)}W)`;
            }
            gpuPower.textContent = powerText;
            gpuPower.style.display = 'block';
        }
        
        // Update GPU engines display
        const engineNames = Object.keys(gpuEngineData);
        if (gpuEngines && engineNames.length > 0) {
            const engineList = engineNames
                .map(name => `${formatEngineName(name)}: ${gpuEngineData[name].toFixed(1)}%`)
                .join(' | ');
            gpuEngines.textContent = engineList;
            gpuEngines.style.display = 'block';
        }
        
        // Calculate overall GPU usage from engines
        const engineMetrics = metrics.filter(m => m.name === 'gpu_engine_usage');
        if (engineMetrics.length > 0) {
            // Use max engine usage as GPU usage (typically RCS is the main compute engine)
            const maxGpuUsage = Math.max(...engineMetrics.map(m => m.fields.usage || 0));
            ChartManager.pushStatSample('gpu', maxGpuUsage);
            
            if (gpuVal) {
                gpuVal.textContent = `${maxGpuUsage.toFixed(1)}%`;
            }
            
            // Mark GPU as available
            if (gpuDetail) gpuDetail.style.display = 'block';
            if (gpuError) gpuError.style.display = 'none';
        }
    }

    function init(elements) {
        // Initialize charts
        ChartManager.createStatChart('cpuChart', 'CPU %', '#1ad0ff');
        ChartManager.createStatChart('ramChart', 'RAM %', '#8ca0c2');
        ChartManager.createStatChart('gpuChart', 'GPU %', '#ffb347');

        // WebSocket connection to metrics collector
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/clients`;

        function connectMetricsWS() {
            if (metricsWS && (metricsWS.readyState === WebSocket.CONNECTING || metricsWS.readyState === WebSocket.OPEN)) {
                console.log('WebSocket already connected or connecting');
                return;
            }

            console.log('Connecting to metrics collector WebSocket:', wsUrl);
            metricsWS = new WebSocket(wsUrl);

            metricsWS.onopen = () => {
                console.log('Metrics WebSocket connected');
                reconnectAttempts = 0;
                
                // Update UI to show collector connected
                const collectorStatus = document.getElementById('collectorStatus');
                const collectorStatusDot = document.getElementById('collectorStatusDot');
                if (collectorStatus) {
                    collectorStatus.textContent = 'Connected';
                    collectorStatus.className = 'status-connected';
                }
                if (collectorStatusDot) {
                    collectorStatusDot.classList.add('active');
                }
            };

            metricsWS.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (!data.metrics || !Array.isArray(data.metrics)) {
                        return;
                    }

                    processCollectorMetrics(data.metrics, elements);
                } catch (err) {
                    console.error('Error parsing metrics message:', err);
                }
            };

            metricsWS.onerror = (error) => {
                console.error('Metrics WebSocket error:', error);
            };

            metricsWS.onclose = () => {
                console.log('Metrics WebSocket closed');
                
                // Update UI to show collector disconnected
                const collectorStatus = document.getElementById('collectorStatus');
                const collectorStatusDot = document.getElementById('collectorStatusDot');
                if (collectorStatus) {
                    collectorStatus.textContent = 'Disconnected';
                    collectorStatus.className = 'status-disconnected';
                }
                if (collectorStatusDot) {
                    collectorStatusDot.classList.remove('active');
                }

                // Attempt to reconnect
                if (reconnectAttempts < maxReconnectAttempts) {
                    reconnectAttempts++;
                    console.log(`Attempting to reconnect (${reconnectAttempts}/${maxReconnectAttempts})...`);
                    reconnectTimeout = setTimeout(connectMetricsWS, reconnectDelay);
                } else {
                    console.error('Max reconnect attempts reached for metrics WebSocket');
                }
            };
        }

        // Start connection
        connectMetricsWS();
        
        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            if (reconnectTimeout) {
                clearTimeout(reconnectTimeout);
            }
            if (metricsWS) {
                metricsWS.close();
            }
        });
    }

    return {
        init
    };
})();
