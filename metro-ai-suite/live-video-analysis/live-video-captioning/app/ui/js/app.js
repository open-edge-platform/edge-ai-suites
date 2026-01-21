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
            setPipelineOptions([ApiService.DEFAULT_PIPELINE]);
            SettingsManager.restoreSelectValues(els);
            toggleDetectionFieldsByText();
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
                };

                const ui = RunCardComponent.createRunElement(run, stopRun);
                els.runsContainer.appendChild(ui.wrap);
                attachRunStreams(run, ui);
                state.selectedRunId = run.runId;
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
            const requestBody = { rtspUrl, prompt, detectionModelName, detectionThreshold, modelName, maxNewTokens: maxTokens, pipelineName };
            if (runName) {
                requestBody.runName = runName;
            }
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
            };

            // Hide the hint when first pipeline starts
            if (els.hintEl) els.hintEl.style.display = 'none';

            const ui = RunCardComponent.createRunElement(run, stopRun);
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
        // Set application title based on agent mode
        const appTitleEl = document.getElementById('appTitle');
        if (appTitleEl && cfg.agentMode) {
            appTitleEl.textContent = 'Live Video Captioning and Alerts';
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

        if (els.pipelineSelect) {
            els.pipelineSelect.addEventListener('change', toggleDetectionFieldsByText);
        }

        loadModels();
        loadPipelines();
        initCollectorMetrics();

        // Restore active runs from backend
        restoreActiveRuns();

        els.form.addEventListener('submit', startPipeline);

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
