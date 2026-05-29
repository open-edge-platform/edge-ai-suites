/**
 * Agentic Alert NVR Dashboard
 */


let activeStreams = [];
let streamMetadata = {};
let cardStates = {};
let alertConfig = [];
let resultsCache = {};
let availableTools = [];

let eventSource = null;
let pollingInterval = null;
let sseConnected = false;

function cssSafeId(str) {
    return str.replace(/[^a-zA-Z0-9-_]/g, '_');
}

function showToast(message, type = 'info') {
    const existing = document.getElementById('toast-notification');
    if (existing) existing.remove();
    
    const colors = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        info: 'bg-blue-500'
    };
    
    const toast = document.createElement('div');
    toast.id = 'toast-notification';
    toast.className = `fixed bottom-4 right-4 ${colors[type] || colors.info} text-white px-4 py-2 rounded-lg shadow-lg z-50 text-sm font-medium`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}

document.addEventListener('DOMContentLoaded', async () => {
    await loadAvailableTools();
    await loadAlertConfig();
    await loadStreams();

    initSSE();
    initResizer();

    window.addEventListener('beforeunload', () => {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        if (metricsWs) {
            metricsWs.close();
            metricsWs = null;
        }
    });
});

function initSSE() {
    if (eventSource) {
        eventSource.close();
    }
    
    console.log('[SSE] Connecting to /events...');
    eventSource = new EventSource('/events');
    
    eventSource.onopen = () => {
        console.log('[SSE] Connected successfully');
        sseConnected = true;
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
            console.log('[SSE] Stopped polling - using SSE');
        }
    };
    
    eventSource.addEventListener('init', (e) => {
        try {
            const data = JSON.parse(e.data);
            console.log('[SSE] Received init:', data.streams?.length, 'streams');
            
            if (data.streams && JSON.stringify(data.streams.sort()) !== JSON.stringify(activeStreams.sort())) {
                activeStreams = data.streams;
                renderGrid();
                renderStreamList();
            }
            
            if (data.results) {
                updateAllResults(data.results);
            }
        } catch (err) {
            console.error('[SSE] Init parse error:', err);
        }
    });
    
    eventSource.addEventListener('analysis', (e) => {
        try {
            const data = JSON.parse(e.data);
            const { stream_id, results } = data;
            
            updateStreamResult(stream_id, results);
        } catch (err) {
            console.error('[SSE] Analysis parse error:', err);
        }
    });
    
    eventSource.addEventListener('keepalive', () => {
        console.log('[SSE] Keepalive received');
    });

    eventSource.addEventListener('alert_fired', (e) => {
        try {
            const data = JSON.parse(e.data);
            console.log('[SSE] Alert fired:', data.alert_name, data.stream_id);
            if (!resultsCache[data.stream_id]) resultsCache[data.stream_id] = {};
            resultsCache[data.stream_id][data.alert_name] = {
                answer: data.answer,
                reason: data.reason,
            };
            updateStreamResult(data.stream_id, resultsCache[data.stream_id]);
        } catch (err) {
            console.error('[SSE] alert_fired parse error:', err);
        }
    });

    eventSource.addEventListener('alert_action', (e) => {
        try {
            const data = JSON.parse(e.data);
            console.log('[SSE] Alert action (tools completed):', data);
        } catch (err) {
            console.error('[SSE] alert_action parse error:', err);
        }
    });
    
    eventSource.onerror = (e) => {
        console.error('[SSE] Connection error');
        sseConnected = false;
        
        if (eventSource.readyState === EventSource.CLOSED) {
            console.log('[SSE] Connection closed, falling back to polling');
            eventSource.close();
            eventSource = null;
            startPollingFallback();
        }
    };
}

function startPollingFallback() {
    if (pollingInterval) return;
    console.log('[Polling] Starting fallback polling...');
    pollingInterval = setInterval(fetchData, 1000);
}

function updateStreamResult(streamId, results) {
    resultsCache[streamId] = results;
    
    const safeId = cssSafeId(streamId);
    const resultDiv = document.getElementById(`result-${safeId}`);
    if (!resultDiv) return;
    
    const selectedAlert = cardStates[streamId];
    renderResultDiv(resultDiv, selectedAlert, results);
}

