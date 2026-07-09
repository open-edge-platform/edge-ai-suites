/**
 * Settings persistence utilities
 */
const SettingsManager = (function () {
    const SETTINGS_KEY = 'lvc-settings';

    function saveSettings(els) {
        try {
            const settings = {
                rtspUrl: els.rtspInput?.value || '',
                streamSourceType: els.streamSourceTypeSelect?.value || 'camera',
                cameraDevicePath: els.cameraDeviceSelect?.value || '',
                prompt: els.promptInput?.value || '',
                modelName: els.modelNameSelect?.value || '',
                pipelineType: els.pipelineTypeSelect?.value || 'non-detection',
                vlmDevice: els.vlmDeviceSelect?.value || 'cpu',
                detectionDevice: els.detectionDeviceSelect?.value || 'cpu',
                includeRoiBoundingBox: Boolean(els.includeRoiBoundingBoxCheckbox?.checked),
                maxTokens: els.maxTokensInput?.value || '70',
                captionHistory: els.captionHistoryInput?.value || '3',
                runName: els.runNameInput?.value || '',
                frameRate: els.frameRateInput?.value || '',
                chunkSize: els.chunkSizeInput?.value || '',
                frameQuality: els.frameQualitySelect?.value || '',
                customWidth: els.customWidthInput?.value || '',
                customHeight: els.customHeightInput?.value || '',
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
        const savedCaptionHistory = settings.captionHistory;
        if (savedCaptionHistory !== undefined && savedCaptionHistory !== '' && els.captionHistoryInput) {
            els.captionHistoryInput.value = savedCaptionHistory;
        }
        if (settings.runName && els.runNameInput) {
            els.runNameInput.value = settings.runName;
        }
        if (settings.frameRate !== undefined && settings.frameRate !== '' && els.frameRateInput) {
            els.frameRateInput.value = settings.frameRate;
        }
        if (settings.chunkSize !== undefined && settings.chunkSize !== '' && els.chunkSizeInput) {
            els.chunkSizeInput.value = settings.chunkSize;
        }
        if (settings.frameQuality !== undefined && settings.frameQuality !== '' && els.frameQualitySelect) {
            els.frameQualitySelect.value = settings.frameQuality;
        }
        if (settings.customWidth !== undefined && settings.customWidth !== '' && els.customWidthInput) {
            els.customWidthInput.value = settings.customWidth;
        }
        if (settings.customHeight !== undefined && settings.customHeight !== '' && els.customHeightInput) {
            els.customHeightInput.value = settings.customHeight;
        }
        if (settings.streamSourceType && els.streamSourceTypeSelect) {
            els.streamSourceTypeSelect.value = settings.streamSourceType;
        }
        if (settings.vlmDevice && els.vlmDeviceSelect) {
            const options = Array.from(els.vlmDeviceSelect.options).map(o => o.value);
            if (options.includes(settings.vlmDevice)) {
                els.vlmDeviceSelect.value = settings.vlmDevice;
            }
        }
        if (settings.detectionDevice && els.detectionDeviceSelect) {
            const options = Array.from(els.detectionDeviceSelect.options).map(o => o.value);
            if (options.includes(settings.detectionDevice)) {
                els.detectionDeviceSelect.value = settings.detectionDevice;
            }
        }
        if (els.includeRoiBoundingBoxCheckbox) {
            els.includeRoiBoundingBoxCheckbox.checked = settings.includeRoiBoundingBox === true;
        }
        if (settings.pipelineType && els.pipelineTypeSelect) {
            const options = Array.from(els.pipelineTypeSelect.options).map(o => o.value);
            if (options.includes(settings.pipelineType)) {
                els.pipelineTypeSelect.value = settings.pipelineType;
            }
        }
        // Model will be restored after options are loaded
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
        if (settings.cameraDevicePath && els.cameraDeviceSelect) {
            const options = Array.from(els.cameraDeviceSelect.options).map(o => o.value);
            if (options.includes(settings.cameraDevicePath)) {
                els.cameraDeviceSelect.value = settings.cameraDevicePath;
            }
        }
    }

    function setupSettingsPersistence(els) {
        // Save settings on input changes
        const inputs = [els.rtspInput, els.streamSourceTypeSelect, els.cameraDeviceSelect,
        els.promptInput, els.maxTokensInput, els.modelNameSelect, els.pipelineTypeSelect, els.vlmDeviceSelect, els.detectionDeviceSelect, els.runNameInput,
        els.frameRateInput, els.chunkSizeInput, els.frameQualitySelect, els.customWidthInput, els.customHeightInput,
        els.includeRoiBoundingBoxCheckbox,
        els.captionHistoryInput];
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
