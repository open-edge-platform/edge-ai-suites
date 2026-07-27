/**
 * API service for backend communication
 */
const ApiService = (function () {
    const DEFAULT_MODEL = 'InternVL2-1B';
    // Full ModelInfo list cached for filtering: [{name, device}, ...]
    let allModels = [];
    // Sentinel value stored in allModels when the API call itself failed
    let modelsFetchFailed = false;
    let detectionModelsFetchFailed = false;

    async function fetchModels() {
        try {
            const resp = await fetch('/api/vlm-models');
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            // Backend returns [{name, device}, ...]; fall back to legacy string list
            const raw = data?.models || [];
            allModels = raw.map((m) => {
                if (m && typeof m === 'object' && typeof m.name === 'string') {
                    return { name: m.name, device: m.device || 'cpu' };
                }
                if (typeof m === 'string') {
                    return { name: m, device: 'cpu' };
                }
                return null;
            }).filter(Boolean);
            modelsFetchFailed = false;
            return allModels;
        } catch (_err) {
            allModels = [];
            modelsFetchFailed = true;
            return allModels;
        }
    }

    function getAllModels() {
        return allModels;
    }

    function didModelsFetchFail() {
        return modelsFetchFailed;
    }

    async function fetchDetectionModels() {
        try {
            const resp = await fetch('/api/detection-models');
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            detectionModelsFetchFailed = false;
            return Array.isArray(data?.models) ? data.models : [];
        } catch (_err) {
            detectionModelsFetchFailed = true;
            return [];
        }
    }

    function didDetectionModelsFetchFail() {
        return detectionModelsFetchFailed;
    }

    async function fetchCameras() {
        try {
            const resp = await fetch('/api/cameras', { method: 'GET' });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            return Array.isArray(data?.cameras) ? data.cameras : [];
        } catch (_err) {
            return [];
        }
    }

    async function fetchSystemCapabilities(metricsServicePort) {
        const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
        const host = window.location.hostname;
        const capabilitiesUrl = `${protocol}//${host}:${metricsServicePort}/api/v1/capabilities?profile=minimal`;

        try {
            const resp = await fetch(capabilitiesUrl, { method: 'GET' });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            const devices = Array.isArray(data?.devices) ? data.devices : null;
            if (!devices) throw new Error('Invalid capability response');

            return {
                ...data,
                has_gpu: devices.some(
                    (device) => device?.present === true
                        && ['igpu', 'dgpu'].includes(device?.category)
                ),
                has_npu: devices.some(
                    (device) => device?.present === true && device?.category === 'npu'
                ),
            };
        } catch (_err) {
            try {
                const resp = await fetch('/api/capabilities', { method: 'GET' });
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                const data = await resp.json();
                return {
                    has_gpu: data?.has_gpu === true,
                    has_npu: data?.has_npu === true,
                    devices: [],
                };
            } catch (_fallbackErr) {
                return {
                    has_gpu: null,
                    has_npu: null,
                    devices: [],
                };
            }
        }
    }

    async function fetchRuns() {
        const resp = await fetch('/api/generate_captions_alerts');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    }

    async function startRun(requestBody) {
        const resp = await fetch('/api/generate_captions_alerts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        const data = await resp.json().catch(async () => ({ message: await resp.text() }));

        if (!resp.ok) {
            let errorMessage = resp.statusText;

            // Handle FastAPI validation errors (status 422)
            if (resp.status === 422 && data?.detail && Array.isArray(data.detail)) {
                // Extract validation error messages
                const validationErrors = data.detail.map(error => {
                    const field = error.loc ? error.loc[error.loc.length - 1] : 'unknown field';
                    return `${field}: ${error.msg}`;
                }).join(', ');
                errorMessage = validationErrors;
            }
            // Handle other error formats
            else if (data?.message) {
                errorMessage = data.message;
            }
            else if (data?.detail?.message) {
                errorMessage = data.detail.message;
            }
            else if (typeof data?.detail === 'string') {
                errorMessage = data.detail;
            }

            throw new Error(errorMessage);
        }

        return data;
    }

    async function stopRun(runId) {
        const resp = await fetch(`/api/generate_captions_alerts/${runId}`, { method: 'DELETE' });
        if (!resp.ok) {
            if (resp.status === 404 || resp.status === 502) {
                return { notFound: true };
            }
            const data = await resp.json().catch(async () => ({ message: await resp.text() }));
            throw new Error(data?.message || data?.detail?.message || resp.statusText);
        }
        return await resp.json();
    }

    async function checkStreamReady(runId) {
        try {
            const resp = await fetch(`/api/generate_captions_alerts/${runId}/stream-ready`);
            if (!resp.ok) return { ready: false, error: false, state: null };
            const data = await resp.json();
            return {
                ready: data?.ready === true,
                error: data?.error === true,
                state: data?.state ?? null,
            };
        } catch (_err) {
            return { ready: false, error: false, state: null };
        }
    }

    return {
        fetchModels,
        getAllModels,
        didModelsFetchFail,
        didDetectionModelsFetchFail,
        fetchDetectionModels,
        fetchCameras,
        fetchSystemCapabilities,
        fetchRuns,
        startRun,
        stopRun,
        checkStreamReady,
        DEFAULT_MODEL
    };
})();