function refreshAllResults() {
    activeStreams.forEach(id => {
        const safeId = cssSafeId(id);
        const resultDiv = document.getElementById(`result-${safeId}`);
        if (!resultDiv) return;
        
        const selectedAlert = cardStates[id];
        const cachedData = resultsCache[id];
        renderResultDiv(resultDiv, selectedAlert, cachedData);
    });
}

function updateAllResults(allResults) {
    activeStreams.forEach(id => {
        const streamData = allResults[id];
        if (streamData) {
            updateStreamResult(id, streamData);
        }
    });
}

function renderResultDiv(resultDiv, selectedAlert, streamData) {
    if (!streamData) {
        resultDiv.innerHTML = '<p class="text-xs text-gray-400 italic">Waiting for analysis...</p>';
        return;
    }
    
    const enabledAlertNames = alertConfig.filter(a => a.enabled).map(a => a.name);
    
    const MAX_VISIBLE_ALERTS = 4;

    if (selectedAlert === '__ALL__') {
        if (enabledAlertNames.length === 0) {
            resultDiv.innerHTML = '<p class="text-xs text-gray-400 italic">No alerts enabled</p>';
            return;
        }
        let allHtml = '';
        let count = 0;
        enabledAlertNames.forEach(alertName => {
            if (count >= MAX_VISIBLE_ALERTS) return;
            const result = streamData[alertName];
            if (result && result.answer) {
                allHtml += renderResultCard(result, alertName);
                count++;
            }
        });
        resultDiv.innerHTML = allHtml || '<p class="text-xs text-gray-400 italic">Waiting for analysis...</p>';
    } else if (selectedAlert && streamData[selectedAlert] && enabledAlertNames.includes(selectedAlert)) {
        resultDiv.innerHTML = renderResultCard(streamData[selectedAlert], selectedAlert);
    } else {
        resultDiv.innerHTML = '<p class="text-xs text-gray-400 italic">Waiting for analysis...</p>';
    }
}

function renderResultCard(result, alertName) {
    const isYes = result.answer === 'YES';
    const bgClass = isYes ? 'bg-red-50 border-red-300' : 'bg-green-50 border-green-300';
    const textClass = isYes ? 'text-red-800' : 'text-green-800';
    const badgeClass = isYes ? 'bg-red-200 text-red-800' : 'bg-green-200 text-green-800';
    const icon = isYes ? '⚠️' : '✓';
    
    return `
        <div class="rounded border p-2 ${bgClass} transition-colors duration-300">
            <div class="flex justify-between items-center mb-1">
                <span class="font-bold text-xs uppercase ${textClass}">${icon} ${result.answer}</span>
                <span class="text-[10px] px-1.5 py-0.5 rounded font-medium ${badgeClass}">${escapeHtml(alertName)}</span>
            </div>
            <p class="text-xs ${textClass} opacity-80 leading-tight">${escapeHtml(result.reason || 'No details')}</p>
        </div>
    `;
}

// ============== RESIZER LOGIC ==============
function initResizer() {
    const sidebar = document.getElementById('sidebar');
    const resizer = document.getElementById('resizer');
    const container = document.getElementById('main-container');
    let isResizing = false;

    resizer.addEventListener('mousedown', (e) => {
        isResizing = true;
        document.body.style.cursor = 'col-resize';
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        const containerRect = container.getBoundingClientRect();
        const newWidth = e.clientX - containerRect.left;
        if (newWidth > 200 && newWidth < containerRect.width * 0.5) {
            sidebar.style.width = `${newWidth}px`;
        }
    });

    document.addEventListener('mouseup', () => {
        isResizing = false;
        document.body.style.cursor = 'default';
    });
}

async function loadAlertConfig() {
    try {
        const res = await fetch('/config/alerts');
        alertConfig = await res.json();
        renderAlertConfig();
    } catch(e) { 
        console.error("Failed to load alert config:", e);
        alertConfig = [];
        renderAlertConfig();
    }
}

