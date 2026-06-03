/**
 * Run card UI component
 */
const RunCardComponent = (function () {
    const MODEL_ICON_SVG = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>';
    const DETECTION_ICON_SVG = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="16" rx="2"></rect><path d="M16 2v4"></path><path d="M8 2v4"></path><path d="M3 10h18"></path></svg>';
    const CAMERA_ICON_SVG = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 7l-7 5 7 5V7z"></path><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>';
    const RTSP_ICON_SVG = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 0 20"></path><path d="M12 2a15.3 15.3 0 0 0 0 20"></path></svg>';

    function createChip(text, iconSvg, inlineStyles) {
        const chip = document.createElement('span');
        chip.className = 'chip';
        if (inlineStyles) Object.assign(chip.style, inlineStyles);
        if (iconSvg) chip.insertAdjacentHTML('beforeend', iconSvg);
        chip.appendChild(document.createTextNode(text));
        return chip;
    }

    function createTooltipRow(label, value, valueClassName) {
        const row = document.createElement('div');
        row.className = 'info-tooltip-row';

        const labelEl = document.createElement('strong');
        labelEl.textContent = `${label}:`;

        const valueEl = document.createElement('span');
        if (valueClassName) valueEl.className = valueClassName;
        valueEl.textContent = value;

        row.appendChild(labelEl);
        row.appendChild(document.createTextNode(' '));
        row.appendChild(valueEl);
        return row;
    }

    function getFrameQualityDisplay(frameQuality, frameWidth, frameHeight) {
        if (frameQuality === 'custom') {
            return `Custom (${frameWidth ?? '?'}×${frameHeight ?? '?'})`;
        }
        return ({ best: 'Best (1280×720)', better: 'Better (640×480)', good: 'Good (480×360)' }[frameQuality] || frameQuality);
    }

    function formatRunNameForDisplay(runId) {
        // Convert underscores to spaces for UI display
        if (!runId) return runId;
        return runId.replace(/_/g, ' ');
    }

    function inferSourceType(streamSource) {
        const source = (streamSource || '').toString().trim().toLowerCase();
        if (source.startsWith('/dev/video')) return 'camera';
        return 'rtsp';
    }

    function createRunElement(run, onStopCallback) {
        const wrap = document.createElement('div');
        wrap.className = 'card';
        wrap.style.background = 'var(--panel-strong)';

        const header = document.createElement('div');
        header.className = 'status';
        header.style.margin = '0 0 10px 0';
        header.style.justifyContent = 'space-between';
        header.style.gap = '12px';
        header.style.flexWrap = 'wrap';

        const headerLeft = document.createElement('div');
        headerLeft.style.display = 'flex';
        headerLeft.style.alignItems = 'center';
        headerLeft.style.gap = '8px';
        headerLeft.style.fontSize = '0.85rem';
        headerLeft.style.flexWrap = 'wrap';

        // Determine device from pipeline name
        const deviceType = (run.pipelineName || '').toLowerCase().includes('gpu') ? 'GPU' : 'CPU';
        const deviceIcon = deviceType === 'GPU'
            ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="12" x2="15" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg>'
            : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><circle cx="12" cy="12" r="3"/></svg>';

        // Format run name for display: underscores become spaces
        const displayRunName = formatRunNameForDisplay(run.runId);
        const dot = document.createElement('span');
        dot.className = 'dot active';
        headerLeft.appendChild(dot);

        const runNameWrap = document.createElement('span');
        const runNameLabel = document.createElement('strong');
        runNameLabel.textContent = ' Run Name : ';
        runNameWrap.appendChild(runNameLabel);
        runNameWrap.appendChild(document.createTextNode(displayRunName || 'N/A'));
        headerLeft.appendChild(runNameWrap);

        const divider = document.createElement('span');
        divider.style.color = 'var(--muted)';
        divider.style.margin = '0 4px';
        divider.textContent = '|';
        headerLeft.appendChild(divider);

        const deviceChip = document.createElement('span');
        deviceChip.className = 'chip';
        deviceChip.style.background = 'var(--accent)';
        deviceChip.style.color = 'var(--bg)';
        deviceChip.insertAdjacentHTML('beforeend', deviceIcon);
        const deviceStrong = document.createElement('strong');
        deviceStrong.textContent = deviceType;
        deviceChip.appendChild(deviceStrong);
        headerLeft.appendChild(deviceChip);

        const sourceType = inferSourceType(run.rtspUrl);
        const sourceLabel = sourceType === 'camera' ? 'Camera' : 'RTSP';
        const sourceIcon = sourceType === 'camera' ? CAMERA_ICON_SVG : RTSP_ICON_SVG;
        headerLeft.appendChild(createChip(sourceLabel, sourceIcon));

        headerLeft.appendChild(createChip(run.modelName || 'Unknown', MODEL_ICON_SVG));

        if (run.isEnabledDetection) {
            headerLeft.appendChild(createChip(run.detectionModelName || 'N/A', DETECTION_ICON_SVG));
        }

        // Info button with tooltip
        const infoBtn = document.createElement('button');
        infoBtn.className = 'info-btn';
        infoBtn.type = 'button';
        infoBtn.title = 'View Run details';
        infoBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;

        // Create tooltip element
        const tooltip = document.createElement('div');
        tooltip.className = 'info-tooltip';
        const tooltipTitle = document.createElement('div');
        tooltipTitle.className = 'info-tooltip-title';
        tooltipTitle.textContent = 'Run Details';
        tooltip.appendChild(tooltipTitle);
        tooltip.appendChild(createTooltipRow('Pipeline', run.pipelineName || 'N/A'));
        tooltip.appendChild(createTooltipRow('Stream Source', run.rtspUrl || 'N/A'));
        tooltip.appendChild(createTooltipRow('Max Tokens', String(run.maxTokens ?? 'N/A')));
        tooltip.appendChild(createTooltipRow('Prompt', run.prompt || 'N/A', 'info-tooltip-prompt'));

        if (run.frameRate != null) {
            tooltip.appendChild(createTooltipRow('Frame Rate', String(run.frameRate || 'N/A')));
        }
        if (run.chunkSize != null) {
            tooltip.appendChild(createTooltipRow('Chunk Size', String(run.chunkSize || 'N/A')));
        }
        if (run.frameQuality != null) {
            tooltip.appendChild(
                createTooltipRow(
                    'Frame Quality',
                    getFrameQualityDisplay(run.frameQuality, run.frameWidth, run.frameHeight)
                )
            );
        }
        if (run.isEnabledDetection && (run.detectionModelName ?? '') !== '') {
            tooltip.appendChild(createTooltipRow('Detection Model', run.detectionModelName));
        }
        if (run.isEnabledDetection && (run.detectionThreshold ?? '') !== '') {
            tooltip.appendChild(createTooltipRow('Detection Threshold', String(run.detectionThreshold)));
        }
        tooltip.style.display = 'none';
        document.body.appendChild(tooltip);

        function positionTooltip() {
            const rect = infoBtn.getBoundingClientRect();
            const tooltipWidth = 360;
            let left = rect.left + rect.width / 2 - tooltipWidth / 2;
            // Clamp to viewport with 8px margin
            left = Math.max(8, Math.min(left, window.innerWidth - tooltipWidth - 8));
            tooltip.style.left = left + 'px';
            tooltip.style.top = (rect.bottom + 8) + 'px';
        }

        // Toggle tooltip on click
        infoBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const isVisible = tooltip.style.display === 'block';
            if (!isVisible) {
                tooltip.style.display = 'block';
                positionTooltip();
            } else {
                tooltip.style.display = 'none';
            }
        });

        // Close tooltip when clicking outside
        document.addEventListener('click', (e) => {
            if (!infoBtn.contains(e.target) && !tooltip.contains(e.target)) {
                tooltip.style.display = 'none';
            }
        });

        // Reposition on scroll/resize
        window.addEventListener('scroll', () => {
            if (tooltip.style.display === 'block') positionTooltip();
        }, true);
        window.addEventListener('resize', () => {
            if (tooltip.style.display === 'block') positionTooltip();
        });

        // Wrapper for info button and tooltip
        const infoBtnWrapper = document.createElement('div');
        infoBtnWrapper.className = 'info-btn-wrapper';
        infoBtnWrapper.appendChild(infoBtn);
        headerLeft.appendChild(infoBtnWrapper);

        const grid = document.createElement('div');
        grid.className = 'run-grid';

        const video = document.createElement('iframe');
        video.className = 'run-video';
        video.title = `WebRTC ${run.peerId}`;

        const captionPanel = document.createElement('div');
        captionPanel.className = 'caption-panel';

        const chips = document.createElement('div');
        chips.className = 'chips';
        chips.style.marginTop = '0';
        chips.style.marginBottom = '0';
        chips.style.fontSize = '0.8rem';
        chips.innerHTML = `
            <span class="chip"><strong>TTFT</strong><span data-ttft>—</span></span>
            <span class="chip"><strong>TPOT</strong><span data-tpot>—</span></span>
            <span class="chip"><strong>Throughput</strong><span data-throughput>—</span></span>
            <span class="chip"><strong>Lag</strong><span data-lag>—</span></span>
        `;

        const timestamp = document.createElement('div');
        timestamp.className = 'timestamp';
        timestamp.style.fontSize = '0.75rem';
        timestamp.style.marginLeft = 'auto';
        timestamp.style.whiteSpace = 'nowrap';
        timestamp.textContent = '—';

        // Chips row container with chips on left and timestamp on right
        const chipsRow = document.createElement('div');
        chipsRow.style.display = 'flex';
        chipsRow.style.alignItems = 'center';
        chipsRow.style.justifyContent = 'space-between';
        chipsRow.style.gap = '8px';
        chipsRow.appendChild(chips);
        chipsRow.appendChild(timestamp);

        const watcher = document.createElement('div');
        watcher.className = 'status';
        watcher.style.fontSize = '0.8rem';
        watcher.style.marginBottom = '2px';

        // Wrapper for caption text to enable absolute positioning
        const captionContent = document.createElement('div');
        captionContent.className = 'caption-content';

        const captionTimeline = document.createElement('div');
        captionTimeline.className = 'caption-timeline';

        const initialEntry = document.createElement('div');
        initialEntry.className = 'caption-entry caption-entry-placeholder';
        initialEntry.textContent = 'Waiting for live captions...';
        captionTimeline.appendChild(initialEntry);

        captionContent.appendChild(captionTimeline);

        const stopBtn = document.createElement('button');
        stopBtn.className = 'btn btn-danger';
        stopBtn.type = 'button';
        stopBtn.style.fontSize = '0.85rem';
        stopBtn.style.padding = '6px 12px';
        stopBtn.textContent = 'Stop';
        stopBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (stopBtn.disabled) return;
            stopBtn.disabled = true;
            stopBtn.textContent = 'Stopping...';
            if (onStopCallback) {
                await onStopCallback(run.runId, stopBtn);
            }
        });

        header.appendChild(headerLeft);
        header.appendChild(stopBtn);

        captionPanel.appendChild(chipsRow);
        captionPanel.appendChild(watcher);
        captionPanel.appendChild(captionContent);

        grid.appendChild(video);
        grid.appendChild(captionPanel);

        wrap.appendChild(header);
        wrap.appendChild(grid);

        return { wrap, video, captionTimeline, captionPanel, watcher, timestamp, chips, stopBtn };
    }

    function validateAndPrepareRunName(rawName) {
        // Validate and convert run name: replace spaces with underscores
        if (!rawName || !rawName.trim()) return null;
        // Replace spaces with underscores, trim, and remove special characters except alphanumeric, underscore, hyphen
        let prepared = rawName.trim().replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_-]/g, '');
        return prepared || null;
    }

    function getUniqueRunName(baseName, existingRunIds) {
        // Check for existing runs with the same name and append suffix if needed
        if (!baseName) return null;
        let finalName = baseName;
        let counter = 1;
        while (existingRunIds.includes(finalName)) {
            finalName = `${baseName}_${counter}`;
            counter++;
        }
        return finalName;
    }

    /**
     * Transition a run card into the error state.
     * Called when the backend reports the pipeline instance has gone away.
     * Safe to call multiple times — subsequent calls are no-ops.
     *
     * @param {object} ui - The object returned by createRunElement.
     */
    function setRunErrorState(ui) {
        // Switch dot to pulsing red
        const dot = ui.wrap?.querySelector('.dot');
        if (dot) {
            dot.classList.remove('active');
            dot.classList.add('error');
        }

        // Show error banner in the watcher row
        if (ui.watcher) {
            ui.watcher.innerHTML = `
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" style="flex-shrink:0">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <span style="color:#ef4444;font-weight:600;">Pipeline lost, click Remove to clear</span>
            `;
            ui.watcher.style.gap = '6px';
            ui.watcher.style.display = 'flex';
            ui.watcher.style.alignItems = 'center';
        }

        // Re-enable and relabel the stop button so the user can dismiss the card
        if (ui.stopBtn) {
            ui.stopBtn.disabled = false;
            ui.stopBtn.textContent = 'Remove';
        }
    }

    return {
        createRunElement,
        setRunErrorState,
        validateAndPrepareRunName,
        getUniqueRunName,
        formatRunNameForDisplay
    };
})();
