/**
 * Settings persistence utilities
 */
const SettingsManager = (function() {
    const SETTINGS_KEY = 'lvc-settings';

    function saveSettings(els) {
        try {
            const settings = {
                rtspUrl: els.rtspInput?.value || '',
                prompt: els.promptInput?.value || '',
                modelName: els.modelNameSelect?.value || '',
                pipelineName: els.pipelineSelect?.value || '',
                maxTokens: els.maxTokensInput?.value || '70',
                runName: els.runNameInput?.value || '',
            };
            localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
        } catch (_err) {
            // localStorage not available
        }
    }

    function loadSettings() {
        try {
            const saved = localStorage.getItem(SETTINGS_KEY);
            if (!saved) return null;
            return JSON.parse(saved);
        } catch (_err) {
            return null;
        }
    }

    function restoreSettings(els, cfg) {
        const settings = loadSettings();
        if (!settings) return;
        
        // Only restore RTSP URL if it's different from the current runtime config default
        // This allows runtime config to take precedence for fresh sessions
        if (settings.rtspUrl && els.rtspInput) {
            const cfgDefault = cfg?.defaultRtspUrl || '';
            // Only restore if user had a custom value (different from config default)
            if (settings.rtspUrl !== cfgDefault) {
                els.rtspInput.value = settings.rtspUrl;
            }
        }
        // Only restore prompt if it's different from the current runtime config default
        if (settings.prompt && els.promptInput) {
            const cfgDefault = cfg?.defaultPrompt || 'Describe what you see in one sentence.';
            // Only restore if user had a custom value (different from config default)
            if (settings.prompt !== cfgDefault && settings.prompt !== 'Describe what you see in one sentence.') {
                els.promptInput.value = settings.prompt;
            }
        }
        if (settings.maxTokens && els.maxTokensInput) {
            els.maxTokensInput.value = settings.maxTokens;
        }
        if (settings.runName && els.runNameInput) {
            els.runNameInput.value = settings.runName;
        }
        // Model and pipeline will be restored after options are loaded
    }

    function restoreSelectValues(els) {
        const settings = loadSettings();
        if (!settings) return;
        
        if (settings.modelName && els.modelNameSelect) {
            const options = Array.from(els.modelNameSelect.options).map(o => o.value);
            if (options.includes(settings.modelName)) {
                els.modelNameSelect.value = settings.modelName;
            }
        }
        if (settings.pipelineName && els.pipelineSelect) {
            const options = Array.from(els.pipelineSelect.options).map(o => o.value);
            if (options.includes(settings.pipelineName)) {
                els.pipelineSelect.value = settings.pipelineName;
            }
        }
    }

    function setupSettingsPersistence(els) {
        // Save settings on input changes
        const inputs = [els.rtspInput, els.promptInput, els.maxTokensInput, els.modelNameSelect, els.pipelineSelect, els.runNameInput];
        inputs.forEach(el => {
            if (el) {
                el.addEventListener('change', () => saveSettings(els));
                el.addEventListener('input', () => saveSettings(els));
            }
        });
    }

    return {
        saveSettings,
        loadSettings,
        restoreSettings,
        restoreSelectValues,
        setupSettingsPersistence
    };
})();