function renderAlertConfig() {
    const container = document.getElementById('alerts-container');
    const addBtn = document.getElementById('add-alert-btn');
    container.innerHTML = '';
    
    alertConfig.forEach((alertEntry, index) => {
        const card = document.createElement('div');
        card.className = "bg-white border border-slate-200 rounded-lg p-3 shadow-sm hover:shadow-md transition-all group relative";
        card.innerHTML = `
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                     <input type="checkbox" 
                       class="w-3.5 h-3.5 rounded border-slate-300 text-blue-600 focus:ring-offset-0 focus:ring-1 focus:ring-blue-500 cursor-pointer" 
                       ${alertEntry.enabled ? 'checked' : ''} 
                       onchange="toggleAlert(${index}, this.checked)">
                     <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Alert ${index + 1}</span>
                </div>
                <button onclick="removeAlert(${index})" class="text-slate-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100" title="Remove Alert">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            <div class="space-y-2">
                <input type="text" 
                       value="${escapeHtml(alertEntry.name)}" 
                       class="w-full text-xs font-semibold text-slate-700 bg-slate-100 border-0 rounded px-2.5 py-1.5 focus:bg-white focus:ring-2 focus:ring-blue-500/20 placeholder:text-slate-400 transition-all outline-none"
                       placeholder="Alert Name"
                       onchange="updateAlertName(${index}, this.value)">
                <textarea class="w-full text-[11px] text-slate-600 bg-slate-100 border-0 rounded px-2.5 py-1.5 resize-none focus:bg-white focus:ring-2 focus:ring-blue-500/20 placeholder:text-slate-400 transition-all outline-none leading-relaxed" 
                          rows="2" 
                          placeholder="Describe visual condition (e.g., Is there fire?)"
                          onchange="updateAlertPrompt(${index}, this.value)">${escapeHtml(alertEntry.prompt)}</textarea>
            </div>
        `;
        container.appendChild(card);
    });
    
    addBtn.style.display = alertConfig.length >= 4 ? 'none' : 'flex';
    
    updateAllDropdowns();
    refreshAllResults();
}

function addAlert() {
    if (alertConfig.length >= 4) return;
    let num = 1;
    while (alertConfig.some(a => a.name === `Alert ${num}`)) {
        num++;
    }
    alertConfig.push({
        name: `Alert ${num}`,
        prompt: "",
        enabled: true,
        tools: ["log_alert", "capture_snapshot"]
    });
    renderAlertConfig();
}

function removeAlert(index) {
    const name = alertConfig[index]?.name || `Alert ${index + 1}`;
    alertConfig.splice(index, 1);
    renderAlertConfig();
    showToast(`Removed ${name}`, "info");
}

function toggleAlert(index, enabled) {
    alertConfig[index].enabled = enabled;
    updateAllDropdowns();
    refreshAllResults();
}

function updateAlertName(index, name) {
    alertConfig[index].name = name;
    updateAllDropdowns();
}

function updateAlertPrompt(index, prompt) {
    alertConfig[index].prompt = prompt;
}

async function saveAlerts() {
    const valid = alertConfig.every(a => a.name.trim() && a.prompt.trim());
    if (!valid && alertConfig.length > 0) {
        showToast("Please fill in all alert names and prompts", "error");
        return;
    }
    
    const names = alertConfig.map(a => a.name.trim().toLowerCase());
    if (new Set(names).size !== names.length) {
        showToast("Alert names must be unique", "error");
        return;
    }
    
    try {
        const res = await fetch('/config/alerts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(alertConfig)
        });
        if (res.ok) {
            showToast("Alerts saved!", "success");
        } else {
            showToast("Failed to save alerts", "error");
        }
    } catch(e) {
        console.error(e);
        showToast("Failed to save alerts", "error");
    }
}

function updateAllDropdowns() {
    const enabledAlerts = alertConfig.filter(a => a.enabled);
    let optionsHtml = '<option value="__ALL__">All Alerts</option>';
    optionsHtml += enabledAlerts.length > 0
        ? enabledAlerts.map(a => `<option value="${escapeHtml(a.name)}">${escapeHtml(a.name)}</option>`).join('')
        : '';
    
    activeStreams.forEach(id => {
        const safeId = cssSafeId(id);
        const select = document.querySelector(`#card-${safeId} select`);
        if (select) {
            const currentVal = select.value;
            select.innerHTML = optionsHtml;
            if (currentVal === '__ALL__') {
                select.value = '__ALL__';
                cardStates[id] = '__ALL__';
            } else if (enabledAlerts.some(a => a.name === currentVal)) {
                select.value = currentVal;
            } else {
                select.value = '__ALL__';
                cardStates[id] = '__ALL__';
            }
        }
    });
}


