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
        pipelineSelect: document.getElementById('pipelineSelect'),
        maxTokensInput: document.getElementById('maxTokensInput'),
        captionHistoryInput: document.getElementById('captionHistoryInput'),
        rtspInput: document.getElementById('rtspInput'),
        runNameInput: document.getElementById('runNameInput'),
        startBtn: document.getElementById('startBtn'),
        pipelineInfo: document.getElementById('pipelineInfo'),
        runsContainer: document.getElementById('runsContainer'),
        themeToggle: document.getElementById('themeToggle'),
        detectionModelField: document.getElementById('detectionModelField'),
        detectionThresholdField: document.getElementById('detectionThresholdField'),
        detectionModelNameSelect: document.getElementById('detectionModelNameSelect'),
        detectionThresholdInput: document.getElementById('detectionThresholdInput'),
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
    };

    const state = { selectedRunId: null, runs: new Map() };

    (function initDetectionVisibility() {
        const enabledByFlag = cfg.enableDetectionPipeline === true;
        const detectionSection = document.getElementById('detectionSection');
        if (!enabledByFlag) {
            setSectionVisible(detectionSection, false);
        }
    })();

    function setSectionVisible(el, show) {
        if (!el) return;
        el.style.display = show ? '' : 'none';
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
            '#detectionModelNameSelect',
            '#detectionThresholdInput'
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
        const select = els.pipelineSelect;
        if (!select) return;

        const selectedOpt = select.options[select.selectedIndex];
        const label = selectedOpt?.textContent || '';
        const isDetection = label.includes('[Detection]');

        showDetectionFields(isDetection);
    }

    function getSelectedPipelineType() {
        const select = els.pipelineSelect;
        if (!select || select.selectedIndex < 0) return 'non-detection';

        const opt = select.options[select.selectedIndex];
        // Preferred: data attribute set by setPipelineOptions
        const fromData = opt?.dataset?.pipelineType;
        if (fromData === 'detection' || fromData === 'non-detection') return fromData;
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

    function setModelOptions(models) {
        const select = els.modelNameSelect;
        if (!select) return;
        select.innerHTML = '';
        const list = Array.isArray(models) && models.length ? models : [ApiService.DEFAULT_MODEL];
        for (const name of list) {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            select.appendChild(opt);
        }
        const preferred = list.includes(ApiService.DEFAULT_MODEL) ? ApiService.DEFAULT_MODEL : list[0];
        select.value = preferred;
    }

    function setDetectionModelOptions(models) {
        const select = els.detectionModelNameSelect;
        if (!select) return;
        select.innerHTML = '';
        const list = Array.isArray(models) && models.length ? models : [ApiService.DEFAULT_DETECTION_MODEL];
        for (const name of list) {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            select.appendChild(opt);
        }
        const preferred = list.includes(ApiService.DEFAULT_DETECTION_MODEL) ? ApiService.DEFAULT_DETECTION_MODEL : list[0];
        select.value = preferred;
    }

    function setPipelineOptions(pipelines) {
        const select = els.pipelineSelect;
        if (!select) return;
        select.innerHTML = '';

        const list = Array.isArray(pipelines) && pipelines.length
            ? pipelines
            : [{ pipeline_name: ApiService.DEFAULT_PIPELINE, pipeline_type: 'non-detection' }];

        const map = new Map();
        for (const it of list) {
            if (!it || typeof it !== 'object' || typeof it.pipeline_name !== 'string') continue;
            const t = it.pipeline_type === 'detection' ? 'detection' : 'non-detection';
            map.set(it.pipeline_name, { pipeline_name: it.pipeline_name, pipeline_type: t });
        }
        const normalized = Array.from(map.values()).sort((a, b) => {
            if (a.pipeline_type !== b.pipeline_type) {
                return a.pipeline_type === 'non-detection' ? -1 : 1;
            }
            return a.pipeline_name.localeCompare(b.pipeline_name);
        });

        for (const { pipeline_name, pipeline_type } of normalized) {
            const opt = document.createElement('option');
            opt.value = pipeline_name;
            opt.textContent = pipeline_type === 'detection'
                ? `${pipeline_name}  [Detection]`
                : pipeline_name;
            opt.dataset.pipelineType = pipeline_type;
            select.appendChild(opt);
        }

        if (normalized.length > 0) {
            select.value = normalized[0].pipeline_name;
        }

        toggleDetectionFieldsByText();
    }

    async function loadModels() {
        try {
            const models = await ApiService.fetchModels();
            setModelOptions(models);
            SettingsManager.restoreSelectValues(els);
            updatePipelineInfo('Models loaded');
        } catch (_err) {
            setModelOptions([ApiService.DEFAULT_MODEL]);
            SettingsManager.restoreSelectValues(els);
            updatePipelineInfo('Model list unavailable, using default');
        }
    }

    async function loadDetectionModels() {
        try {
            const detectionModels = await ApiService.fetchDetectionModels();
            setDetectionModelOptions(detectionModels);
            SettingsManager.restoreSelectValues(els);
            updatePipelineInfo('Detection models loaded');
        } catch (_err) {
            setDetectionModelOptions([ApiService.DEFAULT_DETECTION_MODEL]);
            SettingsManager.restoreSelectValues(els);
            updatePipelineInfo('Detection model list unavailable, using default');
        }
    }

    async function loadPipelines() {
        try {
            const pipelines = await ApiService.fetchPipelines();
            setPipelineOptions(pipelines);
            SettingsManager.restoreSelectValues(els);
            toggleDetectionFieldsByText();
        } catch (_err) {
            if (els.pipelineServerError) {
                els.pipelineServerError.textContent = 'Pipeline server not reachable. Please check the logs.';
                els.pipelineServerError.style.display = '';
            }
        }
    }

    function tearDownRun(runId, current, message) {
        console.log(`Tearing down run ${runId}`);
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

    function attachRunStreams(run, ui) {
        const base = resolveSignalingBase(cfg.signalingUrl);
        if (base) {
            ui.video.src = `${base}/${run.peerId}`;
        }

        // Store UI reference for the multiplexed metadata stream
        MetadataStreamService.registerRunUI(run.runId, ui);

        // Initialize the multiplexed stream if not already done
        MetadataStreamService.initMultiplexedMetadataStream(cfg);

        // Store run info without individual EventSource
        state.runs.set(run.runId, { ...run, ui });
        // Keep references for UI teardown
        state.runs.get(run.runId).wrap = ui.wrap;
        state.runs.get(run.runId).stopBtn = ui.stopBtn;
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
            gpuVal: document.getElementById('gpuVal'),
            gpuDetail: document.getElementById('gpuDetail'),
            gpuEngines: document.getElementById('gpuEngines'),
            gpuFreq: document.getElementById('gpuFreq'),
            gpuPower: document.getElementById('gpuPower'),
            gpuTemp: document.getElementById('gpuTemp'),
            gpuError: document.getElementById('gpuError'),
        };

        MetricsCollectorService.init(elements);
    }

    async function startPipeline(evt) {
        evt.preventDefault();
        const rtspUrl = els.rtspInput.value.trim();
        const defaultPrompt = cfg.defaultPrompt || 'Describe what you see in one sentence.';
        const prompt = (els.promptInput.value || '').trim() || defaultPrompt;
        const modelName = (els.modelNameSelect?.value || '').trim() || ApiService.DEFAULT_MODEL;
        const pipelineName = (els.pipelineSelect?.value || '').trim() || ApiService.DEFAULT_PIPELINE;
        const maxTokensRaw = (els.maxTokensInput?.value || '').toString().trim();
        const maxTokensParsed = Number.parseInt(maxTokensRaw, 10);
        const maxTokens = Number.isFinite(maxTokensParsed) && maxTokensParsed > 0 ? maxTokensParsed : 70;
        const selectedPipelineType = getSelectedPipelineType(); // 'detection' | 'non-detection'
        const isDetectionEnabled = (selectedPipelineType === 'detection');
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

        // Route to proxy pipeline when Default resolution is selected
        const PROXY_PIPELINE_MAP = {
            'GenAI_Pipeline_on_CPU': 'GenAI_Pipeline_on_CPU_Default_Resolution',
            'GenAI_Pipeline_on_GPU': 'GenAI_Pipeline_on_GPU_Default_Resolution',
        };
        const effectivePipelineName = (qualityKey === 'default' && PROXY_PIPELINE_MAP[pipelineName])
            ? PROXY_PIPELINE_MAP[pipelineName]
            : pipelineName;

        // Alert color rules (alert mode only, per-run)
        const alertRules = cfg.alertMode ? readAlertRules() : [];

        // Process optional run name
        const rawRunName = (els.runNameInput?.value || '').trim();
        let runName = RunCardComponent.validateAndPrepareRunName(rawRunName);
        if (runName) {
            const existingRunIds = Array.from(state.runs.keys());
            runName = RunCardComponent.getUniqueRunName(runName, existingRunIds);
        }

        if (!rtspUrl) return;
        els.startBtn.disabled = true;
        updatePipelineInfo('Starting pipeline...');
        try {
            const requestBody = { rtspUrl, prompt, detectionModelName, detectionThreshold, modelName, maxNewTokens: maxTokens, pipelineName: effectivePipelineName };
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
                pipelineName: pipelineName,
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
            els.startBtn.disabled = false;
        }
    }

    function init() {
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

        if (els.pipelineSelect) {
            els.pipelineSelect.addEventListener('change', toggleDetectionFieldsByText);
        }

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

        loadModels();
        loadPipelines();
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
