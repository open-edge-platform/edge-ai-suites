/**
 * Metrics collector service for the bundled metrics-manager microservice.
 *
 * Consumes the Server-Sent Events stream exposed by metrics-manager
 * (GET /metrics/stream on port 9090) and renders CPU, RAM, GPU and NPU
 * utilization percentages.
 *
 * The stream emits events shaped as:
 *   { "timestamp": <ms>, "metrics": [ { "name", "labels", "value", "timestamp" }, ... ] }
 * where metric names are flattened (measurement + "_" + field). Only the
 * usage-percentage series are consumed: "cpu_usage_user", "mem_used_percent",
 * "gpu_engine_usage_usage" and "npu_utilization". On multi-GPU hosts, GPU
 * samples are grouped by labels.gpu_id first to avoid cross-device overwrites.
 * Each detected GPU is rendered as its own chart line and header value.
 */
const MetricsCollectorService = (function () {
    let metricsSource = null;
    let reconnectTimeout = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 10;
    const reconnectDelay = 3000;

    // Metrics service configuration - uses runtime config from backend
    function getMetricsServiceUrl() {
        // Check for explicit metrics service URL configuration
        if (window.METRICS_SERVICE_URL) {
            return window.METRICS_SERVICE_URL;
        }

        const cfg = window.RUNTIME_CONFIG || {};
        // metrics-manager serves the SSE stream over plain HTTP(S), not WS.
        const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
        const host = window.location.hostname;
        const port = cfg.metricsServicePort || window.METRICS_SERVICE_PORT || '9090';
        return `${protocol}//${host}:${port}/metrics/stream`;
    }

    function processCollectorMetrics(metrics, elements) {
        const { cpuVal, ramVal, gpuValues, gpuError, npuVal, npuStat } = elements;

        // Per-batch accumulators
        const gpuEngineDataByDevice = new Map();
        let cpuUtilization = null;
        let ramUtilization = null;
        let npuUtilization = null;

        function getGpuDeviceId(labels) {
            // Prefer Telegraf qmassa_reader gpu_id for multi-GPU correctness.
            if (labels.gpu_id !== undefined && labels.gpu_id !== null) {
                return String(labels.gpu_id);
            }
            // Backward-compatible fallbacks for alternate exporters.
            if (labels.device !== undefined && labels.device !== null) {
                return String(labels.device);
            }
            if (labels.card !== undefined && labels.card !== null) {
                return String(labels.card);
            }
            return '0';
        }

        metrics.forEach(metric => {
            const { name, value } = metric;
            const labels = metric.labels || {};

            switch (name) {
                case 'cpu_usage_user':
                    // Prefer the aggregate "cpu-total" series when present.
                    if (labels.cpu === undefined || labels.cpu === 'cpu-total') {
                        cpuUtilization = value;
                        if (cpuVal) cpuVal.textContent = `${value.toFixed(1)}%`;
                    }
                    break;

                case 'mem_used_percent':
                    ramUtilization = value;
                    if (ramVal) ramVal.textContent = `${value.toFixed(1)}%`;
                    break;

                case 'gpu_engine_usage_usage':
                    if (labels.engine) {
                        const deviceId = getGpuDeviceId(labels);
                        if (!gpuEngineDataByDevice.has(deviceId)) {
                            gpuEngineDataByDevice.set(deviceId, new Map());
                        }
                        gpuEngineDataByDevice.get(deviceId).set(labels.engine.toUpperCase(), value);
                    }
                    break;

                case 'npu_utilization':
                    npuUtilization = value;
                    break;
            }
        });

        const frameSamples = {};
        if (cpuUtilization !== null) {
            frameSamples.cpu = cpuUtilization;
        }
        if (ramUtilization !== null) {
            frameSamples.ram = ramUtilization;
        }

        // GPU usage: compute max across engines for each GPU device.
        if (gpuEngineDataByDevice.size > 0) {
            const perGpuUsage = Array.from(gpuEngineDataByDevice.entries())
                .map(([deviceId, engineMap]) => ({
                    deviceId,
                    usage: Math.max(...Array.from(engineMap.values())),
                }))
                .sort((a, b) => {
                    const aNum = Number(a.deviceId);
                    const bNum = Number(b.deviceId);
                    if (Number.isNaN(aNum) || Number.isNaN(bNum)) {
                        return a.deviceId.localeCompare(b.deviceId);
                    }
                    return aNum - bNum;
                });

            perGpuUsage.forEach((entry) => {
                frameSamples[`gpu:${entry.deviceId}`] = entry.usage;
            });

            if (gpuValues) {
                gpuValues.innerHTML = '';
                perGpuUsage.forEach((entry) => {
                    const chip = document.createElement('span');
                    chip.className = 'gpu-value-chip';
                    const key = `gpu:${entry.deviceId}`;
                    chip.style.color = ChartManager.getSeriesColor(key);
                    chip.textContent = `GPU-${entry.deviceId} ${entry.usage.toFixed(1)}%`;
                    gpuValues.appendChild(chip);
                });
                gpuValues.style.display = '';
            }

            if (gpuError) gpuError.style.display = 'none';
        } else if (gpuValues) {
            gpuValues.innerHTML = '';
            gpuValues.style.display = 'none';
        }

        // NPU usage (only when NPU metrics arrive)
        if (npuUtilization !== null) {
            frameSamples.npu = npuUtilization;

            if (npuVal) {
                npuVal.textContent = `${npuUtilization.toFixed(1)}%`;
            }
            // Reveal the NPU stat only once data is present
            if (npuStat) npuStat.style.display = '';
        }

        if (Object.keys(frameSamples).length > 0) {
            ChartManager.pushStatFrame(frameSamples);
        }
    }

    function setConnectionStatus(connected) {
        const collectorStatus = document.getElementById('collectorStatus');
        const collectorStatusDot = document.getElementById('collectorStatusDot');
        if (collectorStatus) {
            collectorStatus.textContent = connected ? 'Connected' : 'Disconnected';
            collectorStatus.className = connected ? 'status-connected' : 'status-disconnected';
        }
        if (collectorStatusDot) {
            collectorStatusDot.classList.toggle('active', connected);
        }
    }

    function init(elements) {
        // Initialize consolidated chart
        ChartManager.createConsolidatedChart('statsChart', [
            { key: 'cpu', label: 'CPU %', color: '#1ad0ff' },
            { key: 'ram', label: 'RAM %', color: '#8ca0c2' },
            { key: 'npu', label: 'NPU %', color: '#b388ff' },
        ]);

        const streamUrl = getMetricsServiceUrl();

        function connectMetricsStream() {
            if (metricsSource && metricsSource.readyState !== EventSource.CLOSED) {
                console.log('Metrics SSE already connected or connecting');
                return;
            }

            console.log('Connecting to metrics-manager SSE stream:', streamUrl);
            metricsSource = new EventSource(streamUrl);

            metricsSource.onopen = () => {
                console.log('Metrics SSE connected');
                reconnectAttempts = 0;
                setConnectionStatus(true);
            };

            metricsSource.onmessage = (event) => {
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

            metricsSource.onerror = () => {
                // EventSource auto-reconnects while the connection is open; only
                // intervene with manual backoff once it has fully closed.
                setConnectionStatus(false);

                if (metricsSource.readyState === EventSource.CLOSED) {
                    metricsSource.close();
                    metricsSource = null;

                    if (reconnectAttempts < maxReconnectAttempts) {
                        reconnectAttempts++;
                        console.log(`Attempting to reconnect (${reconnectAttempts}/${maxReconnectAttempts})...`);
                        reconnectTimeout = setTimeout(connectMetricsStream, reconnectDelay);
                    } else {
                        console.error('Max reconnect attempts reached for metrics SSE');
                    }
                }
            };
        }

        // Start connection
        connectMetricsStream();

        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            if (reconnectTimeout) {
                clearTimeout(reconnectTimeout);
            }
            if (metricsSource) {
                metricsSource.close();
            }
        });
    }

    return {
        init
    };
})();
