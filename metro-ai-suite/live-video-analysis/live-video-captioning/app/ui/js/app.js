/**
 * Main application entry point
 */
(function () {
    const cfg = window.RUNTIME_CONFIG || {};
    const els = {
        statusDot: document.getElementById('videoStatus'),
        hintEl: document.getElementById('hint'),
        form: document.getElementById('pipelineForm'),
        promptInput: document.getElementById('promptInput'),
        modelNameSelect: document.getElementById('modelNameSelect'),
        pipelineTypeSelect: document.getElementById('pipelineTypeSelect'),
        vlmDeviceSelect: document.getElementById('vlmDeviceSelect'),
        maxTokensInput: document.getElementById('maxTokensInput'),
        captionHistoryInput: document.getElementById('captionHistoryInput'),
        streamSourceTypeSelect: document.getElementById('streamSourceTypeSelect'),
        cameraDeviceRow: document.getElementById('cameraDeviceRow'),
        cameraDeviceSelect: document.getElementById('cameraDeviceSelect'),
        cameraDeviceWarning: document.getElementById('cameraDeviceWarning'),
        rtspInputRow: document.getElementById('rtspInputRow'),
        rtspInput: document.getElementById('rtspInput'),
        runNameInput: document.getElementById('runNameInput'),
        startBtn: document.getElementById('startBtn'),
        pipelineInfo: document.getElementById('pipelineInfo'),
        runsContainer: document.getElementById('runsContainer'),
        themeToggle: document.getElementById('themeToggle'),
        chatToggle: document.getElementById('chatToggle'),
        detectionModelField: document.getElementById('detectionModelField'),
        detectionThresholdField: document.getElementById('detectionThresholdField'),
        detectionDeviceSelect: document.getElementById('detectionDeviceSelect'),
        detectionModelNameSelect: document.getElementById('detectionModelNameSelect'),
        detectionThresholdInput: document.getElementById('detectionThresholdInput'),
        includeRoiBoundingBoxCheckbox: document.getElementById('includeRoiBoundingBoxCheckbox'),
        frameRateInput: document.getElementById('frameRateInput'),
        chunkSizeInput: document.getElementById('chunkSizeInput'),
        frameQualitySelect: document.getElementById('frameQualitySelect'),
        customWidthInput: document.getElementById('customWidthInput'),
        customHeightInput: document.getElementById('customHeightInput'),
        customDimensionsRow: document.getElementById('customDimensionsRow'),
        alertRulesSection: document.getElementById('alertRulesSection'),
        alertRulesList: document.getElementById('alertRulesList'),
        addAlertRuleBtn: document.getElementById('addAlertRuleBtn'),
        pipelineServerError: document.getElementById('pipelineServerError'),
        modelCompatibilityWarningIcon: document.getElementById('modelCompatibilityWarningIcon'),
        detectionModelCompatibilityWarningIcon: document.getElementById('detectionModelCompatibilityWarningIcon'),
    };

    const state = {
        selectedRunId: null,
        runs: new Map(),
        isStarting: false,
        hasSavedVlmDevicePreference: false,
        hasGpuDevice: null,
        hasNpuDevice: null,
    };
    const CHAT_TAB_NAME = 'Live Caption RAG Dashboard';

    (function initChatToggleVisibility() {
        if (cfg.enableEmbedding !== true) {
            setSectionVisible(els.chatToggle, false);
        } else if (els.chatToggle) {
            els.chatToggle.addEventListener('click', () => {
                const chatUrl = `http://${window.location.hostname}:${cfg.liveVideoRagHostPort}`;
                const chatWindow = window.open(chatUrl, CHAT_TAB_NAME);
                if (chatWindow) {
                    chatWindow.focus();
                }
            });
        }
    })();

    function setSectionVisible(el, show) {
        if (!el) return;
        el.style.display = show ? '' : 'none';
    }

    function syncPipelineTypeOptions() {
        const select = els.pipelineTypeSelect;
        if (!select) return;

        const detectionEnabled = cfg.enableDetectionPipeline === true;
        const detectionOption = select.querySelector('option[value="detection"]');

        if (!detectionEnabled && detectionOption) {
            detectionOption.remove();
        }

        if (!select.querySelector('option[value="detection"]') && detectionEnabled) {
            const option = document.createElement('option');
            option.value = 'detection';
            option.textContent = 'Video Captioning Pipeline with Detection';
            select.appendChild(option);
        }

        if (select.value !== 'detection' && select.value !== 'non-detection') {
            select.value = 'non-detection';
        }
    }

    function normalizeCaptionHistory(rawValue, fallback = 3) {
        const parsed = Number.parseInt(rawValue, 10);
        if (!Number.isFinite(parsed)) return fallback;
        return Math.max(0, parsed);
    }

    function getDefaultCaptionHistory() {
        return normalizeCaptionHistory(cfg.captionHistory, 3);
    }

    function getPreferredCaptionHistoryOnLoad() {
        const settings = SettingsManager.loadSettings();
        if (settings) {
            const savedCaptionHistory = settings.captionHistory;
            if (savedCaptionHistory !== undefined && savedCaptionHistory !== '') {
                return normalizeCaptionHistory(savedCaptionHistory, getDefaultCaptionHistory());
            }
        }
        return getDefaultCaptionHistory();
    }

    function applyCaptionHistorySetting() {
        if (!els.captionHistoryInput) return;
        const resolved = normalizeCaptionHistory(els.captionHistoryInput.value, getDefaultCaptionHistory());
        if (els.captionHistoryInput.value !== String(resolved)) {
            els.captionHistoryInput.value = String(resolved);
        }
        MetadataStreamService.setCaptionHistoryLimit(resolved);
    }

    function handleCaptionHistoryInput() {
        if (!els.captionHistoryInput) return;
        const raw = els.captionHistoryInput.value;
        // Allow transient empty value while user is editing with backspace/delete.
        if (raw === '') return;

        const parsed = Number.parseInt(raw, 10);
        if (!Number.isFinite(parsed)) return;

        MetadataStreamService.setCaptionHistoryLimit(Math.max(0, parsed));
    }

    const ALERT_RULE_DEFAULTS = [];
    const ALERT_RULES_STORAGE_KEY = 'lvc_alert_rules';
    const MAX_ALERT_RULES = 3;

    function createAlertRuleRow(substring, color) {
        const row = document.createElement('div');
        row.className = 'alert-rule-row';

        // Hidden native color input
        const colorPicker = document.createElement('input');
        colorPicker.type = 'color';
        colorPicker.className = 'alert-rule-color-picker';
        colorPicker.value = color || '#ff4444';
        colorPicker.title = 'Pick highlight color';
        colorPicker.setAttribute('aria-label', 'Highlight color');

        // Visible color swatch that triggers the picker
        const swatch = document.createElement('button');
        swatch.type = 'button';
        swatch.className = 'alert-rule-swatch';
        swatch.title = 'Click to change color';
        swatch.style.background = color || '#ff4444';
        swatch.appendChild(colorPicker);
        colorPicker.addEventListener('input', () => {
            swatch.style.background = colorPicker.value;
            saveAlertRulesToStorage();
        });

        const substringInput = document.createElement('input');
        substringInput.type = 'text';
        substringInput.className = 'alert-rule-substring';
        substringInput.placeholder = 'Keyword to match…';
        substringInput.value = substring || '';
        substringInput.addEventListener('input', () => { saveAlertRulesToStorage(); });

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'alert-rule-remove';
        removeBtn.title = 'Remove rule';
        removeBtn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
        removeBtn.addEventListener('click', () => {
            row.remove();
            refreshAlertRulesUI();
            saveAlertRulesToStorage();
        });

        row.appendChild(swatch);
        row.appendChild(substringInput);
        row.appendChild(removeBtn);
        return row;
    }

    function refreshAlertRulesUI() {
        if (!els.alertRulesList || !els.addAlertRuleBtn) return;
        const rows = els.alertRulesList.querySelectorAll('.alert-rule-row');
        const count = rows.length;
        // Show/hide empty state hint
        let emptyHint = els.alertRulesList.querySelector('.alert-rules-empty');
        if (count === 0) {
            if (!emptyHint) {
                emptyHint = document.createElement('p');
                emptyHint.className = 'alert-rules-empty';
                els.alertRulesList.appendChild(emptyHint);
            }
        } else if (emptyHint) {
            emptyHint.remove();
        }
        // Show/hide Add Rule button
        els.addAlertRuleBtn.style.display = count >= MAX_ALERT_RULES ? 'none' : '';
    }

    function loadAlertRulesFromStorage() {
        try {
            const raw = localStorage.getItem(ALERT_RULES_STORAGE_KEY);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) return parsed;
            }
        } catch (_e) { /* ignore corrupt data */ }
        return null;
    }

    function saveAlertRulesToStorage() {
        const rules = readAlertRules();
        try {
            localStorage.setItem(ALERT_RULES_STORAGE_KEY, JSON.stringify(rules));
        } catch (_e) { /* storage full or unavailable */ }
    }

    function initAlertRulesUI() {
        if (!els.alertRulesList || !els.addAlertRuleBtn) return;
        els.alertRulesList.innerHTML = '';

        // Load from localStorage, fall back to defaults (empty)
        const saved = loadAlertRulesFromStorage();
        const initial = saved !== null ? saved : ALERT_RULE_DEFAULTS;
        for (const def of initial) {
            els.alertRulesList.appendChild(createAlertRuleRow(def.substring, def.color));
        }
        refreshAlertRulesUI();

        els.addAlertRuleBtn.addEventListener('click', () => {
            const count = els.alertRulesList.querySelectorAll('.alert-rule-row').length;
            if (count >= MAX_ALERT_RULES) return;
            const randomColor = '#' + Math.floor(Math.random() * 0xFFFFFF).toString(16).padStart(6, '0');
            els.alertRulesList.appendChild(createAlertRuleRow('', randomColor));
            refreshAlertRulesUI();
            saveAlertRulesToStorage();
        });
    }

    function readAlertRules() {
        if (!els.alertRulesList) return [];
        const rows = els.alertRulesList.querySelectorAll('.alert-rule-row');
        const rules = [];
        for (const row of rows) {
            const substring = (row.querySelector('.alert-rule-substring')?.value || '').trim();
            const color = row.querySelector('.alert-rule-color-picker')?.value || '#ff4444';
            if (substring) rules.push({ substring, color });
        }
        return rules;
    }

    function showDetectionFields(show) {
        const detectionSection = document.getElementById('detectionSection');
        const visibleByFlag = cfg.enableDetectionPipeline === true; // respects global flag
        const shouldShow = visibleByFlag && !!show;

        setSectionVisible(detectionSection, shouldShow);

        // Disable inputs when hidden to avoid accidental submission
        const toDisableSelectors = [
            '#detectionDeviceSelect',
            '#detectionModelNameSelect',
            '#detectionThresholdInput',
            '#includeRoiBoundingBoxCheckbox'
        ];
        for (const sel of toDisableSelectors) {
            const el = document.querySelector(sel);
            if (el) el.disabled = !shouldShow;
        }

        if (shouldShow) {
            loadDetectionModels();
        }
    }

    function toggleDetectionFieldsByText() {
        showDetectionFields(getSelectedPipelineType() === 'detection');
        updateDetectionDeviceOptions();
        updateStartButtonAvailability();
    }

    function updateDetectionDeviceOptions() {
        const deviceSelect = els.detectionDeviceSelect;
        if (!deviceSelect) return;

        const selectedVlmDevice = getSelectedVlmDevice();
        const selectedDetectionDevice = (deviceSelect.value || '').toLowerCase();
        const allowCpuOnly = selectedVlmDevice === 'cpu';
        const hasGpu = state.hasGpuDevice === true;
        const hasNpu = state.hasNpuDevice === true;

        for (const opt of Array.from(deviceSelect.options)) {
            const value = (opt.value || '').toLowerCase();
            let allowed = false;
            if (allowCpuOnly) {
                allowed = value === 'cpu';
            } else if (value === 'gpu') {
                allowed = hasGpu;
            } else if (value === 'npu') {
                allowed = hasNpu;
            }

            // Keep the UI usable if capabilities are unknown or no accelerator exists.
            if (!allowCpuOnly && !hasGpu && !hasNpu) {
                allowed = value === 'cpu';
            }

            opt.hidden = !allowed;
            opt.disabled = !allowed;
        }

        const selectedStillAllowed = Array.from(deviceSelect.options).some((opt) => {
            return !opt.hidden && opt.value.toLowerCase() === selectedDetectionDevice;
        });

        if (!selectedStillAllowed) {
            const firstVisible = Array.from(deviceSelect.options).find((o) => !o.hidden);
            if (firstVisible) deviceSelect.value = firstVisible.value;
        }
    }

    function getSelectedPipelineType() {
        const selected = (els.pipelineTypeSelect?.value || '').trim().toLowerCase();
        if (cfg.enableDetectionPipeline === true && selected === 'detection') {
            return 'detection';
        }
        return 'non-detection';
    }

    function resolveSignalingBase(url) {
        if (!url) return '';
        let base = url.replace(/\/$/, '');
        try {
            const parsed = new URL(base, window.location.origin);
            const localHosts = ['localhost', '127.0.0.1', '0.0.0.0'];
            if (localHosts.includes(parsed.hostname)) parsed.hostname = window.location.hostname;
            base = `${parsed.protocol}//${parsed.hostname}${parsed.port ? ':' + parsed.port : ''}`;
        } catch (_err) {
            base = base.replace('localhost', window.location.hostname);
        }
        return base;
    }

    function updatePipelineInfo(text) {
        els.pipelineInfo.textContent = text;
    }

    function hasCameraSourceOption() {
        return !!els.streamSourceTypeSelect?.querySelector('option[value="camera"]');
    }

    function getSelectedSourceType() {
        const selected = els.streamSourceTypeSelect?.value;
        if (selected === 'rtsp') return 'rtsp';
        if (selected === 'camera' && hasCameraSourceOption()) return 'camera';
        return hasCameraSourceOption() ? 'camera' : 'rtsp';
    }

    function setCameraSourceAvailability(hasUsableCameras) {
        const select = els.streamSourceTypeSelect;
        if (!select) return;

        let cameraOption = select.querySelector('option[value="camera"]');
        if (hasUsableCameras) {
            if (!cameraOption) {
                cameraOption = document.createElement('option');
                cameraOption.value = 'camera';
                cameraOption.textContent = 'Host Camera';
                select.insertBefore(cameraOption, select.firstChild);
            }
            return;
        }

        if (cameraOption) {
            cameraOption.remove();
        }

        // Ensure dropdown stays on a valid mode when camera source is unavailable.
        if (select.value !== 'rtsp') {
            select.value = 'rtsp';
            SettingsManager.saveSettings(els);
        }
    }

    function setModelOptions(models, previousSelection) {
        const select = els.modelNameSelect;
        if (!select) return;
        select.innerHTML = '';

        // Accept both ModelInfo objects {name, device} and legacy plain strings
        const list = Array.isArray(models)
            ? models.map((m) => (typeof m === 'string' ? { name: m, device: 'cpu' } : m))
            : [];

        // Hide warning by default; will be shown below if needed
        if (els.modelCompatibilityWarningIcon) {
            els.modelCompatibilityWarningIcon.style.display = 'none';
            els.modelCompatibilityWarningIcon.setAttribute('title', '');
            els.modelCompatibilityWarningIcon.setAttribute('data-tooltip', '');
            els.modelCompatibilityWarningIcon.setAttribute('aria-label', 'Model compatibility warning');
        }

        if (!list.length) {
            // Show disabled placeholder so the select is not empty
            const placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = 'No compatible models (required)';
            placeholder.disabled = true;
            placeholder.selected = true;
            select.appendChild(placeholder);
            select.disabled = true;

            // Determine the right warning message
            let msg;
            const selectedVlmDevice = getSelectedVlmDevice();
            if (ApiService.didModelsFetchFail()) {
                msg = '⚠ Could not load model list. Is the backend running?';
            } else if (selectedVlmDevice && selectedVlmDevice !== 'any') {
                msg = `⚠ No ${selectedVlmDevice.toUpperCase()} models found. ` +
                    `Download a ${selectedVlmDevice}-optimised model first (see model-preparation guide).`;
            } else {
                msg = '⚠ No models were found in the models directory. Download one model first before starting.';
            }

            if (els.modelCompatibilityWarningIcon) {
                els.modelCompatibilityWarningIcon.style.display = 'inline-flex';
                els.modelCompatibilityWarningIcon.setAttribute('data-tooltip', msg);
                els.modelCompatibilityWarningIcon.setAttribute('aria-label', msg);
            }

            // Disable start button — no model to run with
            if (els.startBtn) els.startBtn.disabled = true;
            return;
        }

        select.disabled = false;

        // Re-enable start button now that we have models
        if (els.startBtn) els.startBtn.disabled = false;

        for (const { name } of list) {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            select.appendChild(opt);
        }

        // Restore previous selection if still compatible, otherwise pick first
        const names = list.map((m) => m.name);
        const restore = previousSelection && names.includes(previousSelection)
            ? previousSelection
            : names[0];
        select.value = restore;
    }

    function getSelectedVlmDevice() {
        const selected = (els.vlmDeviceSelect?.value || '').trim().toLowerCase();
        return ['cpu', 'gpu', 'npu'].includes(selected) ? selected : 'cpu';
    }

    function getSelectedDetectionDevice() {
        const selected = (els.detectionDeviceSelect?.value || '').trim().toLowerCase();
        return ['cpu', 'gpu', 'npu'].includes(selected) ? selected : 'cpu';
    }

    function getCapabilityBasedDefaultDevice() {
        return state.hasGpuDevice === true ? 'gpu' : 'cpu';
    }

    function setVlmDeviceOptionsByCapabilities() {
        const select = els.vlmDeviceSelect;
        if (!select) return;

        const previous = (select.value || '').trim().toLowerCase();
        const options = [];

        options.push({ value: 'cpu', label: 'CPU' });
        if (state.hasGpuDevice === true) {
            options.push({ value: 'gpu', label: 'GPU' });
        }
        if (state.hasNpuDevice === true) {
            options.push({ value: 'npu', label: 'NPU' });
        }

        // Fallback for partially reported capabilities to keep the UI usable.
        if (options.length === 0) {
            options.push({ value: 'cpu', label: 'CPU' });
        }

        select.innerHTML = '';
        for (const option of options) {
            const opt = document.createElement('option');
            opt.value = option.value;
            opt.textContent = option.label;
            select.appendChild(opt);
        }

        const settings = SettingsManager.loadSettings();
        const saved = (settings?.vlmDevice || '').trim().toLowerCase();
        const availableValues = options.map((o) => o.value);
        const capabilityDefault = getCapabilityBasedDefaultDevice();
        const selected = state.hasSavedVlmDevicePreference && availableValues.includes(saved)
            ? saved
            : (availableValues.includes(capabilityDefault) ? capabilityDefault : [previous, saved].find((value) => availableValues.includes(value)) || options[0].value);
        select.value = selected;

        updateDetectionDeviceOptions();
        SettingsManager.saveSettings(els);
    }

    async function loadSystemCapabilities() {
        const capabilities = await ApiService.fetchSystemCapabilities();
        if (capabilities?.has_gpu === true || capabilities?.has_gpu === false) {
            state.hasGpuDevice = capabilities.has_gpu;
        } else {
            state.hasGpuDevice = null;
        }
        if (capabilities?.has_npu === true || capabilities?.has_npu === false) {
            state.hasNpuDevice = capabilities.has_npu;
        } else {
            state.hasNpuDevice = null;
        }

        setVlmDeviceOptionsByCapabilities();
        refreshModelsBySelectedVlmDevice();
    }

    /**
     * Filter the full model list to those compatible with the selected VLM device.
     * Strict one-to-one matching: cpu↔cpu, gpu↔gpu, npu↔npu.
     */
    function getCompatibleModels(vlmDevice) {
        const all = ApiService.getAllModels();
        if (!vlmDevice) return all;
        return all.filter((m) => m.device === vlmDevice);
    }

    /** Re-populate the model dropdown based on the currently selected VLM device. */
    function refreshModelsBySelectedVlmDevice() {
        const selectedVlmDevice = getSelectedVlmDevice();
        const previousModel = els.modelNameSelect?.value || null;
        const compatible = getCompatibleModels(selectedVlmDevice);
        setModelOptions(compatible, previousModel);
    }

    function setDetectionModelOptions(models, warningMessage = '') {
        const select = els.detectionModelNameSelect;
        if (!select) return;
        select.innerHTML = '';

        if (els.detectionModelCompatibilityWarningIcon) {
            els.detectionModelCompatibilityWarningIcon.style.display = 'none';
            els.detectionModelCompatibilityWarningIcon.setAttribute('title', '');
            els.detectionModelCompatibilityWarningIcon.setAttribute('data-tooltip', '');
            els.detectionModelCompatibilityWarningIcon.setAttribute('aria-label', 'Detection model compatibility warning');
        }

        const hasModels = Array.isArray(models) && models.length > 0;
        if (!hasModels) {
            const placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = 'No model found (required)';
            placeholder.disabled = true;
            placeholder.selected = true;
            select.appendChild(placeholder);
            select.disabled = true;
        } else {
            select.disabled = false;
            for (const name of models) {
                const opt = document.createElement('option');
                opt.value = name;
                opt.textContent = name;
                select.appendChild(opt);
            }
            select.value = models[0];
        }

        const message = warningMessage || (!hasModels
            ? '⚠ No detection models found. Download a YOLO detection model first.(see model-preparation guide)'
            : '');

        if (message && els.detectionModelCompatibilityWarningIcon) {
            els.detectionModelCompatibilityWarningIcon.style.display = 'inline-flex';
            els.detectionModelCompatibilityWarningIcon.setAttribute('data-tooltip', message);
            els.detectionModelCompatibilityWarningIcon.setAttribute('aria-label', message);
        }

        updateStartButtonAvailability();
    }

    function setCameraOptions(cameras) {
        const select = els.cameraDeviceSelect;
        if (!select) return;

        select.innerHTML = '';

        if (!Array.isArray(cameras) || cameras.length === 0) {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = 'No usable camera devices found';
            select.appendChild(opt);
            select.disabled = true;
            return;
        }

        select.disabled = false;
        for (const camera of cameras) {
            if (!camera || typeof camera.device_path !== 'string') continue;
            const opt = document.createElement('option');
            opt.value = camera.device_path;
            const deviceName = (typeof camera.device_name === 'string' && camera.device_name.trim())
                ? camera.device_name.trim()
                : camera.device_path;
            opt.textContent = `${deviceName} (${camera.device_path})`;
            select.appendChild(opt);
        }
    }

    function updateCameraWarningVisibility() {
        if (!els.cameraDeviceWarning) return;
        const isCameraMode = getSelectedSourceType() === 'camera';
        const noUsableCamera = !els.cameraDeviceSelect
            || els.cameraDeviceSelect.disabled
            || !els.cameraDeviceSelect.value;
        els.cameraDeviceWarning.style.display = (isCameraMode && noUsableCamera) ? '' : 'none';
    }

    function updateStartButtonAvailability() {
        if (!els.startBtn) return;
        if (state.isStarting) {
            els.startBtn.disabled = true;
            return;
        }

        const noVlmModel = !els.modelNameSelect
            || els.modelNameSelect.disabled
            || !(els.modelNameSelect.value || '').trim();

        const isCameraMode = getSelectedSourceType() === 'camera';
        const noUsableCamera = !els.cameraDeviceSelect
            || els.cameraDeviceSelect.disabled
            || !els.cameraDeviceSelect.value;
        const detectionRequired = getSelectedPipelineType() === 'detection';
        const noDetectionModel = detectionRequired && (
            !els.detectionModelNameSelect
            || els.detectionModelNameSelect.disabled
            || !(els.detectionModelNameSelect.value || '').trim()
        );

        els.startBtn.disabled = noVlmModel || (isCameraMode && noUsableCamera) || noDetectionModel;
    }

    async function loadCameraDevices() {
        try {
            const cameras = await ApiService.fetchCameras();
            const usableCameras = cameras.filter((camera) => camera?.has_usable_format === true);
            setCameraOptions(usableCameras);
            setCameraSourceAvailability(usableCameras.length > 0);
            SettingsManager.restoreSelectValues(els);
            updateStreamSourceInputs();
            updateCameraWarningVisibility();
            updateStartButtonAvailability();
        } catch (_err) {
            setCameraOptions([]);
            setCameraSourceAvailability(false);
            updateStreamSourceInputs();
            updateCameraWarningVisibility();
            updateStartButtonAvailability();
        }
    }

    function updateStreamSourceInputs() {
        const sourceType = getSelectedSourceType();
        const isCamera = sourceType === 'camera';

        if (els.cameraDeviceRow) {
            els.cameraDeviceRow.style.display = isCamera ? '' : 'none';
        }
        if (els.rtspInputRow) {
            els.rtspInputRow.style.display = isCamera ? 'none' : '';
        }

        if (els.cameraDeviceSelect) {
            els.cameraDeviceSelect.disabled = !isCamera || els.cameraDeviceSelect.options.length === 0;
        }
        if (els.rtspInput) {
            els.rtspInput.disabled = isCamera;
        }

        if (isCamera && els.cameraDeviceSelect?.options.length === 0) {
            loadCameraDevices();
        }

        updateDetectionDeviceOptions();

        updateCameraWarningVisibility();
        updateStartButtonAvailability();
    }

    async function loadModels() {
        try {
            await ApiService.fetchModels();
            // Initial model population is driven by selected VLM device.
            refreshModelsBySelectedVlmDevice();
            SettingsManager.restoreSelectValues(els);
            updatePipelineInfo('Models loaded');
        } catch (_err) {
            setModelOptions([]);
            SettingsManager.restoreSelectValues(els);
            updatePipelineInfo('Model list unavailable');
        }
    }

    async function loadDetectionModels() {
        try {
            const detectionModels = await ApiService.fetchDetectionModels();
            const fetchFailed = typeof ApiService.didDetectionModelsFetchFail === 'function'
                ? ApiService.didDetectionModelsFetchFail()
                : false;
            const warning = fetchFailed
                ? '⚠ Could not load detection model list. No detection model is available.'
                : '';

            setDetectionModelOptions(detectionModels, warning);
            SettingsManager.restoreSelectValues(els);
            updatePipelineInfo('Detection models loaded');
        } catch (_err) {
            setDetectionModelOptions([], '⚠ Could not load detection model list. No detection model is available.');
            SettingsManager.restoreSelectValues(els);
            updatePipelineInfo('Detection model list unavailable');
        }
    }

    function tearDownRun(runId, current, message) {
        console.log(`Tearing down run ${runId}`);
        // Cancel any in-flight stream-readiness polling for this run
        if (typeof current?.cancelVideoPolling === 'function') current.cancelVideoPolling();
        // Remove UI reference from multiplexed stream handler
        MetadataStreamService.unregisterRunUI(runId);
        if (current?.wrap) current.wrap.remove();
        state.runs.delete(runId);
        if (state.selectedRunId === runId) state.selectedRunId = null;
        if (message) updatePipelineInfo(message);
        // Show hint again when all runs are stopped
        if (state.runs.size === 0 && els.hintEl) {
            els.hintEl.style.display = 'block';
            els.hintEl.textContent = 'Start a pipeline to see video streams here';
        }
    }

    async function stopRun(runId, stopBtn) {
        const current = state.runs.get(runId);
        if (!current) return;

        updatePipelineInfo(`Stopping: ${runId}...`);
        try {
            const result = await ApiService.stopRun(runId);
            if (result.notFound) {
                tearDownRun(runId, current, 'Run missing on server, removing');
                return;
            }
            tearDownRun(runId, current, state.runs.size <= 1 ? 'Pipeline stopped' : `Stopped: ${runId}`);
        } catch (err) {
            const msg = (err?.message || '').toLowerCase();
            if (msg.includes('404') || msg.includes('not found') || msg.includes('502')) {
                tearDownRun(runId, current, 'Run missing on server, removing');
            } else {
                // Re-enable the stop button so user can retry
                if (stopBtn) {
                    stopBtn.disabled = false;
                    stopBtn.textContent = 'Stop';
                }
                updatePipelineInfo(`Stop failed: ${err.message}`);
                console.error('Stop run error:', err);
            }
        }
    }

    function loadRunVideo(run, ui) {
        const base = resolveSignalingBase(cfg.signalingUrl);
        if (base) {
            ui.video.src = `${base}/${run.peerId}`;
        }
        if (ui.videoOverlay) ui.videoOverlay.style.display = 'none';
    }

    function showStreamStartupError(runId, ui) {
        // Guard against double-application: the SSE status heartbeat may also
        // report this run as errored. The flag is shared with the metadata
        // stream service so whichever path fires first wins.
        if (ui._errorStateShown) return;
        ui._errorStateShown = true;
        RunCardComponent.setRunErrorState(ui, 'Stream failed to start, click Remove to clear');
        RunCardComponent.setVideoOverlayError(ui, 'Stream failed to start');
    }

    async function mediamtxHasPublisher(peerId) {
        // Confirm mediamtx has a publisher for the path before loading the
        // iframe. The backend's fps-based readiness can lead mediamtx's track
        // gathering by a moment, and loading too early briefly shows the raw
        // "stream not found, retrying" page. An invalid-SDP probe against the
        // WHEP endpoint settles it without creating a session: mediamtx
        // replies 404 while the path has no publisher and 400 once it does.
        // The Content-Type header is required — without it mediamtx rejects
        // the request before looking up the path.
        const base = resolveSignalingBase(cfg.signalingUrl);
        if (!base) return true; // nothing to probe; keep legacy behaviour
        try {
            const resp = await fetch(`${base}/${peerId}/whep`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/sdp' },
            });
            return resp.status !== 404;
        } catch (_err) {
            // Probe unreachable (proxy/CORS/network) – don't block the video
            // forever on a diagnostic request; fall back to loading the
            // iframe, whose built-in page retries by itself.
            return true;
        }
    }

    function waitForStreamThenLoad(run, ui) {
        // Two-stage readiness gate, each side answering the only question it
        // can answer authoritatively: the backend answers "is the pipeline
        // alive and producing?", mediamtx answers "can the browser watch it
        // yet?". Poll the backend until the DL Streamer pipeline is RUNNING
        // and frames are flowing, then load the iframe once mediamtx confirms
        // a publisher for the path. This avoids showing mediamtx's raw
        // "stream not found, retrying" page while the pipeline spins up. If
        // the pipeline leaves the RUNNING/QUEUED states (i.e. it failed to
        // start the stream) the card is switched to an error state instead of
        // loading the video.
        const POLL_INTERVAL_MS = 1000;
        const MAX_WAIT_MS = 45000;
        const started = Date.now();
        let cancelled = false;

        if (ui.videoOverlay) ui.videoOverlay.style.display = '';

        const poll = async () => {
            if (cancelled) return;
            // Stop polling if the run card was removed (e.g. user clicked Stop).
            if (!state.runs.has(run.runId)) return;

            const result = await ApiService.checkStreamReady(run.runId);
            if (cancelled || !state.runs.has(run.runId)) return;

            // Pipeline is no longer RUNNING/QUEUED – the stream will never come
            // up, so surface an error instead of waiting indefinitely.
            if (result.error) {
                showStreamStartupError(run.runId, ui);
                return;
            }

            if (result.ready && await mediamtxHasPublisher(run.peerId)) {
                if (cancelled || !state.runs.has(run.runId)) return;
                loadRunVideo(run, ui);
                return;
            }

            if (Date.now() - started >= MAX_WAIT_MS) {
                // Timed out. If the pipeline is still running, mediamtx is just
                // slow – load the iframe anyway. Otherwise show an error.
                if (result.state === 'running') {
                    loadRunVideo(run, ui);
                } else {
                    showStreamStartupError(run.runId, ui);
                }
                return;
            }
            setTimeout(poll, POLL_INTERVAL_MS);
        };

        poll();
        return () => { cancelled = true; };
    }

    function attachRunStreams(run, ui) {
        // Store UI reference for the multiplexed metadata stream
        MetadataStreamService.registerRunUI(run.runId, ui);

        // Initialize the multiplexed stream if not already done
        MetadataStreamService.initMultiplexedMetadataStream(cfg);

        // Store run info without individual EventSource
        state.runs.set(run.runId, { ...run, ui });
        // Keep references for UI teardown
        state.runs.get(run.runId).wrap = ui.wrap;
        state.runs.get(run.runId).stopBtn = ui.stopBtn;

        // Gate the iframe load on real stream readiness instead of loading it
        // immediately (the pipeline needs a few seconds to start publishing).
        // Must run after the run is registered in state.runs so the poller's
        // liveness check passes.
        const cancelPolling = waitForStreamThenLoad(run, ui);
        state.runs.get(run.runId).cancelVideoPolling = cancelPolling;
    }

    async function restoreActiveRuns() {
        // Fetch active runs from backend and restore UI cards
        try {
            const runs = await ApiService.fetchRuns();

            if (runs.length === 0) {
                return;
            }

            // Hide hint if there are active runs
            if (els.hintEl) els.hintEl.style.display = 'none';

            for (const runData of runs) {
                const run = {
                    runId: runData.runId,
                    pipelineId: runData.pipelineId,
                    peerId: runData.peerId,
                    metadataFile: runData.metadataFile,
                    modelName: runData.modelName || 'Unknown',
                    pipelineName: runData.pipelineName || '',
                    vlmDevice: runData.vlmDevice || 'cpu',
                    detectionDevice: runData.detectionDevice || 'cpu',
                    prompt: runData.prompt || 'N/A',
                    maxTokens: runData.maxTokens || 'N/A',
                    rtspUrl: runData.rtspUrl || 'N/A',
                    frameRate: runData.frameRate ?? null,
                    chunkSize: runData.chunkSize ?? null,
                    frameWidth: runData.frameWidth ?? null,
                    frameHeight: runData.frameHeight ?? null,
                    frameQuality: runData.frameQuality ?? null,
                };

                const ui = RunCardComponent.createRunElement(run, stopRun);
                // Restored runs don't have saved alert rules; use defaults
                ui.alertRules = runData.alertRules ?? [
                    { substring: 'yes', color: '#ff4444' },
                ];
                els.runsContainer.appendChild(ui.wrap);
                attachRunStreams(run, ui);
                state.selectedRunId = run.runId;

                // If the pipeline was already in error state when the page loaded
                // (detected by the background health monitor before this refresh),
                // show the error immediately without waiting for the next SSE heartbeat.
                if (runData.status === 'error') {
                    RunCardComponent.setRunErrorState(ui);
                }
            }

            updatePipelineInfo(`Restored ${runs.length} active run(s)`);
        } catch (err) {
            console.warn('Failed to restore active runs:', err);
        }
    }

    function initCollectorMetrics() {
        const elements = {
            cpuVal: document.getElementById('cpuVal'),
            ramVal: document.getElementById('ramVal'),
            gpuValues: document.getElementById('gpuValues'),
            gpuError: document.getElementById('gpuError'),
            npuVal: document.getElementById('npuVal'),
            npuStat: document.getElementById('npuStat'),
        };

        MetricsCollectorService.init(elements);
    }

    async function startPipeline(evt) {
        evt.preventDefault();
        const streamSourceType = getSelectedSourceType();
        const rtspUrl = streamSourceType === 'camera'
            ? (els.cameraDeviceSelect?.value || '').trim()
            : (els.rtspInput?.value || '').trim();
        const defaultPrompt = cfg.defaultPrompt || 'Describe what you see in one sentence.';
        const prompt = (els.promptInput.value || '').trim() || defaultPrompt;
        const modelName = (els.modelNameSelect?.value || '').trim();
        const vlmDevice = (els.vlmDeviceSelect?.value || 'cpu').trim().toLowerCase();
        const maxTokensRaw = (els.maxTokensInput?.value || '').toString().trim();
        const maxTokensParsed = Number.parseInt(maxTokensRaw, 10);
        const maxTokens = Number.isFinite(maxTokensParsed) && maxTokensParsed > 0 ? maxTokensParsed : 70;
        const selectedPipelineType = getSelectedPipelineType(); // 'detection' | 'non-detection'
        const isDetectionEnabled = (selectedPipelineType === 'detection');
        const detectionDevice = isDetectionEnabled ? getSelectedDetectionDevice() : null;
        const detectionModelNameRaw = (els.detectionModelNameSelect?.value || '').trim();
        const detectionThresholdRaw = (els.detectionThresholdInput?.value || '').toString().trim();
        const detectionThresholdParsed = Number.parseFloat(detectionThresholdRaw);

        // Derive detection fields only when the selected pipeline is detection
        const detectionModelName = isDetectionEnabled ? (detectionModelNameRaw || null) : null;
        const detectionThreshold = isDetectionEnabled
            ? (Number.isFinite(detectionThresholdParsed) && detectionThresholdParsed >= 0 && detectionThresholdParsed <= 1
                ? detectionThresholdParsed
                : 0.5)
            : null;
        const includeRoiBoundingBox = isDetectionEnabled
            ? Boolean(els.includeRoiBoundingBoxCheckbox?.checked)
            : false;

        // Frame rate, chunk size and frame dimensions
        const frameRateRaw = (els.frameRateInput?.value || '').toString().trim();
        const frameRateParsed = Number.parseInt(frameRateRaw, 10);
        const frameRate = (frameRateRaw !== '' && Number.isFinite(frameRateParsed) && frameRateParsed >= 0) ? frameRateParsed : null;

        const chunkSizeRaw = (els.chunkSizeInput?.value || '').toString().trim();
        const chunkSizeParsed = Number.parseInt(chunkSizeRaw, 10);
        const chunkSize = (chunkSizeRaw !== '' && Number.isFinite(chunkSizeParsed) && chunkSizeParsed >= 1) ? chunkSizeParsed : null;

        const QUALITY_PRESETS = { '1280x720': [1280, 720], '640x480': [640, 480], '480x360': [480, 360] };
        const qualityKey = (els.frameQualitySelect?.value || '').trim();
        let frameWidth = null;
        let frameHeight = null;
        if (qualityKey === 'custom') {
            const wRaw = Number.parseInt((els.customWidthInput?.value || '').trim(), 10);
            const hRaw = Number.parseInt((els.customHeightInput?.value || '').trim(), 10);
            frameWidth = Number.isFinite(wRaw) && wRaw > 0 ? wRaw : null;
            frameHeight = Number.isFinite(hRaw) && hRaw > 0 ? hRaw : null;
        } else {
            const qualityPreset = QUALITY_PRESETS[qualityKey] || null;
            frameWidth = qualityPreset ? qualityPreset[0] : null;
            frameHeight = qualityPreset ? qualityPreset[1] : null;
        }

        // Alert color rules (alert mode only, per-run)
        const alertRules = cfg.alertMode ? readAlertRules() : [];

        // Process optional run name
        const rawRunName = (els.runNameInput?.value || '').trim();
        let runName = RunCardComponent.validateAndPrepareRunName(rawRunName);
        if (runName) {
            const existingRunIds = Array.from(state.runs.keys());
            runName = RunCardComponent.getUniqueRunName(runName, existingRunIds);
        }

        if (!rtspUrl) {
            if (streamSourceType === 'camera') {
                updateCameraWarningVisibility();
                updateStartButtonAvailability();
            }
            return;
        }
        state.isStarting = true;
        updateStartButtonAvailability();
        updatePipelineInfo('Starting pipeline...');
        try {
            const requestBody = {
                rtspUrl,
                prompt,
                detectionModelName,
                detectionThreshold,
                modelName,
                maxNewTokens: maxTokens,
                streamSourceType,
                pipelineType: selectedPipelineType,
                vlmDevice,
                detectionDevice,
                includeRoiBoundingBox,
            };
            if (runName) {
                requestBody.runName = runName;
            }
            if (frameRate !== null) requestBody.frameRate = frameRate;
            if (chunkSize !== null) requestBody.chunkSize = chunkSize;
            if (frameWidth !== null) requestBody.frameWidth = frameWidth;
            if (frameHeight !== null) requestBody.frameHeight = frameHeight;
            const data = await ApiService.startRun(requestBody);

            const run = {
                runId: data.runId,
                pipelineId: data.pipelineId,
                peerId: data.peerId,
                metadataFile: data.metadataFile,
                isEnabledDetection: isDetectionEnabled,
                detectionModelName: detectionModelName,
                detectionThreshold: detectionThreshold,
                modelName: modelName,
                pipelineName: data.pipelineName || `Device: ${vlmDevice.toUpperCase()}`,
                vlmDevice: vlmDevice,
                detectionDevice: detectionDevice,
                prompt: prompt,
                maxTokens: maxTokens,
                rtspUrl: rtspUrl,
                frameRate: frameRate,
                chunkSize: chunkSize,
                frameWidth: frameWidth,
                frameHeight: frameHeight,
                frameQuality: qualityKey || null,
                alertRules: alertRules,
            };

            // Hide the hint when first pipeline starts
            if (els.hintEl) els.hintEl.style.display = 'none';

            const ui = RunCardComponent.createRunElement(run, stopRun);
            ui.alertRules = run.alertRules;
            els.runsContainer.appendChild(ui.wrap);
            attachRunStreams(run, ui);
            updatePipelineInfo(`Latest Run: (${run.runId})`);
            state.selectedRunId = run.runId;
        } catch (err) {
            updatePipelineInfo(`Start failed: ${err.message}`);
        } finally {
            state.isStarting = false;
            updateStartButtonAvailability();
        }
    }

    function init() {
        const initialSettings = SettingsManager.loadSettings();
        state.hasSavedVlmDevicePreference = Boolean(
            initialSettings
            && typeof initialSettings.vlmDevice === 'string'
            && ['cpu', 'gpu', 'npu'].includes(initialSettings.vlmDevice.trim().toLowerCase())
        );

        // Set application title based on alert mode
        const appTitleEl = document.getElementById('appTitle');
        if (appTitleEl && cfg.alertMode) {
            appTitleEl.textContent = 'Live Video Captioning and Alerts';
        }

        // Show alert color rules section only in alert mode
        if (cfg.alertMode) {
            setSectionVisible(els.alertRulesSection, true);
            initAlertRulesUI();
        }

        // Set default RTSP URL from runtime config (before restoring localStorage)
        if (cfg.defaultRtspUrl && els.rtspInput && !els.rtspInput.value) {
            els.rtspInput.value = cfg.defaultRtspUrl;
        }

        // Set default prompt from runtime config (before restoring localStorage)
        if (cfg.defaultPrompt && els.promptInput) {
            // Only set if empty or still has HTML default value
            if (!els.promptInput.value || els.promptInput.value === 'Describe what you see in one sentence.') {
                els.promptInput.value = cfg.defaultPrompt;
            }
        }

        // Resolve caption history for reload: prefer saved UI value, then runtime config default
        if (els.captionHistoryInput) {
            els.captionHistoryInput.value = String(getPreferredCaptionHistoryOnLoad());
        }

        ThemeManager.applyTheme(ThemeManager.detectInitialTheme(), els.themeToggle);
        if (els.themeToggle) {
            els.themeToggle.addEventListener('click', () => {
                ThemeManager.toggleTheme(els.themeToggle);
                ChartManager.updateChartColors();
            });
        }

        syncPipelineTypeOptions();

        // Restore settings from localStorage before loading options
        SettingsManager.restoreSettings(els, cfg);
        SettingsManager.setupSettingsPersistence(els);
        applyCaptionHistorySetting();
        SettingsManager.saveSettings(els);

        if (els.captionHistoryInput) {
            els.captionHistoryInput.addEventListener('change', applyCaptionHistorySetting);
            els.captionHistoryInput.addEventListener('input', handleCaptionHistoryInput);
            els.captionHistoryInput.addEventListener('blur', applyCaptionHistorySetting);
        }

        if (els.pipelineTypeSelect) {
            els.pipelineTypeSelect.addEventListener('change', () => {
                SettingsManager.saveSettings(els);
                toggleDetectionFieldsByText();
            });
        }

        if (els.vlmDeviceSelect) {
            els.vlmDeviceSelect.addEventListener('change', () => {
                refreshModelsBySelectedVlmDevice();
                updateDetectionDeviceOptions();
                updateStartButtonAvailability();
            });
        }

        if (els.streamSourceTypeSelect) {
            els.streamSourceTypeSelect.addEventListener('change', updateStreamSourceInputs);
        }
        if (els.cameraDeviceSelect) {
            els.cameraDeviceSelect.addEventListener('change', () => {
                updateCameraWarningVisibility();
                updateStartButtonAvailability();
            });
        }

        loadCameraDevices();
        updateStreamSourceInputs();
        toggleDetectionFieldsByText();

        function updateCustomDimensionsVisibility() {
            const isCustom = els.frameQualitySelect?.value === 'custom';
            if (els.customDimensionsRow) {
                els.customDimensionsRow.style.display = isCustom ? '' : 'none';
            }
        }
        if (els.frameQualitySelect) {
            els.frameQualitySelect.addEventListener('change', updateCustomDimensionsVisibility);
            updateCustomDimensionsVisibility();
        }

        loadSystemCapabilities().finally(() => {
            loadModels();
            if (cfg.enableDetectionPipeline === true) {
                loadDetectionModels();
            }
        });
        initCollectorMetrics();

        // Restore active runs from backend
        restoreActiveRuns();

        els.form.addEventListener('submit', startPipeline);

        // Wire run-error callback: when the health monitor reports a pipeline is gone,
        // update the card UI immediately without waiting for the user to interact.
        MetadataStreamService.setOnRunError((runId, ui) => {
            RunCardComponent.setRunErrorState(ui);
        });

        // Update lag display every 100ms for all active runs
        setInterval(() => {
            const now = Date.now();
            const runUIs = MetadataStreamService.getRunUIs();
            for (const [runId, ui] of runUIs) {
                const lastTime = MetadataStreamService.getLastCaptionTime(runId);
                if (lastTime && ui.chips) {
                    const lagSeconds = (now - lastTime) / 1000;
                    const lagEl = ui.chips.querySelector('[data-lag]');
                    if (lagEl) {
                        lagEl.textContent = `${lagSeconds.toFixed(2)}s`;
                    }
                }
            }
        }, 100);

        // Cleanup SSE connections when page unloads
        window.addEventListener('beforeunload', () => {
            MetadataStreamService.close();
        });
    }

    init();
})();