async function loadAvailableTools() {
    try {
        const res = await fetch('/tools');
        const data = await res.json();
        availableTools = (data.tools || []).filter(t => t.enabled);
        renderToolCheckboxes();
    } catch (e) {
        console.error("Failed to load tools:", e);
        availableTools = [];
    }
}

function renderToolCheckboxes() {
    const container = document.getElementById('tool-checkboxes');
    if (!container) return;
    if (availableTools.length === 0) {
        container.innerHTML = '<span class="text-[9px] text-slate-400 italic">No tools available</span>';
        return;
    }
    container.innerHTML = availableTools.map(tool => `
        <label class="flex items-center gap-1.5 cursor-pointer hover:bg-slate-50 rounded px-1 py-0.5 transition-colors">
            <input type="checkbox" value="${escapeHtml(tool.name)}" checked
                class="tool-checkbox w-3 h-3 rounded border-slate-300 text-blue-600 focus:ring-1 focus:ring-blue-500 cursor-pointer">
            <span class="text-[10px] text-slate-600">${escapeHtml(tool.name)}</span>
            <span class="text-[8px] text-slate-400 ml-auto">${escapeHtml(tool.source || 'builtin')}</span>
        </label>
    `).join('');
}

function getSelectedTools() {
    const checkboxes = document.querySelectorAll('#tool-checkboxes input.tool-checkbox:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

function toggleAllTools() {
    const checkboxes = document.querySelectorAll('#tool-checkboxes input.tool-checkbox');
    if (checkboxes.length === 0) return;
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    checkboxes.forEach(cb => cb.checked = !allChecked);
}

async function loadStreams() {
    try {
        const res = await fetch('/streams');
        const data = await res.json();
        const streams = data.streams || [];
        // Backend returns objects {stream_id, name, url, tools, alerts, ...}; extract IDs for rendering
        activeStreams = streams.map(s => typeof s === 'string' ? s : s.stream_id);
        streamMetadata = {};
        streams.forEach(s => {
            if (typeof s === 'object') {
                streamMetadata[s.stream_id] = s;
                // Restore per-stream alert selection from persisted backend state
                const a = s.alerts;
                cardStates[s.stream_id] = (a && a.length === 1) ? a[0] : '__ALL__';
            }
        });
        renderGrid();
        renderStreamList();
    } catch(e) { console.error("Error loading streams", e); }
}

function renderStreamList() {
    const list = document.getElementById('stream-list');
    if (!list) return;
    list.innerHTML = '';
    if (activeStreams.length === 0) {
        list.innerHTML = '<li class="text-xs text-gray-400 italic">No streams active.</li>';
        return;
    }
    activeStreams.forEach(id => {
        const li = document.createElement('li');
        li.className = "flex justify-between items-center text-xs text-slate-600 bg-white p-2.5 rounded-md border border-slate-200 shadow-sm hover:border-blue-300 transition-all group";
        const meta = streamMetadata[id];
        const displayName = (meta && meta.name) ? meta.name : id;
        const toolCount = meta && meta.tools && meta.tools.length > 0 ? meta.tools.length : null;
        const toolBadge = toolCount
            ? `<span class="text-[8px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-600 font-medium shrink-0">${toolCount} tools</span>`
            : `<span class="text-[8px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-400 font-medium shrink-0">all tools</span>`;
        const alertCount = meta && meta.alerts && meta.alerts.length > 0 ? meta.alerts.length : null;
        const alertBadge = alertCount
            ? `<span class="text-[8px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-600 font-medium shrink-0">${alertCount} alert${alertCount > 1 ? 's' : ''}</span>`
            : `<span class="text-[8px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-400 font-medium shrink-0">all alerts</span>`;
        li.innerHTML = `
            <div class="flex items-center gap-2 overflow-hidden">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0 shadow-[0_0_4px_rgba(16,185,129,0.4)]"></span>
                <span class="font-semibold truncate" title="${escapeHtml(id)}">${escapeHtml(displayName)}</span>
                ${toolBadge}
                ${alertBadge}
            </div>
            <button onclick="deleteStream('${escapeHtml(id)}')" class="text-slate-300 hover:text-red-500 transition p-1 opacity-0 group-hover:opacity-100" title="Delete Stream">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
            </button>
        `;
        list.appendChild(li);
    });
}

async function deleteStream(id) {
    // Optimistic UI update - remove immediately
    const idx = activeStreams.indexOf(id);
    if (idx > -1) {
        activeStreams.splice(idx, 1);
        renderGrid();
        renderStreamList();
    }
    
    try {
        const res = await fetch(`/streams/${id}`, { method: 'DELETE' });
        if(res.ok) {
            const result = await res.json();
            showToast(`Deleted stream '${result.name}'`, "success");
        } else {
            // Revert on failure
            await loadStreams();
            showToast("Failed to delete stream", "error");
        }
    } catch(e) { 
        console.error(e);
        await loadStreams();
        showToast("Error deleting stream", "error"); 
    }
}

async function addNewStream() {
    if (activeStreams.length >= 4) {
        showToast("Limit reached. Delete an existing stream first", "error");
        return;
    }

    const name = (document.getElementById('inp-stream-name') || document.getElementById('inp-stream-id'))?.value.trim() || '';
    const url = document.getElementById('inp-stream-url').value.trim();
    if(!url) {
        showToast("Please enter a stream URL", "error");
        return;
    }

    const tools = getSelectedTools();

    try {
        const res = await fetch('/streams', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, url, tools})
        });
        if(res.ok) {
            const result = await res.json();
            const nameInput = document.getElementById('inp-stream-name') || document.getElementById('inp-stream-id');
            if (nameInput) nameInput.value = '';
            document.getElementById('inp-stream-url').value = '';
            await loadStreams();
            showToast(`Added stream '${result.name}'`, "success");
        } else {
            showToast("Failed to add stream", "error");
        }
    } catch(e) { 
        console.error(e);
        showToast("Error adding stream", "error"); 
    }
}

