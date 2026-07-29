/**
 * Model info (fetch once and cache)
 */
const ModelInfo = (function () {
    let llmModelName = null;
    let llmModelLoaded = false;

    /*
     * Loads model info from /api/model once and caches it
     */
    async function loadModelInfoOnce() {
        if (llmModelLoaded) return llmModelName;
        try {
            const res = await fetch('/api/model', { headers: { 'Accept': 'application/json' } });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            llmModelName = data?.llm_model || 'Unknown model';
        } catch (e) {
            console.warn('Failed to load /api/model:', e);
            llmModelName = 'Unknown model';
        } finally {
            llmModelLoaded = true;
        }
        return llmModelName;
    }

    return { loadModelInfoOnce };
})();