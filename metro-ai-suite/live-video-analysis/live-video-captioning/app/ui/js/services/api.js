/**
 * API service for backend communication
 */
const ApiService = (function () {
    const DEFAULT_MODEL = 'InternVL2-1B';
    const DEFAULT_DETECTION_MODEL = 'yolov8s';
    const DEFAULT_PIPELINE = 'GenAI_Pipeline_on_CPU';
    let pipelineCache = [];

    async function fetchModels() {
        try {
            const resp = await fetch('/api/vlm-models');
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            return data?.models || [DEFAULT_MODEL];
        } catch (_err) {
            return [DEFAULT_MODEL];
        }
    }

    async function fetchDetectionModels() {
        try {
            const resp = await fetch('/api/detection-models');
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            return data?.models || [DEFAULT_DETECTION_MODEL];
        } catch (_err) {
            return [DEFAULT_DETECTION_MODEL];
        }
    }

    async function fetchPipelines() {
        try {
            const resp = await fetch('/api/pipelines', { method: 'GET' });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

            const data = await resp.json();
            const list = Array.isArray(data?.pipelines) ? data.pipelines : [];

            // Accept either correct shape objects or fallback strings (future-proof)
            const normalized = list
                .map((it) => {
                    if (it && typeof it === 'object' && typeof it.pipeline_name === 'string') {
                        const t = it.pipeline_type;
                        const type = (t === 'detection' || t === 'non-detection') ? t : 'non-detection';
                        return { pipeline_name: it.pipeline_name, pipeline_type: type };
                    }
                    if (typeof it === 'string') {
                        return { pipeline_name: it, pipeline_type: 'non-detection' };
                    }
                    return null;
                })
                .filter(Boolean);

            // De-duplicate by name (last wins), then sort (non-detection first, then name)
            const map = new Map();
            for (const p of normalized) map.set(p.pipeline_name, p);
            const pipelines = Array.from(map.values()).sort((a, b) => {
                if (a.pipeline_type !== b.pipeline_type) {
                    return a.pipeline_type === 'non-detection' ? -1 : 1;
                }
                return a.pipeline_name.localeCompare(b.pipeline_name);
            });

            pipelineCache = pipelines.length
                ? pipelines
                : [{ pipeline_name: DEFAULT_PIPELINE, pipeline_type: 'non-detection' }];

            return pipelineCache;
        } catch (_err) {
            pipelineCache = [{ pipeline_name: DEFAULT_PIPELINE, pipeline_type: 'non-detection' }];
            return pipelineCache;
        }
    }

    async function fetchRuns() {
        const resp = await fetch('/api/runs');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    }

    async function startRun(requestBody) {
        const resp = await fetch('/api/runs', {
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
        const resp = await fetch(`/api/runs/${runId}`, { method: 'DELETE' });
        if (!resp.ok) {
            if (resp.status === 404 || resp.status === 502) {
                return { notFound: true };
            }
            const data = await resp.json().catch(async () => ({ message: await resp.text() }));
            throw new Error(data?.message || data?.detail?.message || resp.statusText);
        }
        return await resp.json();
    }

    return {
        fetchModels,
        fetchDetectionModels,
        fetchPipelines,
        fetchRuns,
        startRun,
        stopRun,
        DEFAULT_MODEL,
        DEFAULT_PIPELINE
    };
})();