function updateCardAlert(streamId, alertName) {
    cardStates[streamId] = alertName;
    const alerts = alertName === '__ALL__' ? [] : [alertName];
    fetch(`/streams/${encodeURIComponent(streamId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alerts }),
    }).catch(err => console.error('[PATCH stream alerts]', err));
}

// ============== VIDEO GRID RENDERING ==============
function renderGrid() {
    const grid = document.getElementById('video-grid');
    
    // Re-render check shortcut (compare CSS-safe IDs)
    const existingIds = Array.from(grid.children).map(c => c.id.replace('card-', ''));
    const currentSafeIds = activeStreams.map(id => cssSafeId(id));
    const sameStreams = currentSafeIds.length === existingIds.length && currentSafeIds.every(id => existingIds.includes(id));
    if (sameStreams) {
        // Even if not re-rendering, update dropdowns
        updateAllDropdowns();
        return;
    }

    grid.innerHTML = '';
    
    if (activeStreams.length === 0) {
        grid.innerHTML = '<div class="col-span-2 text-gray-400 text-center mt-10">No active streams. Add one from the sidebar.</div>';
        return;
    }

    // Get enabled alerts for dropdown
    const enabledAlerts = alertConfig.filter(a => a.enabled);

    activeStreams.forEach(id => {
        // Default state - default to "All Alerts"
        if (!cardStates[id]) {
            cardStates[id] = '__ALL__';
        }
        
        const safeId = cssSafeId(id);
        const meta = streamMetadata[id];
        const displayName = (meta && meta.name) ? meta.name : id;

        // Card Container
        const card = document.createElement('div');
        card.id = `card-${safeId}`;
        card.className = "bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden flex flex-col h-full";
        
        // Header (with Title + Live Badge)
        const header = document.createElement('div');
        header.className = "px-4 py-2 bg-gray-50 border-b border-gray-100 flex justify-between items-center";
        header.innerHTML = `<span class="font-bold text-gray-700 text-sm overflow-hidden text-ellipsis whitespace-nowrap mr-2" title="${escapeHtml(id)}">${escapeHtml(displayName)}</span><span class="text-xs text-green-600 font-mono shrink-0">LIVE</span>`;

        // Video Wrapper
        const videoWrapper = document.createElement('div');
        videoWrapper.className = "relative bg-black w-full aspect-video flex items-center justify-center";
        
        const img = document.createElement('img');
        img.src = `/video_feed?stream_id=${encodeURIComponent(id)}`;
        img.className = "w-full h-full object-contain";
        img.alt = id;
        videoWrapper.appendChild(img);

        // Control Bar (Alert Selector)
        const controlBar = document.createElement('div');
        controlBar.className = "px-2 py-2 bg-gray-50 border-b border-gray-100 flex items-center";
        const select = document.createElement('select');
        select.className = "w-full text-xs p-1 border border-gray-300 rounded bg-white focus:outline-none";
        
        // Build dropdown options from enabled alerts
        let selectOptions = '<option value="__ALL__">All Alerts</option>';
        if (enabledAlerts.length > 0) {
            selectOptions += enabledAlerts.map(a => `<option value="${escapeHtml(a.name)}">${escapeHtml(a.name)}</option>`).join('');
        }
        select.innerHTML = selectOptions;
        
        if (cardStates[id]) select.value = cardStates[id];
        select.onchange = (e) => updateCardAlert(id, e.target.value);
        controlBar.appendChild(select);

        // Results Area
        const stats = document.createElement('div');
        stats.id = `result-${safeId}`;
        stats.className = "flex-1 overflow-y-auto p-2 bg-white flex flex-col gap-1 min-h-[80px] max-h-[220px]";
        stats.innerHTML = '<p class="text-xs text-gray-400 italic">Waiting for analysis...</p>';

        card.appendChild(header);
        card.appendChild(videoWrapper);
        card.appendChild(controlBar);
        card.appendChild(stats);
        grid.appendChild(card);
    });
}

async function fetchData() {
    try {
        const response = await fetch('/data');
        const json = await response.json();

        // Update each stream's result area using the shared render function
        activeStreams.forEach(id => {
            const safeId = cssSafeId(id);
            const resultDiv = document.getElementById(`result-${safeId}`);
            if (!resultDiv) return;
            
            const selectedAlert = cardStates[id];
            const streamData = json[id];
            renderResultDiv(resultDiv, selectedAlert, streamData);
        });

    } catch (e) {
        console.error("Error fetching data:", e);
    }
}


// ============== SYSTEM METRICS (WebSocket from live-metrics-service) ==============
let metricsWs = null;
let metricsReconnectTimer = null;
let systemChart = null;

// Track GPU engine metrics for aggregation
const gpuEngineUsages = [];

const MAX_DATA_POINTS = 60;

// Dataset indices in the combined chart
const DS_CPU = 0;
const DS_GPU = 1;
const DS_MEM = 2;

function createCombinedChart(canvasId) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx || typeof Chart === 'undefined') return null;

    function makeGradient(color) {
        const g = ctx.createLinearGradient(0, 0, 0, 200);
        g.addColorStop(0, `${color}30`);
        g.addColorStop(1, `${color}05`);
        return g;
    }

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'CPU %',
                    data: [],
                    borderColor: '#3b82f6',
                    backgroundColor: makeGradient('#3b82f6'),
                    borderWidth: 2,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 0,
                    pointHoverRadius: 3,
                    spanGaps: true
                },
                {
                    label: 'GPU %',
                    data: [],
                    borderColor: '#10b981',
                    backgroundColor: makeGradient('#10b981'),
                    borderWidth: 2,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 0,
                    pointHoverRadius: 3,
                    spanGaps: true
                },
                {
                    label: 'Memory %',
                    data: [],
                    borderColor: '#a855f7',
                    backgroundColor: makeGradient('#a855f7'),
                    borderWidth: 2,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 0,
                    pointHoverRadius: 3,
                    spanGaps: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        usePointStyle: true,
                        pointStyle: 'circle',
                        boxWidth: 6,
                        boxHeight: 6,
                        padding: 16,
                        font: { size: 11 },
                        color: '#64748b'
                    }
                },
                tooltip: {
                    enabled: true,
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%`
                    }
                }
            },
            scales: {
                y: {
                    suggestedMin: 0,
                    suggestedMax: 100,
                    grid: { color: '#e2e8f0' },
                    ticks: {
                        color: '#94a3b8',
                        callback: (v) => v + '%'
                    }
                },
                x: { display: false }
            }
        }
    });
}

function initMetricsCharts() {
    systemChart = createCombinedChart('system-chart');
}

function pushCombinedSample(cpuVal, gpuVal, memVal) {
    if (!systemChart) return;
    const labels = systemChart.data.labels;
    labels.push(new Date().toLocaleTimeString());
    if (labels.length > MAX_DATA_POINTS) labels.shift();

    const datasets = systemChart.data.datasets;
    datasets[DS_CPU].data.push(cpuVal ?? null);
    datasets[DS_GPU].data.push(gpuVal ?? null);
    datasets[DS_MEM].data.push(memVal ?? null);

    for (const ds of datasets) {
        if (ds.data.length > MAX_DATA_POINTS) ds.data.shift();
    }
    systemChart.update('none');
}

function initMetricsWebSocket() {
    const port = (window.RUNTIME_CONFIG || {}).metricsPort || 9090;
    const wsUrl = `ws://${window.location.hostname}:${port}/ws/clients`;

    if (metricsWs) metricsWs.close();

    metricsWs = new WebSocket(wsUrl);

    metricsWs.onopen = () => {
        updateMetricsStatus(true);
        if (metricsReconnectTimer) {
            clearTimeout(metricsReconnectTimer);
            metricsReconnectTimer = null;
        }
    };

    metricsWs.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.metrics) {
                processMetrics(data.metrics);
            }
        } catch (err) {
            console.error('[Metrics] Parse error:', err);
        }
    };

    metricsWs.onclose = () => {
        updateMetricsStatus(false);
        scheduleMetricsReconnect();
    };

    metricsWs.onerror = () => {
        updateMetricsStatus(false);
    };
}

function scheduleMetricsReconnect() {
    if (metricsReconnectTimer) return;
    metricsReconnectTimer = setTimeout(() => {
        metricsReconnectTimer = null;
        initMetricsWebSocket();
    }, 5000);
}

function updateMetricsStatus(connected) {
    const dot = document.getElementById('metrics-status-dot');
    const text = document.getElementById('metrics-status-text');
    if (!dot || !text) return;

    if (connected) {
        dot.innerHTML = '<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>';
        text.textContent = 'Live';
    } else {
        dot.innerHTML = '<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-slate-300 opacity-75"></span><span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-slate-400"></span>';
        text.textContent = 'Connecting...';
    }
}

function processMetrics(metrics) {
    // Reset GPU engine tracking
    gpuEngineUsages.length = 0;

    let cpuVal = null;
    let gpuVal = null;
    let memVal = null;

    metrics.forEach(metric => {
        switch (metric.name) {
            case 'cpu':
                const cpuUsage = metric.fields?.usage_idle != null
                    ? parseFloat((100 - metric.fields.usage_idle).toFixed(1))
                    : null;
                if (cpuUsage != null) {
                    cpuVal = cpuUsage;
                    const cpuEl = document.getElementById('metrics-cpu-val');
                    if (cpuEl) cpuEl.textContent = cpuUsage.toFixed(1) + '%';
                }
                break;
            case 'gpu_engine_usage':
                // Collect all GPU engine usages
                const engineUsage = metric.fields?.usage;
                if (engineUsage != null) {
                    gpuEngineUsages.push(parseFloat(engineUsage));
                }
                break;
            case 'nvidia_smi':
            case 'gpu':
                const gpuUsage = metric.fields?.utilization_gpu || metric.fields?.usage_percent || 0;
                if (gpuUsage != null) {
                    gpuVal = parseFloat(gpuUsage);
                    const gpuEl = document.getElementById('metrics-gpu-val');
                    if (gpuEl) gpuEl.textContent = gpuVal.toFixed(1) + '%';
                }
                break;
            case 'mem':
                const memPercent = metric.fields?.used_percent;
                if (memPercent != null) {
                    memVal = parseFloat(memPercent);
                    const memEl = document.getElementById('metrics-mem-val');
                    if (memEl) memEl.textContent = memVal.toFixed(1) + '%';
                }
                break;
        }
    });

    // Calculate overall GPU usage from maximum engine utilization
    if (gpuEngineUsages.length > 0) {
        const maxGpuUsage = Math.max(...gpuEngineUsages);
        gpuVal = maxGpuUsage;
        const gpuEl = document.getElementById('metrics-gpu-val');
        if (gpuEl) gpuEl.textContent = maxGpuUsage.toFixed(1) + '%';
    }

    // Push all three values as a single time-aligned sample
    pushCombinedSample(cpuVal, gpuVal, memVal);
}

// Initialize metrics system when page loads
function initMetricsSystem() {
    if (typeof Chart === 'undefined') return;
    setTimeout(() => {
        initMetricsCharts();
        initMetricsWebSocket();
    }, 100);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMetricsSystem);
} else {
    initMetricsSystem();
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;')
              .replace(/'/g, '&#039;');
}